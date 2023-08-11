import logging
import subprocess
from datetime import timedelta

import boto3
import sagemaker
from sagemaker.pytorch import PyTorchProcessor


from sagemaker_ssh_helper.wrapper import SSHProcessorWrapper


# noinspection DuplicatedCode
def test_processing_different_region_clean():
    boto3_session = boto3.session.Session(region_name='eu-west-2')
    sagemaker_session = sagemaker.Session(boto_session=boto3_session)

    torch_processor = PyTorchProcessor(
        sagemaker_session=sagemaker_session,
        base_job_name='pytorch-processing',
        framework_version='1.9.1',
        py_version='py38',
        instance_count=1,
        instance_type="ml.m5.xlarge",
        max_runtime_in_seconds=int(timedelta(minutes=15).total_seconds()),
    )

    torch_processor.run(
        source_dir="source_dir/processing/",
        dependencies=[SSHProcessorWrapper.dependency_dir()],
        code="process_framework.py",
        logs=True,
        wait=True
    )


# noinspection DuplicatedCode
def test_processing_different_region_ssh():
    boto3_session = boto3.session.Session(region_name='eu-west-2')
    sagemaker_session = sagemaker.Session(boto_session=boto3_session)

    torch_processor = PyTorchProcessor(
        sagemaker_session=sagemaker_session,
        base_job_name='ssh-pytorch-processing',
        framework_version='1.9.1',
        py_version='py38',
        instance_count=1,
        instance_type="ml.m5.xlarge",
        max_runtime_in_seconds=int(timedelta(minutes=15).total_seconds())
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

    ssh_wrapper.start_ssm_connection_and_continue(15022)

    ssh_wrapper.wait_processing_job()


def test_caller_script():
    from sagemaker_ssh_helper.env import get_caller_script_name
    assert get_caller_script_name() == 'test_environment.py'
    assert get_caller_script_name(2) == 'python.py'


def test_aws_config():
    output = subprocess.check_output("aws configure list".split(" ")).decode("latin1")
    logging.info(f"AWS config:\n{output}")
    logging.info(sagemaker.Session().default_bucket())
