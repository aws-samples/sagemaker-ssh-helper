import logging
import os
import subprocess
import time
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pytest
import sagemaker
from sagemaker import Predictor, Model
from sagemaker.deserializers import CSVDeserializer, JSONDeserializer
from sagemaker.djl_inference import DJLModel, DJLPredictor
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
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
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

        ssh_wrapper.start_ssm_connection_and_continue(12022, 60)

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

        ssh_wrapper.start_ssm_connection_and_continue(12022, 60)

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
        ssh_wrapper.start_ssm_connection_and_continue(13022, 60)

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
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_sklearn():
    logging.info("Starting training")

    from sagemaker.sklearn import SKLearn
    estimator = SKLearn(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        py_version='py3',
                        framework_version='1.0-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


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
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
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
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_estimator_ssh_byoc():
    logging.info("Building BYOC docker image")
    subprocess.check_call("sm-docker build . --file byoc/Dockerfile --repo byoc-ssh:latest".split(' '))

    logging.info("Starting training")

    import boto3
    account_id = boto3.client('sts').get_caller_identity().get('Account')

    from sagemaker.estimator import Estimator

    estimator = Estimator(image_uri=f"{account_id}.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh:latest",
                          instance_count=1,
                          instance_type='ml.m5.xlarge',
                          max_run=int(timedelta(minutes=15).total_seconds()),
                          keep_alive_period_in_seconds=1800,
                          container_log_level=logging.INFO)

    sagemaker_session = sagemaker.Session()
    training_input = sagemaker_session.upload_data(path='byoc/train_data',
                                                   bucket=sagemaker_session.default_bucket(),
                                                   key_prefix='byoc/train_data')

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit({'training': training_input}, wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
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
        ssh_model_wrapper.start_ssm_connection_and_continue(12022, 60)

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
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection PyCompatibility
@pytest.mark.manual("Not working yet")
def test_djl_inference_ssh():
    model = DJLModel(
        "EleutherAI/gpt-j-6B",  # FIXME: unused. Remove duplicate with inference_djl.py
        role=sagemaker.Session().sagemaker_config['SageMaker']['ProcessingJob']['RoleArn'],  # TODO: resolve
        data_type="fp16",       # FIXME: serving.properties uses fp32
        number_of_partitions=2,     # FIXME: unused? See serving.properties
        entry_point=(p := Path('source_dir/inference/inference_djl.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        env={
            'TENSOR_PARALLEL_DEGREE': str(2)
        },
        container_log_level=logging.INFO
    )

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('djl-inference-ssh')

    predictor: Optional[DJLPredictor] = None
    try:
        predictor = model.deploy(
            instance_type="ml.g5.12xlarge",
            endpoint_name=endpoint_name,
            wait=False)
        ssh_wrapper.start_ssm_connection_and_continue(12022, 30)

        # FIXME: ValidationException when calling the DescribeEndpoint operation: Could not find endpoint
        # assert ssh_wrapper.endpoint_is_online()

        result = predictor.predict("Test")
    finally:
        if predictor:
            # FIXME: cannot delete endpoint if it's not InService
            pass
            # predictor.delete_endpoint(delete_endpoint_config=False)

    assert result == "42"
