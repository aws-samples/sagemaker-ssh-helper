import logging
import os
from pathlib import Path

import pytest
import sagemaker.config
from sagemaker import Model

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper

logger = logging.getLogger('sagemaker-ssh-helper:test_model_repack')


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Not working yet")
def test_model_repacking_from_scratch():
    model = Model(
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        entry_point=(p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None  # FIXME: not working
    # FIXME: SAGEMAKER_SUBMIT_DIRECTORY = file://source_dir/inference_hf_accelerate instead of /opt/ml/model/code


def test_model_repacking_with_existing_model():
    model = Model(
        model_data="s3://sagemaker-eu-west-1-169264033083/data/acc_model.tar.gz",
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        entry_point=(p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Not working yet")
def test_model_repacking_default_entry_point_with_existing_model():
    model = Model(
        model_data="s3://sagemaker-eu-west-1-169264033083/data/acc_model.tar.gz",
        image_uri="763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116",
        role="arn:aws:iam::555555555555:role/service-role/AmazonSageMaker-ExecutionRole-Example",
        source_dir=str(Path('source_dir/inference_hf_accelerate/')),
        # entry_point is send in the DJL serving.properties file
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        sagemaker_session=sagemaker.Session(),  # FIXME: otherwise AttributeError: 'NoneType' object has no attribute 'config'
    )
    _ = model.prepare_container_def(instance_type='ml.m5.xlarge')
    logging.info("Model data: %s", model.repacked_model_data)
    assert model.repacked_model_data is not None  # FIXME: not working
    # FIXME: SAGEMAKER_SUBMIT_DIRECTORY = file://source_dir/inference_hf_accelerate instead of /opt/ml/model/code
