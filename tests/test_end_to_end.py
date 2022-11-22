import socket
import threading
import time

import logging

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorch, PyTorchProcessor
from sagemaker.serializers import JSONSerializer
from sagemaker.spark import PySparkProcessor
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper, SSHMultiModelWrapper, SSHProcessorWrapper

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
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    def pycharm_debug_server_mock():
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('127.0.0.1', 12345))

        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.settimeout(600)  # 10 min timeout

        server_sock.listen(0)
        server_sock.accept()
        logger.info("Got connection from the remote pydevd_pycharm on port 12345")
        server_sock.close()

    server_thread = threading.Thread(target=pycharm_debug_server_mock)
    server_thread.start()

    time.sleep(2)  # wait a little to get server thread started

    ssh_wrapper.start_ssm_connection_and_continue(11022, 60, "-R localhost:12345:localhost:12345")  # 10 min to connect

    server_thread.join()  # waiting for pydevd to connect

    ssh_wrapper.stop_training_job()  # the training job most likely fail, because pydevd unable to talk to debug server


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

    p = ssh_wrapper.start_ssm_connection(11022, 60)
    p.terminate()

    ssh_wrapper.stop_training_job()


@pytest.mark.manual
def test_train_placeholder_manual(request):
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
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

    estimator.fit(wait=False)

    instance_ids = ssh_wrapper.get_instance_ids(60)
    logging.info(f"To connect over SSM run: aws ssm start-session --target {instance_ids[0]}")

    ssh_wrapper.wait_training_job()


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
        predictor.delete_model()
        predictor.delete_endpoint()


def test_inference_e2e_mms(request):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=request.config.getini('sagemaker_role'),
                        framework_version='1.9.1',  # Works for: 1.12, 1.11, 1.10 (1.10.2), 1.9 (1.9.1) - py38.
                        py_version='py38',          # Doesn't work for: 1.10.0, 1.9.0 - py38, 1.8, 1.7, 1.6 - py36.
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model = estimator.create_model(entry_point='inference.py',
                                   source_dir='source_dir/inference/',
                                   dependencies=[SSHModelWrapper.dependency_dir()])

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm = MultiDataModel(
        name=model.name,
        model_data_prefix=model_data_prefix,
        model=model
    )

    ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
                                      endpoint_name=endpoint_name,
                                      wait=True)

    try:
        for i in range(1, 10):
            model_name = f"model_{i}.tar.gz"
            # Note: we need a repacked model data here, not an estimator data
            # If inference script and training scripts are in the different source dirs,
            # MMS will fail to find an inference script inside the trained model, so we need a repacked model
            logger.info(f"Adding model {model_name} from repacked source {model.repacked_model_data} "
                        f"(trained model source: {model.model_data})")
            mdm.add_model(model_data_source=model.repacked_model_data, model_data_path=model_name)

        assert mdm.list_models()

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1], target_model="model_1.tar.gz")
        assert predicted_value == [43]
        predicted_value = predictor.predict(data=[2], target_model="model_2.tar.gz")
        assert predicted_value == [44]

        # Note: in MME the models are lazy loaded, so SSH helper will start upon the first prediction request
        ssh_wrapper.start_ssm_connection_and_continue(13022, 60)

    finally:
        predictor.delete_model()
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
