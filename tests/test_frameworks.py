import logging
import sagemaker

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper
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
                           py_version='py39',
                           framework_version='2.9.2',
                           instance_count=1,
                           instance_type='ml.m5.xlarge',
                           max_run=60 * 30,
                           keep_alive_period_in_seconds=1800,
                           container_log_level=logging.INFO)

    estimator.fit()
    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


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
    estimator = Estimator(image_uri=f"{account_id}.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh:latest",
                          role=request.config.getini('sagemaker_role'),
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

    # TODO: test inference with payload.csv

    assert estimator.model_data.find("model.tar.gz") != -1

    test_util._cleanup_dir("./output")

    sagemaker_session.download_data(path='output', bucket=sagemaker_session.default_bucket(),
                                    key_prefix=estimator.latest_training_job.name + '/output')
