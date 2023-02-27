import logging
import os
import time

import pytest
from sagemaker.mxnet import MXNet
from sagemaker.parameter import CategoricalParameter, ContinuousParameter, IntegerParameter
from sagemaker.tuner import HyperparameterTuner

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper


def test_clean_hpo(request):
    estimator = MXNet(entry_point=os.path.basename('source_dir/training_clean/train_clean.py'),
                      source_dir='source_dir/training_clean/',
                      dependencies=[SSHEstimatorWrapper.dependency_dir()],
                      role=request.config.getini('sagemaker_role'),
                      py_version='py38',
                      framework_version='1.9',
                      instance_count=1,
                      instance_type='ml.m5.xlarge',
                      max_run=60 * 30,
                      container_log_level=logging.INFO)

    # Adopted from https://github.com/aws/amazon-sagemaker-examples/blob/main/hyperparameter_tuning/mxnet_mnist/hpo_mxnet_mnist.ipynb

    hyperparameter_ranges = {
        "optimizer": CategoricalParameter(["sgd", "Adam"]),
        "learning_rate": ContinuousParameter(0.01, 0.2),
        "num_epoch": IntegerParameter(10, 50),
    }

    objective_metric_name = "model-accuracy"
    metric_definitions = [{"Name": "model-accuracy", "Regex": "model-accuracy=([0-9\\.]+)"}]

    tuner = HyperparameterTuner(
        estimator,
        objective_metric_name,
        hyperparameter_ranges,
        metric_definitions,
        max_jobs=3,
        max_parallel_jobs=2,
    )

    tuner.fit()

    best_training_job = tuner.best_training_job()

    assert best_training_job is not None


def test_hpo_ssh(request):
    estimator = MXNet(entry_point=os.path.basename('source_dir/training/train.py'),
                      source_dir='source_dir/training/',
                      dependencies=[SSHEstimatorWrapper.dependency_dir()],
                      role=request.config.getini('sagemaker_role'),
                      py_version='py38',
                      framework_version='1.9',
                      instance_count=1,
                      instance_type='ml.m5.xlarge',
                      max_run=60 * 30,
                      container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=60)

    hyperparameter_ranges = {
        "optimizer": CategoricalParameter(["sgd", "Adam"]),
        "learning_rate": ContinuousParameter(0.01, 0.2),
        "num_epoch": IntegerParameter(10, 50),
    }

    objective_metric_name = "model-accuracy"
    metric_definitions = [{"Name": "model-accuracy", "Regex": "model-accuracy=([0-9\\.]+)"}]

    tuner = HyperparameterTuner(
        estimator,
        objective_metric_name,
        hyperparameter_ranges,
        metric_definitions,
        base_tuning_job_name='ssh-hpo-mxnet',
        max_jobs=3,
        max_parallel_jobs=2,
    )

    tuner.fit(wait=False)

    with pytest.raises(AssertionError):
        # Shouldn't be able to get instance ids without calling estimator.fit() first
        _ = ssh_wrapper.get_instance_ids(retry=0)

    time.sleep(15)  # allow training jobs to start

    analytics = tuner.analytics()
    training_jobs = analytics.training_job_summaries()
    training_job_name = training_jobs[0]['TrainingJobName']

    instance_ids = SSMManager().get_training_instance_ids(training_job_name, 300)
    assert len(instance_ids) == 1

    instance_ids = SSHLog().get_training_ssm_instance_ids(training_job_name, 300)
    assert len(instance_ids) == 1

    tuner.wait()

    best_training_job = tuner.best_training_job()
    assert best_training_job is not None
