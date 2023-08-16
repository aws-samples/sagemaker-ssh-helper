import logging
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import boto3
import pytest
import sagemaker.config
from sagemaker import Model

from sagemaker.pytorch import PyTorch

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.wrapper import SSHEnvironmentWrapper, SSHEstimatorWrapper, SSHModelWrapper
from test_util import _create_bucket_if_doesnt_exist

logger = logging.getLogger('sagemaker-ssh-helper:test_functions')


def test_ssm_role_from_arn():
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws:iam::012345678901:role/service-role/SageMakerRole") \
           == 'service-role/SageMakerRole'


def test_ssm_role_from_arn_cn_us_gov():
    # See: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws-cn:iam::012345678901:role/service-role/SageMakerRole") \
           == 'service-role/SageMakerRole'
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn(
        "arn:aws-us-gov:iam::012345678901:role/service-role/SageMakerRole") \
        == 'service-role/SageMakerRole'


def test_ssm_role_fail():
    with pytest.raises(ValueError):
        SSHEnvironmentWrapper.ssm_role_from_iam_arn("service-role/SageMakerRole")


def test_wrapper_checks_ssm_role_bad_prefix():
    with pytest.raises(ValueError):
        SSHEstimatorWrapper(
            PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/service-role/SageMakerRole',
                    instance_count=1, instance_type='ml.m5.large'),
            ssm_iam_role='arn:aws:iam::0123456789012:role/service-role/SageMakerRole',
            bootstrap_on_start=True,
            connection_wait_time_seconds=3600
        )


def test_wrapper_checks_ssm_role_good_prefix():
    SSHEstimatorWrapper(
        PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/service-role/SageMakerRole',
                instance_count=1, instance_type='ml.m5.large'),
        ssm_iam_role='service-role/SageMakerRole',
        bootstrap_on_start=True,
        connection_wait_time_seconds=3600
    )


def test_wrapper_infers_ssm_role():
    wrapper = SSHEstimatorWrapper(
        PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/service-role/SageMakerRole',
                instance_count=1, instance_type='ml.m5.large'),
        bootstrap_on_start=True,
        connection_wait_time_seconds=3600
    )
    assert wrapper.ssm_iam_role == 'service-role/SageMakerRole'


def test_ssm_role_from_arn_simple():
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws:iam::012345678901:role/SageMakerRole") \
           == 'SageMakerRole'


def test_ssm_role_fail_simple():
    with pytest.raises(ValueError):
        SSHEnvironmentWrapper.ssm_role_from_iam_arn("SageMakerRole")


def test_wrapper_checks_ssm_role_bad_prefix_simple():
    with pytest.raises(ValueError):
        SSHEstimatorWrapper(
            PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/SageMakerRole',
                    instance_count=1, instance_type='ml.m5.large'),
            ssm_iam_role='arn:aws:iam::0123456789012:role/SageMakerRole',
            bootstrap_on_start=True,
            connection_wait_time_seconds=3600
        )


def test_wrapper_checks_ssm_role_good_prefix_simple():
    SSHEstimatorWrapper(
        PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/SageMakerRole',
                instance_count=1, instance_type='ml.m5.large'),
        ssm_iam_role='SageMakerRole',
        bootstrap_on_start=True,
        connection_wait_time_seconds=3600
    )


def test_wrapper_infers_ssm_role_simple():
    wrapper = SSHEstimatorWrapper(
        PyTorch(entry_point='', image_uri='', role='arn:aws:iam::012345678901:role/SageMakerRole',
                instance_count=1, instance_type='ml.m5.large'),
        bootstrap_on_start=True,
        connection_wait_time_seconds=3600
    )
    assert wrapper.ssm_iam_role == 'SageMakerRole'


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Not yet working")
def test_model_wrapper_infers_ssm_role_with_defaults():
    from sagemaker.huggingface import HuggingFaceModel
    model = HuggingFaceModel(
        model_data='',
        transformers_version='4.17.0',
        pytorch_version='1.10.2',
        py_version='py38',
        dependencies=[SSHModelWrapper.dependency_dir()]
    )

    # TODO: This is not working yet.

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    assert ssh_wrapper.ssm_iam_role


# noinspection DuplicatedCode
def test_estimator_wrapper_infers_ssm_role_with_defaults():
    estimator = PyTorch(entry_point='',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    assert ssh_wrapper.ssm_iam_role


def test_bucket_exists():
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    custom_bucket_name = f'sagemaker-test-bucket-{account_id}'
    _ = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket.delete()


def test_sagemaker_default_config_location():
    f"""
    See: https://sagemaker.readthedocs.io/en/stable/overview.html#default-configuration-file-location
    See: {sagemaker.config.config_schema.SAGEMAKER_PYTHON_SDK_CONFIG_SCHEMA}
    """
    import os
    from platformdirs import site_config_dir, user_config_dir

    # Prints the location of the admin config file
    logging.info(os.path.join(site_config_dir("sagemaker"), "config.yaml"))

    # Prints the location of the user config file
    logging.info(os.path.join(user_config_dir("sagemaker"), "config.yaml"))


def test_dirname():
    assert os.path.dirname('source_dir/training/train.py') == 'source_dir/training'


def test_cloud_watch_url_training():
    url = SSHLog().get_training_cloudwatch_url('ssh-training-2023-04-20-17-03-10-793')
    logging.info(url)
    assert url == "https://eu-west-1.console.aws.amazon.com/cloudwatch/home?" \
                  "region=eu-west-1#logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTrainingJobs$3F" \
                  "logStreamNameFilter$3Dssh-training-2023-04-20-17-03-10-793$252F"


def test_cloud_watch_url_training_china():
    url = SSHLog(region_name="cn-north-1").get_training_cloudwatch_url('ssh-training-sklearn-2023-02-20-22-34-59-078')
    logging.info(url)
    assert url == "https://cn-north-1.console.amazonaws.cn/cloudwatch/home?" \
                  "region=cn-north-1#logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTrainingJobs$3F" \
                  "logStreamNameFilter$3Dssh-training-sklearn-2023-02-20-22-34-59-078$252F"


def test_cloud_watch_url_training_us_gov():
    url = SSHLog(region_name="us-gov-west-1").get_training_cloudwatch_url('ssh-training-sklearn-2023-02-20-22-34-59-078')
    logging.info(url)
    assert url == "https://us-gov-west-1.console.amazonaws-us-gov.com/cloudwatch/home?" \
                  "region=us-gov-west-1#logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTrainingJobs$3F" \
                  "logStreamNameFilter$3Dssh-training-sklearn-2023-02-20-22-34-59-078$252F"


def test_cloud_watch_url_endpoint():
    url = SSHLog().get_endpoint_cloudwatch_url('ssh-inference-tf-2023-04-21-09-07-10-172')
    logging.info(url)
    assert url == "https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#" \
                  "logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FEndpoints$252F" \
                  "ssh-inference-tf-2023-04-21-09-07-10-172"


def test_cloud_watch_url_transform():
    url = SSHLog().get_processing_cloudwatch_url('ssh-pytorch-processing-2023-04-21-08-15-04-579')
    logging.info(url)
    assert url == "https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#" \
                  "logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FProcessingJobs$3F" \
                  "logStreamNameFilter$3Dssh-pytorch-processing-2023-04-21-08-15-04-579$252F"


def test_cloud_watch_url_transformer():
    url = SSHLog().get_transform_cloudwatch_url('ssh-batch-transform-2023-04-21-06-45-46-843')
    assert url == "https://eu-west-1.console.aws.amazon.com/cloudwatch/home?region=eu-west-1#" \
                  "logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTransformJobs$3F" \
                  "logStreamNameFilter$3Dssh-batch-transform-2023-04-21-06-45-46-843$252F"


def test_local_session():
    from sagemaker.utils import resolve_value_from_config
    from sagemaker import LocalSession
    from sagemaker.config import MODEL_EXECUTION_ROLE_ARN_PATH
    role: str = resolve_value_from_config(None, MODEL_EXECUTION_ROLE_ARN_PATH, sagemaker_session=LocalSession())
    assert role.startswith("arn:aws:iam")
    from sagemaker.workflow.pipeline_context import PipelineSession
    role: str = resolve_value_from_config(None, MODEL_EXECUTION_ROLE_ARN_PATH, sagemaker_session=PipelineSession())
    assert role.startswith("arn:aws:iam")
    from sagemaker.workflow.pipeline_context import LocalPipelineSession
    role: str = resolve_value_from_config(None, MODEL_EXECUTION_ROLE_ARN_PATH, sagemaker_session=LocalPipelineSession())
    assert role.startswith("arn:aws:iam")


def test_entry_point_source_dir():
    entry_point = (p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name
    source_dir = str(p.parents[0])

    assert entry_point == 'inference_ssh.py'
    assert source_dir == 'source_dir/inference_hf_accelerate'
    assert Path('source_dir/inference_hf_accelerate/') != 'source_dir/inference_hf_accelerate'
    assert str(Path('source_dir/inference_hf_accelerate/')) == 'source_dir/inference_hf_accelerate'


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Not working yet")
def test_model_repacking_from_scratch():
    model = Model(
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        entry_point=(p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None  # FIXME: not working
    # FIXME: SAGEMAKER_SUBMIT_DIRECTORY = file://source_dir/inference_hf_accelerate instead of /opt/ml/model/code


def test_model_repacking_with_existing_model():
    model = Model(
        model_data="s3://sagemaker-eu-west-1-169264033083/data/acc_model.tar.gz",
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        entry_point=(p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Not working yet")
def test_model_repacking_default_entry_point_with_existing_model():
    model = Model(
        model_data="s3://sagemaker-eu-west-1-169264033083/data/acc_model.tar.gz",
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        source_dir=str(Path('source_dir/inference_hf_accelerate/')),
        # entry_point is send in the DJL serving.properties file
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None  # FIXME: not working
    # FIXME: SAGEMAKER_SUBMIT_DIRECTORY = file://source_dir/inference_hf_accelerate instead of /opt/ml/model/code


def test_called_process_error_with_output():
    got_error = False
    try:
        # should fail, because we're not connected to a remote kernel
        subprocess.check_output("sm-local-ssh-ide run-command python --version".split(' '), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output.decode('latin1').strip()
        logger.info(f"Got error (expected): {output}")
        got_error = True
        assert output == "ssh: connect to host localhost port 10022: Connection refused"
    assert got_error
