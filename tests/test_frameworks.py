import logging
import os
import time

import pytest
import sagemaker
from sagemaker import Predictor, Model
from sagemaker.deserializers import CSVDeserializer, JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.serializers import CSVSerializer, JSONSerializer
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper, SSHMultiModelWrapper
import test_util


def test_clean_train_huggingface(request):
    logging.info("Starting training")

    from sagemaker.huggingface import HuggingFace
    estimator = HuggingFace(entry_point='train_clean.py',
                            source_dir='source_dir/training_clean/',
                            role=request.config.getini('sagemaker_role'),
                            pytorch_version='1.10',
                            transformers_version='4.17',
                            py_version='py38',
                            instance_count=1,
                            instance_type='ml.g4dn.xlarge',  # HF needs GPU
                            max_run=60 * 30,
                            keep_alive_period_in_seconds=1800,
                            container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_huggingface_ssh(request):
    logging.info("Starting training")

    from sagemaker.huggingface import HuggingFace
    estimator = HuggingFace(entry_point='train.py',
                            source_dir='source_dir/training/',
                            dependencies=[SSHEstimatorWrapper.dependency_dir()],
                            base_job_name='ssh-training-hf',
                            role=request.config.getini('sagemaker_role'),
                            pytorch_version='1.10',
                            transformers_version='4.17',
                            py_version='py38',
                            instance_count=1,
                            instance_type='ml.g4dn.xlarge',  # HF needs GPU
                            max_run=60 * 30,
                            keep_alive_period_in_seconds=1800,
                            container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_tensorflow(request):
    logging.info("Starting training")

    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_clean.py',
                           source_dir='source_dir/training_clean/',
                           role=request.config.getini('sagemaker_role'),
                           framework_version='2.9.2',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 30,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
def test_clean_inference_tensorflow(request):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           role=request.config.getini('sagemaker_role'),
                           framework_version='2.9.2',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 60 * 3,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    # Note: entry_point MUST be called inference.py, otherwise the default handler will be called
    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference_tf_clean/')

    endpoint_name = name_from_base('inference-tf')

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type='ml.m5.xlarge',
                                        endpoint_name=endpoint_name)

    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()

    predicted_value = predictor.predict(data=[1])
    assert predicted_value == [43]

    predictor.delete_endpoint()


# noinspection DuplicatedCode
@pytest.mark.manual("TF MME ignores inference.py")
# TODO: waiting for the fix in https://github.com/aws/deep-learning-containers/pull/2597
def test_clean_inference_tensorflow_mme(request):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           role=request.config.getini('sagemaker_role'),
                           framework_version='2.9.2',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 60 * 3,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    # Note: entry_point MUST be called inference.py, otherwise the default handler will be called
    model_1 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference_tf_clean/')

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)

    # NOTE: for TF model repacked_model_data is not updated
    # repacked_model_data_1 = model_1.repacked_model_data

    # re-fetch container and model data location from Container 1 of the model
    model_1_description = model_1.sagemaker_session.describe_model(model_1.name)
    repacked_model_data_1 = model_1_description['PrimaryContainer']['ModelDataUrl']
    container_uri = model_1_description['PrimaryContainer']['Image']
    deploy_env = model_1_description['PrimaryContainer']['Environment']

    temp_predictor.delete_endpoint()

    # Another model with different inference.py
    model_2 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference_tf_clean_model2/')

    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)

    model_2_description = model_2.sagemaker_session.describe_model(model_2.name)
    repacked_model_data_2 = model_2_description['PrimaryContainer']['ModelDataUrl']
    temp_predictor.delete_endpoint()

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

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
                                      endpoint_name=endpoint_name,
                                      wait=True)

    try:
        mdm.add_model(model_data_source=repacked_model_data_1, model_data_path='model_1.tar.gz')
        mdm.add_model(model_data_source=repacked_model_data_2, model_data_path='model_2.tar.gz')

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model='model_1.tar.gz')
        # Fails here because default handler produces {'error': 'JSON Value: [\n    1\n] Is not object'} .
        # Our inference.py prepares correct JSON, but ignored in MME.
        # Compare with 'test_clean_inference_tensorflow()' that works for a single-model endpoint.
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[1], target_model='model_2.tar.gz')
        assert predicted_value == [20043]

    finally:
        predictor.delete_endpoint()


# noinspection DuplicatedCode
def test_ssh_inference_tensorflow(request):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_clean.py',
                           source_dir='source_dir/training_clean/',
                           role=request.config.getini('sagemaker_role'),
                           framework_version='2.9.2',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 60 * 3,
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

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type='ml.m5.xlarge',
                                        endpoint_name=endpoint_name)

    try:
        ssh_wrapper.start_ssm_connection_and_continue(12022, 60)

        time.sleep(60)  # Cold start latency to prevent prediction time out

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1])
        assert predicted_value == [43]

    finally:
        predictor.delete_endpoint()


# noinspection DuplicatedCode
@pytest.mark.manual("TF MME ignores inference.py")
# TODO: waiting for the fix in https://github.com/aws/deep-learning-containers/pull/2597
def test_ssh_inference_tensorflow_mme(request):
    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train_tf_mme.py',
                           source_dir='source_dir/training/',
                           role=request.config.getini('sagemaker_role'),
                           framework_version='2.9.2',
                           py_version='py39',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 60 * 3,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference.py',    # FIXME: MUST be called only 'inference.py'?
                                     source_dir='source_dir/inference_tf/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)

    # NOTE: for TF model repacked_model_data is not updated
    # repacked_model_data_1 = model_1.repacked_model_data

    # re-fetch container and model data location from Container 1 of the model
    model_1_description = model_1.sagemaker_session.describe_model(model_1.name)
    repacked_model_data_1 = model_1_description['PrimaryContainer']['ModelDataUrl']
    container_uri = model_1_description['PrimaryContainer']['Image']
    deploy_env = model_1_description['PrimaryContainer']['Environment']

    temp_predictor.delete_endpoint()

    # Another model with different inference.py
    model_2 = estimator.create_model(entry_point='inference.py',    # FIXME: MUST have the same name as for the model_1?
                                     source_dir='source_dir/inference_tf_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)

    model_2_description = model_2.sagemaker_session.describe_model(model_2.name)
    repacked_model_data_2 = model_2_description['PrimaryContainer']['ModelDataUrl']
    temp_predictor.delete_endpoint()

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

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
                                      endpoint_name=endpoint_name,
                                      wait=True)

    try:
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
        predictor.delete_endpoint()


def test_train_tensorflow_ssh(request):
    logging.info("Starting training")

    from sagemaker.tensorflow import TensorFlow
    estimator = TensorFlow(entry_point='train.py',
                           source_dir='source_dir/training/',
                           dependencies=[SSHEstimatorWrapper.dependency_dir()],
                           base_job_name='ssh-training-tf',
                           role=request.config.getini('sagemaker_role'),
                           py_version='py39',
                           framework_version='2.9.2',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 30,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_sklearn(request):
    logging.info("Starting training")

    from sagemaker.sklearn import SKLearn
    estimator = SKLearn(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        py_version='py3',
                        framework_version='1.0-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 30,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_sklearn_ssh(request):
    logging.info("Starting training")

    from sagemaker.sklearn import SKLearn
    estimator = SKLearn(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training-sklearn',
                        role=request.config.getini('sagemaker_role'),
                        py_version='py3',
                        framework_version='1.0-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 30,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_clean_train_xgboost(request):
    logging.info("Starting training")

    from sagemaker.xgboost import XGBoost
    estimator = XGBoost(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.5-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 30,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_xgboost_ssh(request):
    logging.info("Starting training")

    from sagemaker.xgboost import XGBoost
    estimator = XGBoost(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training-sklearn',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.5-1',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 30,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_estimator_ssh(request):
    logging.info("Starting training")

    import boto3
    account_id = boto3.client('sts').get_caller_identity().get('Account')

    from sagemaker.estimator import Estimator

    role = request.config.getini('sagemaker_role')

    estimator = Estimator(image_uri=f"{account_id}.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh:latest",
                          role=role,
                          instance_count=1,
                          instance_type='ml.m5.xlarge',
                          max_run=60 * 30,
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
        predictor.delete_endpoint()


def test_train_mxnet_ssh(request):
    logging.info("Starting training")

    from sagemaker.mxnet import MXNet
    estimator = MXNet(entry_point=os.path.basename('source_dir/training/train.py'),
                      source_dir='source_dir/training/',
                      dependencies=[SSHEstimatorWrapper.dependency_dir()],
                      base_job_name='ssh-training-mxnet',
                      role=request.config.getini('sagemaker_role'),
                      py_version='py38',
                      framework_version='1.9',
                      instance_count=1,
                      instance_type='ml.m5.xlarge',
                      max_run=60 * 30,
                      keep_alive_period_in_seconds=1800,
                      container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)
    estimator.fit(wait=False)
    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
    ssh_wrapper.wait_training_job()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1
