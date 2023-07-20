import logging
import os
from datetime import timedelta

import pytest
from sagemaker import Session
# noinspection PyProtectedMember
from sagemaker.estimator import _TrainingJob
from sagemaker.pytorch import PyTorch

from sagemaker_ssh_helper.detached_sagemaker import DetachedEstimator
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


# noinspection DuplicatedCode
def test_attach_estimator():
    estimator = PyTorch(entry_point=os.path.basename('source_dir/training/train.py'),
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    _ = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    job: _TrainingJob = estimator.latest_training_job
    ssh_wrapper = SSHEstimatorWrapper.attach(job.name)

    logging.info(f"To connect over SSH run: sm-local-ssh-training connect {ssh_wrapper.training_job_name()}")
    instance_ids = ssh_wrapper.get_instance_ids()
    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")

    ssh_wrapper.start_ssm_connection_and_continue(11022)

    ssh_wrapper.wait_training_job()

    assert estimator.model_data.find("model.tar.gz") != -1


def test_cannot_fit_detached_estimator():
    estimator = DetachedEstimator.attach('training-job-name', Session())

    with pytest.raises(ValueError):
        _ = SSHEstimatorWrapper.create(estimator)


def test_can_fetch_job_name_from_detached_estimator():
    ssh_wrapper = SSHEstimatorWrapper.attach('training-job-name', Session())

    job_name = ssh_wrapper.training_job_name()

    assert job_name == 'training-job-name'
