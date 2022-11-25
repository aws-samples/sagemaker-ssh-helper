import logging
import os
from abc import ABC, abstractmethod

import boto3
import sagemaker
# noinspection PyProtectedMember
from sagemaker.estimator import _TrainingJob  # need access to sagemaker internals to get last training job name
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.processing import ProcessingJob, ProcessingInput, ScriptProcessor

from sagemaker.sklearn import SKLearnProcessor
from sagemaker.spark import PySparkProcessor

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.proxy import SSMProxy


class SSHEnvironmentWrapper(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper')
    ssh_log = None

    def __init__(self,
                 ssm_iam_role: str,
                 bootstrap_on_start: bool = True,
                 connection_wait_time_seconds: int = 600):
        """

        :param ssm_iam_role: the SSM role without prefix, e.g. 'service-role/SageMakerRole'
            See https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-managed-instance-activation.html .

        :param bootstrap_on_start: Kick-off connection procedure upon sagemaker_ssh_helper.setup_and_start_ssh() .

        :param connection_wait_time_seconds: How long to wait before a SageMaker entry point.
            Can be 0 (don't wait).
        """
        self.ssh_log = SSHLog()

        if ssm_iam_role != '':
            assert not ssm_iam_role.startswith("arn:aws:iam::"), "should be the part after role/, not ARN"

        self.ssm_iam_role = ssm_iam_role
        self.bootstrap_on_start = bootstrap_on_start
        self.connection_wait_time_seconds = connection_wait_time_seconds

    @classmethod
    def dependency_dir(cls):
        return os.path.dirname(__file__)

    @abstractmethod
    def _augment(self):
        pass

    def _augment_env(self, env):
        caller_id = boto3.client('sts').get_caller_identity()
        user_id = caller_id.get('UserId')

        self.logger.info(f"Passing {user_id} as a value of the SSHOwner tag of an SSM managed instance")

        env.update({'START_SSH': str(self.bootstrap_on_start).lower(),
                    'SSH_SSM_ROLE': self.ssm_iam_role,
                    'SSH_SSM_TAGS': f"Key=SSHOwner,Value={user_id}",
                    'SSH_WAIT_TIME_SECONDS': f"{self.connection_wait_time_seconds}"})

    @classmethod
    def ssm_role_from_iam_arn(cls, iam_arn: str):
        assert iam_arn.startswith('arn:aws:iam::')
        role_position = iam_arn.find(":role/")
        assert role_position != -1
        return iam_arn[role_position + 6:]

    @abstractmethod
    def get_instance_ids(self, retry=360):
        """
        :param retry: how many retries (each retry is 10 seconds), 360 is for 1 hour
        """
        pass

    def start_ssm_connection_and_continue(self, ssh_listen_port: int, retry: int = 360,
                                          extra_args: str = ""):
        p = self.start_ssm_connection(ssh_listen_port, retry, extra_args)
        p.terminate()

    def start_ssm_connection(self, ssh_listen_port: int, retry: int = 360,
                             extra_args: str = ""):
        instance_ids = self.get_instance_ids(retry)
        assert instance_ids

        instance_id = instance_ids[0]
        assert "mi-" in instance_id

        ssm_proxy = SSMProxy(ssh_listen_port, extra_args)
        p = ssm_proxy.connect_to_ssm_instance(instance_id)

        if self.connection_wait_time_seconds > 0:
            ssm_proxy.terminate_waiting_loop()

        return p


class SSHEstimatorWrapper(SSHEnvironmentWrapper):
    def __init__(self, estimator: sagemaker.estimator.Framework, ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600,
                 ssh_instance_count: int = 2):
        super().__init__(ssm_iam_role, bootstrap_on_start, connection_wait_time_seconds)

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
        self.logger.info(f'Turning on SSH to training job for estimator {self.estimator.__class__}')
        env = self.estimator.environment
        if env is None:
            env = {}
        self._augment_env(env)
        # TODO: promote ssh_instance_count to processing/inference wrappers
        env.update({'SSH_INSTANCE_COUNT': str(self.ssh_instance_count)})
        self.estimator.environment = env

    def get_instance_ids(self, retry=360):
        training_job: _TrainingJob = self.estimator.latest_training_job
        return self.ssh_log.get_training_ssm_instance_ids(training_job.name, retry, self.ssh_instance_count)

    def wait_training_job(self):
        training_job: _TrainingJob = self.estimator.latest_training_job
        training_job.wait()

    def stop_training_job(self):
        training_job: _TrainingJob = self.estimator.latest_training_job
        training_job.stop()
        training_job.wait()

    @classmethod
    def create(cls, estimator: sagemaker.estimator.Framework, connection_wait_time_seconds: int = 600,
               ssh_instance_count: int = 2):
        result = SSHEstimatorWrapper(estimator, connection_wait_time_seconds=connection_wait_time_seconds,
                                     ssh_instance_count=ssh_instance_count)
        result._augment()
        return result


class SSHModelWrapper(SSHEnvironmentWrapper):
    def __init__(self, model: sagemaker.model.FrameworkModel,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role,
                         bootstrap_on_start, connection_wait_time_seconds)
        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(model.role)
        self.model = model

    def _augment(self):
        self.logger.info(f'Turning on SSH to endpoint for model {self.model.__class__}')
        env = self.model.env
        if env is None:
            env = {}
        self._augment_env(env)
        self.model.env = env

    def get_instance_ids(self, retry=360):
        return SSHLog().get_endpoint_ssm_instance_ids(self.model.endpoint_name, retry)

    def wait_for_endpoint(self):
        sagemaker.Session().wait_for_endpoint(self.model.endpoint_name)

    @classmethod
    def create(cls, model: sagemaker.model.FrameworkModel, connection_wait_time_seconds: int = 600):
        result = SSHModelWrapper(model, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result


class SSHMultiModelWrapper(SSHEnvironmentWrapper):
    def __init__(self, mdm: sagemaker.multidatamodel.MultiDataModel,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True, connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role,
                         bootstrap_on_start, connection_wait_time_seconds)
        self.mdm = mdm
        assert isinstance(mdm.model, sagemaker.model.FrameworkModel)
        self.model = mdm.model
        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(mdm.model.role)
        self.model_wrapper = SSHModelWrapper(mdm.model, self.ssm_iam_role,
                                             bootstrap_on_start,
                                             connection_wait_time_seconds)

    def _augment(self):
        # noinspection PyProtectedMember
        self.model_wrapper._augment()

    def get_instance_ids(self, retry=360):
        return SSHLog().get_endpoint_ssm_instance_ids(self.mdm.endpoint_name, retry)

    def wait_for_endpoint(self):
        sagemaker.Session().wait_for_endpoint(self.mdm.endpoint_name)

    @classmethod
    def create(cls, mdm: sagemaker.multidatamodel.MultiDataModel, connection_wait_time_seconds: int = 600):
        result = SSHMultiModelWrapper(mdm, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result


class SSHProcessorWrapper(SSHEnvironmentWrapper):
    def __init__(self, processor: sagemaker.processing.Processor,
                 ssm_iam_role: str = '',
                 bootstrap_on_start: bool = True,
                 connection_wait_time_seconds: int = 600):
        super().__init__(ssm_iam_role, bootstrap_on_start, connection_wait_time_seconds)
        if self.ssm_iam_role == '':
            self.ssm_iam_role = SSHEnvironmentWrapper.ssm_role_from_iam_arn(processor.role)
        self.processor = processor

    def _augment(self):
        self.logger.info(f'Turning on SSH to processor {self.processor.__class__}')
        env = self.processor.env
        if env is None:
            env = {}
        self._augment_env(env)
        self.processor.env = env

    def get_instance_ids(self, retry=360):
        job: ProcessingJob = self.processor.latest_job
        return SSHLog().get_processing_ssm_instance_ids(job.job_name, retry)

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
        return ProcessingInput(source=SSHProcessorWrapper.dependency_dir(),
                               destination='/opt/ml/processing/input/sagemaker_ssh_helper',
                               input_name='sagemaker_ssh_helper')

    @classmethod
    def create(cls, processor: sagemaker.processing.Processor, connection_wait_time_seconds: int = 600):
        result = SSHProcessorWrapper(processor, connection_wait_time_seconds=connection_wait_time_seconds)
        result._augment()
        return result
