import logging
import os
from abc import ABC, abstractmethod

import boto3
import sagemaker
# noinspection PyProtectedMember
from sagemaker.estimator import _TrainingJob  # need access to sagemaker internals to get last training job name
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.processing import ProcessingInput, ScriptProcessor, FrameworkProcessor
from sagemaker.processing import ProcessingJob  # Note: processing job is not marked as protected
from sagemaker.transformer import Transformer
# noinspection PyProtectedMember
from sagemaker.transformer import _TransformJob  # need access to sagemaker internals to get last training job name

from sagemaker.sklearn import SKLearnProcessor
from sagemaker.spark import PySparkProcessor

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.proxy import SSMProxy


class SSHEnvironmentWrapper(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self,
                 ssm_iam_role: str,
                 bootstrap_on_start: bool = True,
                 connection_wait_time_seconds: int = 600,
                 sagemaker_session: sagemaker.Session = None,
                 local_user_id: str = None,
                 log_to_stdout: bool = False):
        f"""
        :param ssm_iam_role: the SSM role without prefix, e.g. 'service-role/SageMakerRole'
            See https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-managed-instance-activation.html .

        :param bootstrap_on_start: Kick-off connection procedure upon sagemaker_ssh_helper.setup_and_start_ssh() .

        :param connection_wait_time_seconds: How long to wait before a SageMaker entry point.
            Can be 0 (don't wait).
        """
        self.log_to_stdout = log_to_stdout
        self.local_user_id = local_user_id
        self.sagemaker_session = sagemaker_session or sagemaker.Session()
        self.ssm_manager = SSMManager(region_name=self.sagemaker_session.boto_region_name)
        self.ssh_log = SSHLog(region_name=self.sagemaker_session.boto_region_name)

        if ssm_iam_role != '':
            if self._is_arn(ssm_iam_role):
                raise ValueError(f"ssm_iam_role should be only the part after role/, not a full ARN. "
                                 f"Got: {ssm_iam_role}")

        self.ssm_iam_role = ssm_iam_role
        self.bootstrap_on_start = bootstrap_on_start
        self.connection_wait_time_seconds = connection_wait_time_seconds
        self.augmented = False

    @classmethod
    def dependency_dir(cls):
        return os.path.dirname(__file__)

    def _augment(self):
        self.augmented = True

    def _augment_env(self, env):
        if self.local_user_id is None:
            caller_id = boto3.client('sts').get_caller_identity()
            user_id = caller_id.get('UserId')
        else:
            user_id = self.local_user_id

        user_id_masked = list(user_id)
        for i in range(3, len(user_id_masked) - 4):
            user_id_masked[i] = '*'
        user_id_masked = ''.join(user_id_masked)

        self.logger.info(f"Passing '{user_id_masked}' as a value of the SSHOwner tag of an SSM managed instance")

        env.update({'START_SSH': str(self.bootstrap_on_start).lower(),
                    'SSH_SSM_ROLE': self.ssm_iam_role,
                    'SSH_OWNER_TAG': user_id,
                    'SSH_LOG_TO_STDOUT': str(self.log_to_stdout).lower(),
                    'SSH_WAIT_TIME_SECONDS': f"{self.connection_wait_time_seconds}"})

    @classmethod
    def ssm_role_from_iam_arn(cls, iam_arn: str):
        if not cls._is_arn(iam_arn):
            raise ValueError(f"iam_arn should be a full ARN, got: '{iam_arn}'")
        role_position = iam_arn.find(":role/")
        if role_position == -1:
            raise ValueError("':role/' not found in the iam_arn")
        return iam_arn[role_position + 6:]

    @abstractmethod
    def get_instance_ids(self, retry=360):
        f"""
        :param retry: how many retries (each retry is 10 seconds), 360 is for 1 hour
        """
        pass

    def start_ssm_connection_and_continue(self, ssh_listen_port: int, retry: int = 360,
                                          extra_args: str = ""):
        proxy = self.start_ssm_connection(ssh_listen_port, retry, extra_args)
        proxy.disconnect()

    def start_ssm_connection(self, ssh_listen_port: int, retry: int = 360,
                             extra_args: str = "") -> SSMProxy:
        instance_ids = self.get_instance_ids(retry)
        if not instance_ids:
            raise ValueError("instance_ids cannot be empty")

        instance_id = instance_ids[0]
        if "mi-" not in instance_id:
            raise ValueError(f"instance_id doesn't start with 'mi-': {instance_id}")

        ssm_proxy = SSMProxy(ssh_listen_port, extra_args, self.sagemaker_session.boto_region_name)
        ssm_proxy.connect_to_ssm_instance(instance_id)

        if self.connection_wait_time_seconds > 0:
            ssm_proxy.terminate_waiting_loop()

        return ssm_proxy

    @staticmethod
    def _is_arn(arn):
        import re
        return re.match(r'^arn:(aws|aws-cn|aws-us-gov):iam::([0-9]+):role/(\S+)$', arn)


class SSHEstimatorWrapper(SSHEnvironmentWrapper):
    def __init__(self, estimator: sagemaker.estimator.EstimatorBase, ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600,
                 ssh_instance_count: int = 2, local_user_id: str = None,
                 log_to_stdout: bool = False):
        super().__init__(ssm_iam_role, bootstrap_on_start, connection_wait_time_seconds,
                         estimator.sagemaker_session, local_user_id, log_to_stdout)

        if estimator.instance_groups is not None:
            # TODO: add support for heterogeneous clusters
            self.logger.warning("Heterogeneous clusters are not yet supported, SSH Helper will start only on one node")
            self.ssh_instance_count = 1
        elif ssh_instance_count <= estimator.instance_count:
            self.ssh_instance_count = ssh_instance_count
        else:
            self.ssh_instance_count = estimator.instance_count

        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(estimator.role)
        self.estimator = estimator

    def _augment(self):
        super()._augment()
        self.logger.info(f'Turning on SSH to training job for estimator {self.estimator.__class__}')
        env = self.estimator.environment
        if env is None:
            env = {}
        self._augment_env(env)
        # TODO: promote ssh_instance_count to processing/inference wrappers
        env.update({'SSH_INSTANCE_COUNT': str(self.ssh_instance_count)})
        self.estimator.environment = env

    def get_instance_ids(self, retry=360):
        training_job = self._latest_training_job()
        return self.ssm_manager.get_training_instance_ids(training_job.name, retry * 10, self.ssh_instance_count)

    def _latest_training_job(self):
        training_job: _TrainingJob = self.estimator.latest_training_job
        if training_job is None:
            raise AssertionError("No training jobs found for estimator. Did you call estimator.fit() first?")
        return training_job

    def wait_training_job(self):
        training_job = self._latest_training_job()
        training_job.wait()

    def stop_training_job(self):
        training_job = self._latest_training_job()
        training_job.stop()
        training_job.wait()

    @classmethod
    def create(cls, estimator: sagemaker.estimator.EstimatorBase, connection_wait_time_seconds: int = 600,
               ssh_instance_count: int = 2, local_user_id: str = None, log_to_stdout: bool = False):
        # noinspection PyProtectedMember
        if estimator._current_job_name:
            raise AssertionError("You should call wrapper.create() before estimator.fit().")
        result = SSHEstimatorWrapper(estimator, connection_wait_time_seconds=connection_wait_time_seconds,
                                     ssh_instance_count=ssh_instance_count, local_user_id=local_user_id,
                                     log_to_stdout=log_to_stdout)
        result._augment()
        return result


class SSHModelWrapper(SSHEnvironmentWrapper):
    def __init__(self, model: sagemaker.model.Model,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role,
                         bootstrap_on_start, connection_wait_time_seconds, model.sagemaker_session)
        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(model.role)
        self.model = model

    def _augment(self):
        super()._augment()
        self.logger.info(f'Turning on SSH to endpoint for model {self.model.__class__}')
        env = self.model.env
        if env is None:
            env = {}
        self._augment_env(env)
        self.model.env = env

    def get_instance_ids(self, retry=360):
        return self.ssh_log.get_endpoint_ssm_instance_ids(self.model.endpoint_name, retry * 10)

    def wait_for_endpoint(self):
        self.sagemaker_session.wait_for_endpoint(self.model.endpoint_name)

    @classmethod
    def create(cls, model: sagemaker.model.Model, connection_wait_time_seconds: int = 600):
        if model.endpoint_name:
            raise AssertionError("You should call wrapper.create() before model.deploy().")
        result = SSHModelWrapper(model, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result


class SSHMultiModelWrapper(SSHEnvironmentWrapper):
    def __init__(self, mdm: sagemaker.multidatamodel.MultiDataModel,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role,
                         bootstrap_on_start, connection_wait_time_seconds, mdm.sagemaker_session)
        self.mdm = mdm
        if mdm.model:
            self.model = mdm.model
            if self.ssm_iam_role == '':
                self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(mdm.model.role)
            self.model_wrapper = SSHModelWrapper(mdm.model, self.ssm_iam_role,
                                                 bootstrap_on_start,
                                                 connection_wait_time_seconds)
        else:
            self.model = None
            if self.ssm_iam_role == '':
                self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(mdm.role)

    def _augment(self):
        super()._augment()
        if self.model:
            # noinspection PyProtectedMember
            self.model_wrapper._augment()
        else:
            self.logger.info(f'Turning on SSH to endpoint for multi data model {self.mdm.__class__}')
            env = self.mdm.env
            if env is None:
                env = {}
            self._augment_env(env)
            self.mdm.env = env

    def get_instance_ids(self, retry=360):
        return self.ssh_log.get_endpoint_ssm_instance_ids(self.mdm.endpoint_name, retry * 10)

    def wait_for_endpoint(self):
        self.sagemaker_session.wait_for_endpoint(self.mdm.endpoint_name)

    @classmethod
    def create(cls, mdm: sagemaker.multidatamodel.MultiDataModel, connection_wait_time_seconds: int = 600):
        if hasattr(mdm, 'endpoint_name') and mdm.endpoint_name:
            raise AssertionError("You should call wrapper.create() before mdm.deploy().")
        result = SSHMultiModelWrapper(mdm, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result


class SSHProcessorWrapper(SSHEnvironmentWrapper):
    def __init__(self, processor: sagemaker.processing.Processor,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True,
                 connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role, bootstrap_on_start, connection_wait_time_seconds,
                         processor.sagemaker_session)
        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(processor.role)
        self.processor = processor

    def _augment(self):
        super()._augment()
        self.logger.info(f'Turning on SSH to processor {self.processor.__class__}')
        env = self.processor.env
        if env is None:
            env = {}
        self._augment_env(env)
        self.processor.env = env

    def get_instance_ids(self, retry=360):
        job: ProcessingJob = self.processor.latest_job
        return self.ssm_manager.get_processing_instance_ids(job.job_name, retry * 10)

    def wait_processing_job(self):
        job: ProcessingJob = self.processor.latest_job
        job.wait()

    def augmented_input(self):
        f"""
        Attaches the helper as the processing input. Required for processing jobs until the package is in PyPI.

        Useful for processing jobs that don't support source_dir in run() method, e. g. {PySparkProcessor} and
          {ScriptProcessor} / {SKLearnProcessor}

        :return: a ProcessingInput to pass into processor#run(..., inputs=[...])
        """
        if isinstance(self.processor, FrameworkProcessor):
            self.logger.info("The processor {self.processor.__class__} is a subclass of FrameworkProcessor. "
                             "It's recommended to pass SageMaker SSH Helper as a dependency to the run() method "
                             "with dependencies=[SSHProcessorWrapper.dependency_dir()].")

        return ProcessingInput(source=SSHProcessorWrapper.dependency_dir(),
                               destination='/opt/ml/processing/input/sagemaker_ssh_helper',
                               input_name='sagemaker_ssh_helper')

    @classmethod
    def create(cls, processor: sagemaker.processing.Processor, connection_wait_time_seconds: int = 600):
        if processor.latest_job:
            raise AssertionError("You should call wrapper.create() before processor.run()")
        result = SSHProcessorWrapper(processor, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result


class SSHTransformerWrapper(SSHEnvironmentWrapper):
    def __init__(self, transformer: sagemaker.transformer.Transformer, model_wrapper: SSHModelWrapper):
        super().__init__('', True, model_wrapper.connection_wait_time_seconds, transformer.sagemaker_session)
        self.transformer = transformer
        self.model_wrapper = model_wrapper

    def _augment(self):
        super()._augment()

    def get_instance_ids(self, retry=360):
        job: _TransformJob = self.transformer.latest_transform_job
        return self.ssm_manager.get_transformer_instance_ids(job.job_name, retry * 10)

    def wait_transform_job(self):
        job: _TransformJob = self.transformer.latest_transform_job
        job.wait()

    @classmethod
    def create(cls, transformer: sagemaker.transformer.Transformer, model_wrapper: SSHModelWrapper):
        if not model_wrapper.augmented:
            raise ValueError(f"Model Wrapper is not yet augmented. Consider constructing object with create().")
        if model_wrapper.model.name != transformer.model_name:
            raise ValueError(f"Transformer and model should have the same name, "
                             f"got: {transformer.model_name} and {transformer.model_name}")
        if transformer.latest_transform_job:
            raise AssertionError("You should call wrapper.create() before transformer.transform()")
        result = SSHTransformerWrapper(transformer, model_wrapper)
        result._augment()
        return result
