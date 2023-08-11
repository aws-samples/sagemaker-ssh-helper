import logging
from datetime import timedelta
from pathlib import Path

from sagemaker.pytorch import PyTorch, TrainingCompilerConfig

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


def test_ssh_with_training_compiler():
    estimator = PyTorch(
        entry_point=(p := Path('source_dir/training/train.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        base_job_name='train-e2e-compiler',
        framework_version='1.12',
        py_version='py38',
        instance_count=1,
        instance_type='ml.g5.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO,
        compiler_config=TrainingCompilerConfig(),
    )

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    ssh_wrapper.start_ssm_connection_and_continue(11022)

    ssh_wrapper.wait_training_job()

    assert estimator.model_data.find("model.tar.gz") != -1
