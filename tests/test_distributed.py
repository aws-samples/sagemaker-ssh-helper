import logging
import os

import pytest
from sagemaker.pytorch import PyTorch

import sagemaker_ssh_helper
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


def test_node_rank_from_env_json():
    os.environ["SAGEMAKER_BASE_DIR"] = os.path.join(os.path.dirname(__file__), "opt_ml")
    node_rank = sagemaker_ssh_helper.env.sm_get_node_rank()
    assert node_rank == 0


def test_node_rank_from_env_json_non_existing_rc():
    os.environ["SAGEMAKER_BASE_DIR"] = os.path.join(os.path.dirname(__file__), "opt_ml_non_existing")
    node_rank = sagemaker_ssh_helper.env.sm_get_node_rank()
    assert node_rank == 0


def test_distributed_training_with_default_instance_count(request):
    instance_count = 3
    default_ssh_instance_count = 2
    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=instance_count,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)
    mi_ids = ssh_wrapper.get_instance_ids(retry=60)
    ssh_wrapper.stop_training_job()
    assert len(mi_ids) == default_ssh_instance_count


@pytest.mark.parametrize("ssh_instance_count", [3, 1])
def test_distributed_training_with_changed_instance_count(request, ssh_instance_count):
    instance_count = 3
    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=instance_count,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600,
                                             ssh_instance_count=ssh_instance_count)

    estimator.fit(wait=False)
    mi_ids = ssh_wrapper.get_instance_ids(retry=60)
    ssh_wrapper.stop_training_job()
    assert len(mi_ids) == ssh_instance_count


def test_distributed_training_mpi_single_node(request):
    instance_count = 1
    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=instance_count,
                        instance_type='ml.g4dn.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO,
                        distribution={
                            'mpi': {
                                'enabled': True,
                                'processes_per_host': 4,
                            }
                        })

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)
    mi_ids = ssh_wrapper.get_instance_ids(retry=60)
    ssh_wrapper.stop_training_job()
    assert len(mi_ids) == 1
