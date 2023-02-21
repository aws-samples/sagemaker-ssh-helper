import logging

import pytest
import sagemaker
from sagemaker.pytorch import PyTorch

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


@pytest.mark.manual
def test_train_placeholder_manual(request):
    bucket = sagemaker.Session().default_bucket()
    checkpoints_prefix = f"s3://{bucket}/checkpoints/"

    estimator = PyTorch(entry_point='train_placeholder.py',
                        source_dir='source_dir/training_placeholder/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training-manual',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO,
                        checkpoint_s3_uri=checkpoints_prefix)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

    estimator.fit(wait=False)

    instance_ids = ssh_wrapper.get_instance_ids(60)
    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")

    ssh_wrapper.wait_training_job()
