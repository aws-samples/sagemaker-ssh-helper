import boto3
import pytest

from sagemaker.pytorch import PyTorch
from sagemaker_ssh_helper.wrapper import SSHEnvironmentWrapper, SSHEstimatorWrapper
from test_util import _create_bucket_if_doesnt_exist


def test_ssm_role_from_arn():
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws:iam::012345678901:role/service-role/SageMakerRole") \
           == 'service-role/SageMakerRole'


def test_ssm_role_from_arn_cn_us_gov():
    # See: https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws-cn:iam::012345678901:role/service-role/SageMakerRole") \
           == 'service-role/SageMakerRole'
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws-us-gov:iam::012345678901:role/service-role/SageMakerRole") \
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


def test_bucket_exists():
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    custom_bucket_name = f'sagemaker-test-bucket-{account_id}'
    _ = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket.delete()
