import logging
import os

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.djl_inference import DJLPredictor
from sagemaker.pytorch import PyTorch, PyTorchProcessor
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHProcessorWrapper, SSHModelWrapper


@pytest.mark.manual
def test_train_placeholder_manual():
    bucket = sagemaker.Session().default_bucket()
    checkpoints_prefix = f"s3://{bucket}/checkpoints/"

    estimator = PyTorch(
        entry_point=os.path.basename('source_dir/training_placeholder/train_placeholder.py'),
        source_dir='source_dir/training_placeholder/',
        dependencies=[SSHEstimatorWrapper.dependency_dir()],  # <--NEW
        # (alternatively, add sagemaker_ssh_helper into requirements.txt
        # inside source dir) --
        base_job_name='ssh-training-manual',
        framework_version='1.9.1',
        py_version='py38',
        instance_count=1,
        instance_type='ml.m5.xlarge',
        max_run=60 * 60 * 3,
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO,
        checkpoint_s3_uri=checkpoints_prefix
    )

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)  # <--NEW--

    estimator.fit(wait=False)

    instance_ids = ssh_wrapper.get_instance_ids(60)  # <--NEW--

    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")
    logging.info(f"To connect over SSH run: sm-local-ssh-training connect {ssh_wrapper.latest_training_job_name()}")

    ssh_wrapper.wait_training_job()


@pytest.mark.manual
def test_processing_framework_manual():
    torch_processor = PyTorchProcessor(
        base_job_name='ssh-pytorch-processing-manual',
        framework_version='1.9.1',
        py_version='py38',
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
def test_inference_manual():
    estimator = PyTorch.attach("pytorch-training-2023-02-21-23-58-16-252")

    model = estimator.create_model(entry_point='inference_ssh.py',
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


@pytest.mark.manual
def test_djl_inference():
    predictor = DJLPredictor("djl-inference-ssh-2023-05-15-16-26-57-895")
    data = {
        "inputs": [
            "Hello world!",
        ],
        "parameters": {
            "max_length": 200,
            "temperature": 0.1,
        },
    }
    result = predictor.predict(data)
    assert result == "42"


@pytest.mark.manual
def test_subprocess():
    import subprocess
    subprocess.check_call("uname -a".split(' '))
    logging.info("OK")
