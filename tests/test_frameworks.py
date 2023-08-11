import logging
import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pytest
import sagemaker
from botocore.exceptions import ClientError
from mock import mock
from sagemaker import Predictor, Model
from sagemaker.deserializers import CSVDeserializer, JSONDeserializer
from sagemaker.djl_inference import DJLPredictor, DeepSpeedModel
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.serializers import CSVSerializer, JSONSerializer
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper, SSHMultiModelWrapper
import test_util


def test_clean_train_huggingface():
    logging.info("Starting training")

    from sagemaker.huggingface import HuggingFace
    estimator = HuggingFace(entry_point='train_clean.py',
                            source_dir='source_dir/training_clean/',
                            pytorch_version='1.10',
                            transformers_version='4.17',
                            py_version='py38',
                            instance_count=1,
                            instance_type='ml.g4dn.xlarge',  # HF needs GPU
                            max_run=int(timedelta(minutes=15).total_seconds()),
                            keep_alive_period_in_seconds=1800,
                            container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_huggingface_ssh():
    logging.info("Starting training")

    from sagemaker.huggingface import HuggingFace
    estimator = HuggingFace(entry_point='train.py',
                            source_dir='source_dir/training/',
                            dependencies=[SSHEstimatorWrapper.dependency_dir()],
                            base_job_name='ssh-training-hf',
                            pytorch_version='1.10',
                            transformers_version='4.17',
                            py_version='py38',
                            instance_count=1,
                            instance_type='ml.g4dn.xlarge',  # HF needs GPU
                            max_run=int(timedelta(minutes=15).total_seconds()),
                            keep_alive_period_in_seconds=1800,
                            container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
def test_ssh_inference_hugging_face_pretrained_model():
    logging.info("Starting training")

    from sagemaker.huggingface import HuggingFace
    # noinspection PyCompatibility
    estimator = HuggingFace(
        entry_point=(p := Path('source_dir/training_clean/train_clean.py')).name,
        source_dir=str(p.parents[0]),
        pytorch_version='1.10',
        transformers_version='4.17',
        py_version='py38',
        instance_count=1,
        instance_type='ml.g4dn.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO
    )

    estimator.fit()
    logging.info("Finished training")

    logging.info("Starting repacking model")

    # noinspection PyCompatibility
    model = estimator.create_model(
        entry_point=(p := Path('source_dir/inference/inference_hf.py')).name,
        source_dir=str(p.parents[0])
    )

    model.prepare_container_def(instance_type='ml.g4dn.xlarge')
    repacked_model_data = model.repacked_model_data

    logging.info("Finished repacking model")

    logging.info("Starting deploying model")

    from sagemaker.huggingface import HuggingFaceModel

    model = HuggingFaceModel(
        model_data=repacked_model_data,
        entry_point=model.entry_point,  # TODO: does it repack the entry point? What if I also use source_dir?
        role=estimator.role,  # TODO: should take the default
        transformers_version='4.17.0',
        pytorch_version='1.10.2',
        py_version='py38',
        dependencies=[SSHModelWrapper.dependency_dir()],  # NOTE: model will be repacked again with dependencies
    )

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-hf-inference')

    predictor: Predictor = model.deploy(
        initial_instance_count=1,
        instance_type='ml.g4dn.xlarge',
        endpoint_name=endpoint_name,
        wait=True)

    logging.info("Finished deploying model")

    try:
        logging.info("Testing connection")

        ssh_wrapper.start_ssm_connection_and_continue(12022)

        time.sleep(60)  # Cold start latency to prevent prediction time out

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        logging.info("Testing prediction")

        predicted_value = predictor.predict(data=[1])
        assert predicted_value == [43]

        logging.info("Finished prediction")

    finally:
        predictor.delete_endpoint(delete_endpoint_config=False)

    logging.info("Finished testing")


def test_clean_train_tensorflow():
    logging.info("Starting training")

    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_clean.py',
                           source_dir='source_dir/training_clean/',
                           framework_version='2.11',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_tensorflow(instance_type):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           framework_version='2.11',
                           py_version='py39',
                           instance_count=1,
                           instance_type=instance_type,
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    # Note: entry_point MUST be called inference.py, otherwise the default handler will be called
    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference_tf_clean/')

    endpoint_name = name_from_base('inference-tf')

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type=instance_type,
                                        endpoint_name=endpoint_name)

    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()

    predicted_value = predictor.predict(data=[1])
    assert predicted_value == [43]

    predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_tensorflow_mme(instance_type):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           framework_version='2.11',
                           py_version='py39',
                           instance_count=1,
                           instance_type=instance_type,
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    # Note: entry_point MUST be called inference.py, otherwise the default handler will be called
    model_1 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference_tf_clean/')

    model_1_description = model_1.prepare_container_def(instance_type='ml.m5.xlarge')
    container_uri = model_1_description['Image']
    deploy_env = model_1_description['Environment']
    # repacked_model_data_1 = model_1.repacked_model_data  # TODO: doesn't work for TF
    repacked_model_data_1 = model_1_description['ModelDataUrl']

    # Another model with different inference.py
    model_2 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference_tf_clean_model2/')

    model_2_description = model_2.prepare_container_def(instance_type=instance_type)
    # repacked_model_data_2 = model_2.repacked_model_data
    repacked_model_data_2 = model_2_description['ModelDataUrl']

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('model-tf-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        image_uri=container_uri,
        role=model_1.role,
        env=deploy_env,
        predictor_cls=Predictor
    )

    endpoint_name = name_from_base('inference-tf-mms')

    predictor: Optional[Predictor] = None
    try:
        predictor = mdm.deploy(
            initial_instance_count=1,
            instance_type=instance_type,
            endpoint_name=endpoint_name
        )

        mdm.add_model(model_data_source=repacked_model_data_1, model_data_path='model_1.tar.gz')
        mdm.add_model(model_data_source=repacked_model_data_2, model_data_path='model_2.tar.gz')

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model='model_1.tar.gz')
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[1], target_model='model_2.tar.gz')
        assert predicted_value == [20043]

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_ssh_inference_tensorflow(instance_type):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           framework_version='2.11',
                           py_version='py39',
                           instance_count=1,
                           instance_type=instance_type,
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    # Note: entry_point MUST be called inference.py, otherwise the default handler will be called
    # https://github.com/aws/deep-learning-containers/blob/5123076f835853791a1671e8dce2e652c9f8a37a/tensorflow/inference/docker/build_artifacts/sagemaker/python_service.py#L45
    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference_tf/',
                                   dependencies=[SSHModelWrapper.dependency_dir()])

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-tf')

    predictor: Optional[Predictor] = None
    try:
        predictor = model.deploy(
            initial_instance_count=1,
            instance_type=instance_type,
            endpoint_name=endpoint_name
        )

        ssh_wrapper.start_ssm_connection_and_continue(12022)

        time.sleep(60)  # Cold start latency to prevent prediction time out

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1])
        assert predicted_value == [43]

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode,PyCompatibility
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_ssh_inference_tensorflow_mme_without_model(instance_type):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point=(p := Path('source_dir/training_clean/train_tf_clean.py')).name,
                           source_dir=str(p.parents[0]),
                           framework_version='2.11',
                           py_version='py39',
                           instance_count=1,
                           instance_type=instance_type,
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference.py',    # TODO: MUST be called only 'inference.py'?
                                     source_dir='source_dir/inference_tf/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    model_1_description = model_1.prepare_container_def(instance_type=instance_type)
    container_uri = model_1_description['Image']
    deploy_env = model_1_description['Environment']
    # repacked_model_data_1 = model_1.repacked_model_data  # TODO: doesn't work for TF
    repacked_model_data_1 = model_1_description['ModelDataUrl']

    # Another model with different inference.py
    model_2 = estimator.create_model(entry_point='inference.py',    # TODO: MUST have the same name as for the model_1?
                                     source_dir='source_dir/inference_tf_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    model_2_description = model_2.prepare_container_def(instance_type=instance_type)
    # repacked_model_data_2 = model_2.repacked_model_data
    repacked_model_data_2 = model_2_description['ModelDataUrl']

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('ssh-model-tf-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        image_uri=container_uri,
        role=model_1.role,
        env=deploy_env,
        predictor_cls=Predictor
    )

    ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-tf-mms')

    predictor: Optional[Predictor] = None
    try:
        predictor = mdm.deploy(
            initial_instance_count=1,
            instance_type=instance_type,
            endpoint_name=endpoint_name
        )

        mdm.add_model(model_data_source=repacked_model_data_1, model_data_path='model_1.tar.gz')
        mdm.add_model(model_data_source=repacked_model_data_2, model_data_path='model_2.tar.gz')

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model='model_1.tar.gz')
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[1], target_model='model_2.tar.gz')
        assert predicted_value == [20043]

        # Note: in MME the models are lazy loaded, so SSH helper will start upon the first prediction request
        ssh_wrapper.start_ssm_connection_and_continue(13022)

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


def test_train_tensorflow_ssh():
    logging.info("Starting training")

    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train.py',
                           source_dir='source_dir/training/',
                           dependencies=[SSHEstimatorWrapper.dependency_dir()],
                           base_job_name='ssh-training-tf',
                           py_version='py39',
                           framework_version='2.9.2',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=int(timedelta(minutes=15).total_seconds()),
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_sklearn():
    logging.info("Starting training")

    from sagemaker.sklearn import SKLearn
    estimator = SKLearn(
        entry_point=(p := Path('source_dir/training_clean/train_clean.py')).name,
        source_dir=str(p.parents[0]),
        py_version='py3',
        framework_version='1.0-1',
        instance_count=1,
        instance_type='ml.m5.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO
    )

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Temp issues with the dependencies in the container")
def test_train_sklearn_ssh():
    logging.info("Starting training")

    from sagemaker.sklearn import SKLearn
    estimator = SKLearn(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training-sklearn',
                        py_version='py3',
                        framework_version='1.0-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_xgboost():
    logging.info("Starting training")

    from sagemaker.xgboost import XGBoost
    estimator = XGBoost(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        framework_version='1.5-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Temp issues with the dependencies in the container")
def test_train_xgboost_ssh():
    logging.info("Starting training")

    from sagemaker.xgboost import XGBoost
    estimator = XGBoost(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training-xgboost',
                        framework_version='1.5-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
def test_train_estimator_ssh_byoc():
    logging.info("Building BYOC docker image")
    subprocess.check_call(
        "sm-docker build . --file tests/byoc/Dockerfile --repo byoc-ssh:latest".split(' '),
        cwd="../"
    )

    logging.info("Starting training")

    import boto3
    region = boto3.session.Session().region_name
    logging.info(f"Using region to fetch account ID from STS: {region}")
    account_id = boto3.client('sts', region_name=region).get_caller_identity().get('Account')

    from sagemaker.estimator import Estimator

    estimator = Estimator(
        image_uri=f"{account_id}.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh:latest",
        instance_count=1,
        instance_type='ml.m5.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO
    )

    sagemaker_session = sagemaker.Session()
    training_input = sagemaker_session.upload_data(path='byoc/train_data',
                                                   bucket=sagemaker_session.default_bucket(),
                                                   key_prefix='byoc/train_data')

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit({'training': training_input}, wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1

    test_util._cleanup_dir("./output")
    sagemaker_session.download_data(path='output', bucket=sagemaker_session.default_bucket(),
                                    key_prefix=estimator.latest_training_job.name + '/output')

    model: Model = estimator.create_model()

    ssh_model_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('byoc-ssh-inference')

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type='ml.m5.xlarge',
                                        endpoint_name=endpoint_name,
                                        wait=True)

    try:
        ssh_model_wrapper.start_ssm_connection_and_continue(12022)

        time.sleep(60)  # Cold start latency to prevent prediction time out

        predictor.serializer = CSVSerializer()
        predictor.deserializer = CSVDeserializer()

        predicted_value = predictor.predict(data=[
            [5.9, 3, 5.1, 1.8],
            [5.7, 2.8, 4.1, 1.3]
        ])
        assert predicted_value == [['virginica'], ['versicolor']]

    finally:
        predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
def test_train_internet_free_ssh(request):
    logging.info("Building BYOC docker image for Internet-free mode")
    subprocess.check_call(
        "sm-docker build . --file tests/byoc/Dockerfile.internet_free --repo byoc-ssh-no-internet:latest".split(' '),
        cwd="../"
    )

    logging.info("Starting training")
    import boto3
    region = boto3.session.Session().region_name
    logging.info(f"Using region to fetch account ID from STS: {region}")
    account_id = boto3.client('sts', region_name=region).get_caller_identity().get('Account')

    from sagemaker.estimator import Estimator

    vpc_only_subnet = request.config.getini('vpc_only_subnet')
    vpc_only_security_group = request.config.getini('vpc_only_security_group')

    estimator = Estimator(
        image_uri=f"{account_id}.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh-no-internet:latest",
        instance_count=1,
        instance_type='ml.m5.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO,
        subnets=[vpc_only_subnet],
        security_group_ids=[vpc_only_security_group]
    )

    sagemaker_session = sagemaker.Session()
    training_input = sagemaker_session.upload_data(path='byoc/train_data',
                                                   bucket=sagemaker_session.default_bucket(),
                                                   key_prefix='byoc/train_data')

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit({'training': training_input}, wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_mxnet_ssh():
    logging.info("Starting training")

    from sagemaker.mxnet import MXNet
    estimator = MXNet(entry_point=os.path.basename('source_dir/training/train.py'),
                      source_dir='source_dir/training/',
                      dependencies=[SSHEstimatorWrapper.dependency_dir()],
                      base_job_name='ssh-training-mxnet',
                      py_version='py38',
                      framework_version='1.9',
                      instance_count=1,
                      instance_type='ml.m5.xlarge',
                      max_run=int(timedelta(minutes=15).total_seconds()),
                      keep_alive_period_in_seconds=1800,
                      container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection PyCompatibility
def test_hf_djl_deepspeed_inference_ssh():
    """
    Based on https://github.com/aws/amazon-sagemaker-examples/blob/main/advanced_functionality/pytorch_deploy_large_GPT_model/GPT-J-6B-model-parallel-inference-DJL.ipynb  # noqa
    """
    model = DeepSpeedModel(
        "EleutherAI/gpt-j-6B",
        role=sagemaker.Session().sagemaker_config['SageMaker']['ProcessingJob']['RoleArn'],  # TODO: resolve
        tensor_parallel_degree=4,
        entry_point=(p := Path('source_dir/inference/inference_djl.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        container_log_level=logging.INFO
    )

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('djl-inference-ssh')

    predictor: Optional[DJLPredictor] = None
    try:
        predictor = model.deploy(
            instance_type="ml.g4dn.12xlarge",
            endpoint_name=endpoint_name,
            wait=False)
        ssh_wrapper.start_ssm_connection_and_continue(12022)

        description = sagemaker.Session().wait_for_endpoint(endpoint_name, 5)
        logging.info("Endpoint status: %s", str(description))
        assert ssh_wrapper.endpoint_is_online()

        result = predictor.predict("What is the answer to life, the universe, and everything? The answer: ")
        logging.info(f"GPT-J 6B prediction result: {result}")
        assert "What is the answer" in str(result) or "'generated_text': \"What is" in str(result)

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
def test_hf_djl_accelerate_clean():
    """
    Based on https://github.com/aws/amazon-sagemaker-examples/blob/main/inference/generativeai/llm-workshop/lab1-deploy-llm/intro_to_llm_deployment.ipynb  # noqa
    """
    hf_endpoint_name = sagemaker.utils.name_from_base("gptj-acc")
    image_uri = (
        f"763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116"
    )
    sagemaker_session = sagemaker.Session()

    role = sagemaker_session.sagemaker_config['SageMaker']['Model']['ExecutionRoleArn']

    # Tar source_dir/inference_hf_accelerate/ into /tmp/acc_model.tar.gz
    tmp_model = "/tmp/acc_model.tar.gz"  # nosec hardcoded_tmp_directory # safe in tests
    subprocess.run(
        ["/bin/tar", "-czf", tmp_model,
         "-C", str(Path('source_dir/inference_hf_accelerate_clean/')),
         "code/"],
        check=True
    )

    hf_s3_code_artifact = sagemaker_session.upload_data(tmp_model)  # nosec hardcoded_tmp_directory

    # NOTE: HuggingFaceAccelerateModel generates serving.properties with engine=Python (HF Accelerate)
    #  and don't need a pre-trained model
    model = Model(
        image_uri=image_uri,
        model_data=hf_s3_code_artifact,
        role=role,
    )
    model.deploy(
        initial_instance_count=1,
        instance_type="ml.g4dn.4xlarge",
        endpoint_name=hf_endpoint_name
    )
    predictor = sagemaker.Predictor(
        endpoint_name=hf_endpoint_name,
        sagemaker_session=sagemaker_session,
        serializer=JSONSerializer(),
        deserializer=JSONDeserializer(),
    )
    result = predictor.predict(
        {"inputs": "What is the answer to life, the universe, and everything? The answer: ",
         "parameters": {"max_length": 50, "temperature": 0.5}}
    )
    logging.info(f"GPT-J 6B prediction result: {result}")
    predictor.delete_endpoint(delete_endpoint_config=False)
    assert "What is the answer" in str(result)


# noinspection DuplicatedCode
def test_hf_djl_accelerate_ssh():
    """
    Based on https://github.com/aws/amazon-sagemaker-examples/blob/main/inference/generativeai/llm-workshop/lab1-deploy-llm/intro_to_llm_deployment.ipynb  # noqa
    """
    hf_endpoint_name = sagemaker.utils.name_from_base("ssh-gptj-acc")
    image_uri = (
        f"763104351884.dkr.ecr.eu-west-1.amazonaws.com/djl-inference:0.20.0-deepspeed0.7.5-cu116"
    )
    sagemaker_session = sagemaker.Session()

    role = sagemaker_session.sagemaker_config['SageMaker']['Model']['ExecutionRoleArn']

    # Tar source_dir/inference_hf_accelerate/ into /tmp/acc_model.tar.gz
    tmp_model = "/tmp/acc_model.tar.gz"  # nosec hardcoded_tmp_directory # safe in tests
    subprocess.run(
        ["/bin/tar", "-czf", tmp_model,
         "-C", str(Path('source_dir/inference_hf_accelerate_clean/')),
         "code/"],
        check=True
    )

    hf_s3_code_artifact = sagemaker_session.upload_data(tmp_model)

    # NOTE: HuggingFaceAccelerateModel generates serving.properties with engine=Python (HF Accelerate)
    #  and don't need a pre-trained model
    model = Model(
        model_data=hf_s3_code_artifact,
        image_uri=image_uri,
        role=role,
        # NOTE: entry_point is not used, because is set in serving.properties,
        #   but this is the required Model parameter now
        entry_point=(p := Path('source_dir/inference_hf_accelerate/inference_ssh.py')).name,
        source_dir=str(p.parents[0]),  # will override code/serving.properties with the new entry point
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
    )
    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)
    predictor: Optional[Predictor] = None
    try:
        predictor = model.deploy(
            initial_instance_count=1,
            instance_type="ml.g4dn.4xlarge",
            endpoint_name=hf_endpoint_name
        )
        assert ssh_wrapper.get_instance_ids()

        ssh_wrapper.start_ssm_connection_and_continue(12022)

        predictor = sagemaker.Predictor(
            endpoint_name=hf_endpoint_name,
            sagemaker_session=sagemaker_session,
            serializer=JSONSerializer(),
            deserializer=JSONDeserializer(),
        )
        result = predictor.predict(
            {"inputs": "What is the answer to life, the universe, and everything? The answer: ",
             "parameters": {"max_length": 50, "temperature": 0.5}}
        )
        logging.info(f"GPT-J 6B prediction result: {result}")
        assert "'generated_text': 'What is" in str(result) or "'generated_text': \"What is" in str(result)

    except Exception as e:
        if predictor:
            try:
                predictor.delete_endpoint(delete_endpoint_config=False)
            except ClientError as delete_e:
                logging.error(f"Test failed. Additionally, failed to cleanup: {delete_e.response['Error']['Message']}",
                              exc_info=e)
                raise
        raise
    if predictor:
        try:
            predictor.delete_endpoint(delete_endpoint_config=False)
        except ClientError as delete_e:
            logging.error(f"Failed to cleanup", exc_info=delete_e)
            raise


# noinspection DuplicatedCode
@mock.patch.object(sys, 'argv', ['launch', 'source_dir/training_clean/train_clean.py'])
def test_accelerate_training_clean():
    """
    See https://huggingface.co/docs/accelerate/usage_guides/sagemaker .

    Below code is equal to executing the following command:

    accelerate launch ./source_dir/training_clean/train_clean.py

    See: https://github.com/huggingface/accelerate/blob/main/src/accelerate/commands/launch.py#L787-L804
      and https://github.com/huggingface/accelerate/blob/main/src/accelerate/utils/launch.py#L383-L491 .

    """
    import accelerate.commands.launch as launch
    import accelerate.utils.launch as utils_launch
    parser = launch.launch_command_parser()
    args = parser.parse_args()
    args, sagemaker_config, mp_from_config_flag = launch._validate_launch_command(args)
    if args.module or args.no_python:
        raise ValueError(
            "SageMaker requires a python training script file and cannot be used with --module or --no_python"
        )

    args, sagemaker_inputs = utils_launch.prepare_sagemager_args_inputs(sagemaker_config, args)
    del os.environ['AWS_PROFILE']  # HF Accelerate forces AWS_PROFILE to be set, but we don't need it

    from sagemaker.huggingface import HuggingFace
    huggingface_estimator = HuggingFace(**args)
    huggingface_estimator.fit(inputs=sagemaker_inputs)

    logging.info(f"You can find your model data at: {huggingface_estimator.model_data}")


# noinspection DuplicatedCode
@mock.patch.object(sys, 'argv', ['launch', 'source_dir/training/train.py'])
def test_accelerate_training_ssh():
    import accelerate.commands.launch as launch
    import accelerate.utils.launch as utils_launch
    parser = launch.launch_command_parser()
    args = parser.parse_args()
    args, sagemaker_config, mp_from_config_flag = launch._validate_launch_command(args)
    if args.module or args.no_python:
        raise ValueError(
            "SageMaker requires a python training script file and cannot be used with --module or --no_python"
        )

    args, sagemaker_inputs = utils_launch.prepare_sagemager_args_inputs(sagemaker_config, args)
    del os.environ['AWS_PROFILE']  # HF Accelerate forces AWS_PROFILE to be set, but we don't need it

    from sagemaker.huggingface import HuggingFace
    args["dependencies"] = [SSHEstimatorWrapper.dependency_dir()]
    estimator = HuggingFace(**args)
    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(inputs=sagemaker_inputs, wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022)
    ssh_wrapper.wait_training_job()

    logging.info(f"You can find your model data at: {estimator.model_data}")
