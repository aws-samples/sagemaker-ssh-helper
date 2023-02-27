import logging

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.pytorch import PyTorch, PyTorchProcessor
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHProcessorWrapper, SSHModelWrapper


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


@pytest.mark.manual
def test_processing_framework_manual(request):
    torch_processor = PyTorchProcessor(
        base_job_name='ssh-pytorch-processing-manual',
        framework_version='1.9.1',
        py_version='py38',
        role=request.config.getini('sagemaker_role'),
        instance_count=1,
        instance_type="ml.m5.xlarge",
        max_runtime_in_seconds=60 * 60 * 3,
    )

    wait_time = 3600

    ssh_wrapper = SSHProcessorWrapper.create(torch_processor, connection_wait_time_seconds=wait_time)

    torch_processor.run(
        source_dir="source_dir/processing/",
        dependencies=[SSHProcessorWrapper.dependency_dir()],
        code="process_framework.py",
        logs=True,
        wait=False
    )

    instance_ids = ssh_wrapper.get_instance_ids(60)
    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")

    ssh_wrapper.wait_processing_job()


@pytest.mark.manual
def test_inference_manual(request):
    estimator = PyTorch.attach("pytorch-training-2023-02-21-23-58-16-252")

    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference/',
                                   dependencies=[SSHModelWrapper.dependency_dir()])

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-manual')

    _: Predictor = model.deploy(initial_instance_count=1,
                                instance_type='ml.m5.xlarge',
                                endpoint_name=endpoint_name,
                                wait=True)

    instance_ids = ssh_wrapper.get_instance_ids(60)
    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")

    ssh_wrapper.wait_for_endpoint()
