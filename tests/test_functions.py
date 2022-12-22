import pytest

from sagemaker.pytorch import PyTorch
from sagemaker_ssh_helper.wrapper import SSHEnvironmentWrapper, SSHEstimatorWrapper


def test_sm_role_ini(request):
    assert str(request.config.getini('sagemaker_role')).startswith("arn:aws:iam::")


def test_ssm_role_from_arn():
    assert SSHEnvironmentWrapper.ssm_role_from_iam_arn("arn:aws:iam::012345678901:role/service-role/SageMakerRole") \
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
