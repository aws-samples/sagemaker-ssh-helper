import os
import queue
import socket
import threading
import time

import logging

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorch, PyTorchProcessor, PyTorchPredictor
from sagemaker.serializers import JSONSerializer
from sagemaker.spark import PySparkProcessor
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper, SSHMultiModelWrapper, SSHProcessorWrapper
from test_util import _create_bucket_if_doesnt_exist

logger = logging.getLogger('sagemaker-ssh-helper')


def test_train_e2e(request):
    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    ssh_wrapper.start_ssm_connection_and_continue(11022, 60)

    ssh_wrapper.wait_training_job()

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_pycharm_debug_e2e(request):
    estimator = PyTorch(entry_point='train_debug.py',
                        source_dir='source_dir/training_debug/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 15,  # 15 minutes
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    bucket = queue.Queue()

    def pycharm_debug_server_mock():
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('127.0.0.1', 12345))

        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.settimeout(600)  # 10 min timeout

        server_sock.listen(0)
        try:
            logger.info("Waiting for the connection from remote host")
            server_sock.accept()
        except socket.timeout:
            logger.error("Listen socket timeout")
            bucket.put(1)
            return

        logger.info("Got connection from the remote pydevd_pycharm on port 12345")
        server_sock.close()

        bucket.put(0)

    server_thread = threading.Thread(target=pycharm_debug_server_mock)
    server_thread.start()

    time.sleep(2)  # wait a little to get server thread started

    ssm_proxy = ssh_wrapper.start_ssm_connection(11022, 60, "-R localhost:12345:localhost:12345")

    logger.info("Waiting for pydevd to connect")
    server_thread.join()

    ssm_proxy.disconnect()

    result = bucket.get(block=False)
    assert result == 0, "Listen socket timeout."
    assert bucket.qsize() == 0


def test_train_placeholder(request):
    estimator = PyTorch(entry_point='train_placeholder.py',
                        source_dir='source_dir/training_placeholder/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

    estimator.fit(wait=False)

    proxy = ssh_wrapper.start_ssm_connection(11022, 60)

    # Do something on the remote node...

    proxy.disconnect()

    ssh_wrapper.stop_training_job()


# noinspection DuplicatedCode
def test_inference_e2e(request):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference/',
                                   dependencies=[SSHModelWrapper.dependency_dir()])

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference')

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type='ml.m5.xlarge',
                                        endpoint_name=endpoint_name,
                                        wait=True)

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
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_inference_e2e_mms(request, instance_type):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',  # Works for: 1.12, 1.11, 1.10 (1.10.2), 1.9 (1.9.1) - py38.
                        py_version='py38',  # Doesn't work for: 1.10.0, 1.9.0 - py38, 1.8, 1.7, 1.6 - py36.
                        instance_count=1,
                        instance_type=instance_type,
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type=instance_type,
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_1 = model_1.repacked_model_data
    temp_predictor.delete_endpoint()

    model_2 = estimator.create_model(entry_point='inference.py',  # file name should be the same as for model_1
                                     source_dir='source_dir/inference_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type=instance_type,
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_2 = model_2.repacked_model_data
    temp_predictor.delete_endpoint()

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('ssh-model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        model=model_1
    )

    # noinspection DuplicatedCode
    ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type=instance_type,
                                      endpoint_name=endpoint_name,
                                      wait=True)

    try:
        # Note: we need a repacked model data here, not an estimator data
        mdm.add_model(model_data_source=repacked_model_data_1, model_data_path='model_1.tar.gz')
        mdm.add_model(model_data_source=repacked_model_data_2, model_data_path='model_2.tar.gz')

        assert mdm.list_models()

        # noinspection DuplicatedCode
        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model="model_1.tar.gz")
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[1], target_model="model_2.tar.gz")
        assert predicted_value == [20043]

        # Note: in MME the models are lazy loaded, so SSH helper will start upon the first prediction request
        ssh_wrapper.start_ssm_connection_and_continue(13022, 60)

    finally:
        predictor.delete_endpoint()


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_inference_e2e_mms_without_model(request, instance_type):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type=instance_type,
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type=instance_type,
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_1 = model_1.repacked_model_data
    temp_predictor.delete_endpoint()

    # But we still don't have access to the deployed container URI from Model object, so still need to use boto3.
    # Re-fetch container and model data location from Container 1 of the model:
    model_1_description = model_1.sagemaker_session.describe_model(model_1.name)
    container_uri = model_1_description['PrimaryContainer']['Image']
    # Also re-fetch deploy environment:
    deploy_env = model_1_description['PrimaryContainer']['Environment']

    model_2 = estimator.create_model(entry_point='inference.py',
                                     source_dir='source_dir/inference_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type=instance_type,
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_2 = model_2.repacked_model_data
    temp_predictor.delete_endpoint()

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('ssh-model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        role=model_1.role,
        image_uri=container_uri,
        env=deploy_env,  # will copy 'SAGEMAKER_PROGRAM' env variable with entry point file name
        predictor_cls=PyTorchPredictor
    )

    # noinspection DuplicatedCode
    ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type=instance_type,
                                      endpoint_name=endpoint_name,
                                      wait=True)

    try:
        # Note: we need a repacked model data here, not an estimator data
        mdm.add_model(model_data_source=repacked_model_data_1, model_data_path='model_1.tar.gz')
        mdm.add_model(model_data_source=repacked_model_data_2, model_data_path='model_2.tar.gz')

        assert mdm.list_models()

        # noinspection DuplicatedCode
        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model="model_1.tar.gz")
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[1], target_model="model_2.tar.gz")
        assert predicted_value == [20043]

        # Note: in MME the models are lazy loaded, so SSH helper will start upon the first prediction request
        ssh_wrapper.start_ssm_connection_and_continue(13022, 60)

    finally:
        predictor.delete_endpoint()


def test_processing_e2e(request):
    spark_processor = PySparkProcessor(
        base_job_name='ssh-spark-processing',
        framework_version="3.0",
        role=request.config.getini('sagemaker_role'),
        instance_count=1,
        instance_type="ml.m5.xlarge",
        max_runtime_in_seconds=60 * 60 * 3,
    )

    ssh_wrapper = SSHProcessorWrapper.create(spark_processor, connection_wait_time_seconds=3600)

    spark_processor.run(
        submit_app="source_dir/processing/process.py",
        inputs=[ssh_wrapper.augmented_input()],
        logs=True,
        wait=False
    )

    ssh_wrapper.start_ssm_connection_and_continue(14022, 60)

    ssh_wrapper.wait_processing_job()


def test_processing_framework_e2e(request):
    torch_processor = PyTorchProcessor(
        base_job_name='ssh-pytorch-processing',
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

    ssh_wrapper.start_ssm_connection_and_continue(15022, 60)

    ssh_wrapper.wait_processing_job()


def test_train_e2e_with_bucket_override(request):
    import boto3
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    custom_bucket_name = f'sagemaker-custom-bucket-{account_id}'

    bucket = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket.objects.all().delete()

    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=300)

    estimator.fit(wait=False)

    os.environ["SSH_AUTHORIZED_KEYS_PATH"] = f's3://{custom_bucket_name}/ssh-keys-testing/'
    try:
        ssh_wrapper.start_ssm_connection_and_continue(11022, 60)
        ssh_wrapper.wait_training_job()
        all_objects = bucket.objects.all()
        assert any([o.key == "ssh-keys-testing/sagemaker-ssh-gw.pub" for o in all_objects])
    finally:
        del os.environ["SSH_AUTHORIZED_KEYS_PATH"]
