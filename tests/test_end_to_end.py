import os
import queue
import socket
import threading
import time

import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

import boto3
import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorch, PyTorchProcessor, PyTorchPredictor
from sagemaker.serializers import JSONSerializer
from sagemaker.spark import PySparkProcessor
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper, SSHMultiModelWrapper, SSHProcessorWrapper
from test_util import _create_bucket_if_doesnt_exist

logger = logging.getLogger('sagemaker-ssh-helper')


# noinspection DuplicatedCode,PyCompatibility
def test_train_e2e():
    estimator = PyTorch(
        entry_point=(p := Path('source_dir/training/train.py')).name,
        source_dir=str(p.parents[0]),
        dependencies=[SSHEstimatorWrapper.dependency_dir()],  # <--NEW
        # (alternatively, add sagemaker_ssh_helper into requirements.txt
        # inside source dir) --
        base_job_name='train-e2e',
        framework_version='1.9.1',
        py_version='py38',
        instance_count=1,
        instance_type='ml.m5.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=1800,
        container_log_level=logging.INFO
    )

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)

    estimator.fit(wait=False)

    ssh_wrapper.start_ssm_connection_and_continue(11022)

    ssh_wrapper.wait_training_job()

    assert estimator.model_data.find("model.tar.gz") != -1


def test_train_pycharm_debug_e2e():
    estimator = PyTorch(entry_point='train_debug.py',
                        source_dir='source_dir/training_debug/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='train-pycharm-debug-e2e',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
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
            logger.info("pycharm_debug_server_mock: Waiting for the connection from remote host")
            server_sock.accept()
        except socket.timeout:
            logger.error("pycharm_debug_server_mock: Listen socket timeout")
            bucket.put(1)
            return

        logger.info("Got connection from the remote pydevd_pycharm on port 12345")
        server_sock.close()

        bucket.put(0)

    server_thread = threading.Thread(target=pycharm_debug_server_mock)
    server_thread.start()

    time.sleep(2)  # wait a little to get server thread started

    ssm_proxy = ssh_wrapper.start_ssm_connection(
        11022, timeout_in_sec=600,
        extra_args="-R localhost:12345:localhost:12345"
    )

    logger.info("Waiting for pydevd to connect")
    server_thread.join()

    ssm_proxy.disconnect()

    result = bucket.get(block=False)
    assert result == 0, "Socket timeout, remote job didn't connect to PyCharm Debug Server mock. " \
                        "Check the remote logs: " + ssh_wrapper.get_cloudwatch_url()
    assert bucket.qsize() == 0


def test_train_placeholder():
    estimator = PyTorch(entry_point='train_placeholder.py',
                        source_dir='source_dir/training_placeholder/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

    estimator.fit(wait=False)

    proxy = ssh_wrapper.start_ssm_connection(11022, 60)

    # Do something on the remote node...

    proxy.disconnect()

    ssh_wrapper.stop_training_job()


# noinspection DuplicatedCode
def test_debugger_stop_gpu(request):
    sns_notification_topic_arn = request.config.getini('sns_notification_topic_arn')

    from sagemaker.debugger import ProfilerRule, rule_configs, ProfilerConfig

    profiler_config = ProfilerConfig(
        system_monitor_interval_millis=100,  # grab metrics 10 times per second
    )
    rules = [
        ProfilerRule.sagemaker(rule_configs.LowGPUUtilization(
            scan_interval_us=60 * 1000 * 1000,  # scan every minute
            patience=2,  # skip the first 2 minutes
            threshold_p95=50,  # GPU should be at least 50% utilized, 95% of the time
            threshold_p5=0,  # skip detecting accidental drops
            window=1200,  # take the last 1200 readings, i.e., the last 2 minutes
        )),
    ]

    estimator = PyTorch(
        entry_point=os.path.basename('source_dir/training_placeholder/train_placeholder.py'),
        source_dir='source_dir/training_placeholder/',
        dependencies=[SSHEstimatorWrapper.dependency_dir()],
        base_job_name='ssh-training-low-gpu',
        framework_version='1.9.1',
        py_version='py38',
        instance_count=1,
        instance_type='ml.g4dn.xlarge',
        max_run=int(timedelta(minutes=15).total_seconds()),
        keep_alive_period_in_seconds=int(timedelta(minutes=30).total_seconds()),
        container_log_level=logging.INFO,
        profiler_config=profiler_config,
        rules=rules
    )

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

    estimator.fit(wait=False)

    status = ssh_wrapper.wait_training_job_with_status()
    assert status == 'Completed', 'The job should not be stopped by max_run limit'

    from sagemaker_ssh_helper.cdk.low_gpu import low_gpu_lambda
    f"""
    The notification had to be triggered by {low_gpu_lambda.handler}.
    """
    topic_name = sns_notification_topic_arn.split(':')[-1]
    metrics_count = 0
    for i in range(1, 10):
        metrics_count = SSHLog().count_sns_notifications(topic_name, timedelta(minutes=15))
        logging.info(f"Recent SNS notifications received: {metrics_count}")
        if metrics_count > 0:
            break
        time.sleep(30)  # wait for SNS metrics to populate
    assert metrics_count > 0, 'SNS notification had to be triggered by Low GPU Lambda'


# noinspection DuplicatedCode
def test_inference_e2e():
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model = estimator.create_model(
        entry_point='inference_ssh.py',
        source_dir='source_dir/inference/',
        dependencies=[SSHModelWrapper.dependency_dir()]  # <--NEW
        # (alternatively, add sagemaker_ssh_helper into requirements.txt
        # inside source dir) --
    )

    ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)

    endpoint_name = name_from_base('ssh-inference')

    predictor: Predictor = model.deploy(
        initial_instance_count=1,
        instance_type='ml.m5.xlarge',
        endpoint_name=endpoint_name,
        wait=True
    )

    try:
        ssh_wrapper.start_ssm_connection_and_continue(12022)

        time.sleep(60)  # Cold start latency to prevent prediction time out

        predictor.serializer = JSONSerializer()
        predictor.deserializer = JSONDeserializer()

        predicted_value = predictor.predict(data=[1])
        assert predicted_value == [43]

    finally:
        predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_inference_e2e_mms(instance_type):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        framework_version='1.9.1',  # Works for: 1.12, 1.11, 1.10 (1.10.2), 1.9 (1.9.1) - py38.
                        py_version='py38',  # Doesn't work for: 1.10.0, 1.9.0 - py38, 1.8, 1.7, 1.6 - py36.
                        instance_count=1,
                        instance_type=instance_type,
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference_ssh.py',
                                     source_dir='source_dir/inference/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    _ = model_1.prepare_container_def(instance_type=instance_type)
    repacked_model_data_1 = model_1.repacked_model_data

    model_2 = estimator.create_model(entry_point='inference_ssh.py',  # file name should be the same as for model_1
                                     source_dir='source_dir/inference_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    _ = model_2.prepare_container_def(instance_type=instance_type)
    repacked_model_data_2 = model_2.repacked_model_data

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

    predictor: Optional[Predictor] = None
    try:
        predictor = mdm.deploy(
            initial_instance_count=1,
            instance_type=instance_type,
            endpoint_name=endpoint_name
        )

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
        ssh_wrapper.start_ssm_connection_and_continue(13022)

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_inference_e2e_mms_without_model(instance_type):
    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type=instance_type,
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    model_1 = estimator.create_model(entry_point='inference_ssh.py',
                                     source_dir='source_dir/inference/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    model_1_description = model_1.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_1 = model_1.repacked_model_data
    container_uri = model_1_description['Image']
    deploy_env = model_1_description['Environment']

    model_2 = estimator.create_model(entry_point='inference_ssh.py',
                                     source_dir='source_dir/inference_model2/',
                                     dependencies=[SSHModelWrapper.dependency_dir()])

    _ = model_2.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_2 = model_2.repacked_model_data

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('ssh-model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        role=model_1.role,
        image_uri=container_uri,
        # entry_point=model_1.entry_point,  # NOTE: entry point ignored
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
        ssh_wrapper.start_ssm_connection_and_continue(13022)

    finally:
        predictor.delete_endpoint(delete_endpoint_config=False)


def test_processing_e2e():
    spark_processor = PySparkProcessor(
        base_job_name='ssh-spark-processing',
        framework_version="3.0",
        instance_count=1,
        instance_type="ml.m5.xlarge",
        max_runtime_in_seconds=int(timedelta(minutes=15).total_seconds())
    )

    ssh_wrapper = SSHProcessorWrapper.create(spark_processor, connection_wait_time_seconds=3600)

    spark_processor.run(
        submit_app="source_dir/processing/process.py",
        inputs=[ssh_wrapper.augmented_input()],
        logs=True,
        wait=False
    )

    ssh_wrapper.start_ssm_connection_and_continue(14022)

    ssh_wrapper.wait_processing_job()


def test_processing_framework_e2e():
    torch_processor = PyTorchProcessor(
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


def test_train_with_bucket_override():
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    custom_bucket_name = f'sagemaker-custom-bucket-{account_id}'

    bucket = _create_bucket_if_doesnt_exist('eu-west-1', custom_bucket_name)
    bucket.objects.all().delete()

    estimator = PyTorch(entry_point='train.py',
                        source_dir='source_dir/training/',
                        dependencies=[SSHEstimatorWrapper.dependency_dir()],
                        base_job_name='ssh-training',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)

    ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=300)

    estimator.fit(wait=False)

    os.environ["SSH_AUTHORIZED_KEYS_PATH"] = f's3://{custom_bucket_name}/ssh-keys-testing/'
    try:
        ssh_wrapper.start_ssm_connection_and_continue(11022)
        ssh_wrapper.wait_training_job()
        all_objects = bucket.objects.all()
        assert any([o.key == "ssh-keys-testing/sagemaker-ssh-gw.pub" for o in all_objects])
    finally:
        del os.environ["SSH_AUTHORIZED_KEYS_PATH"]
