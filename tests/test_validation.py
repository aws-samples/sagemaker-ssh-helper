import logging
from datetime import timedelta

import pytest
from sagemaker.pytorch import PyTorch

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


def test_calling_fit_before_wrapper_creates_exception():
    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=1).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    estimator.fit(wait=False)

    with pytest.raises(ValueError):
        _ = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
