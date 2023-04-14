import logging
import os

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorch, PyTorchPredictor
from sagemaker.serializers import JSONSerializer
from sagemaker.utils import name_from_base


# noinspection DuplicatedCode
def test_clean_train_warm_pool():
    logging.info("Starting training")

    estimator = PyTorch(entry_point=os.path.basename('source_dir/training_clean/train_clean.py'),
                        source_dir='source_dir/training_clean/',
                        framework_version='1.9.1',
                        py_version='py38',
                        instance_count=1,
                        instance_type='ml.m5.xlarge',
                        max_run=60 * 60 * 3,
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
def test_clean_inference(request):
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

    model = estimator.create_model(entry_point='inference_clean.py',
                                   source_dir='source_dir/inference_clean/')

    endpoint_name = name_from_base('inference')

    predictor: Predictor = model.deploy(initial_instance_count=1,
                                        instance_type='ml.m5.xlarge',
                                        endpoint_name=endpoint_name)

    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()

    predicted_value = predictor.predict(data=[1])
    assert predicted_value == [43]

    predictor.delete_endpoint()


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_mms(request, instance_type):
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

    model_1 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean/')

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_1 = model_1.repacked_model_data
    temp_predictor.delete_endpoint()

    # MUST have the same entry point file name as for the model_1
    model_2 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean_model2/')
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_2 = model_2.repacked_model_data
    temp_predictor.delete_endpoint()

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        model=model_1
    )

    endpoint_name = name_from_base('inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
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

    finally:
        predictor.delete_endpoint()


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_mms_without_model(request, instance_type):
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

    model_1 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean/')

    # we need a temp endpoint to produce 'repacked_model_data'
    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_1.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
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

    # MUST have the same entry point file name as for the model_1
    model_2 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean_model2/')

    temp_endpoint_name = name_from_base('temp-inference-mms')
    temp_predictor: Predictor = model_2.deploy(initial_instance_count=1,
                                               instance_type='ml.m5.xlarge',
                                               endpoint_name=temp_endpoint_name,
                                               wait=True)
    repacked_model_data_2 = model_2.repacked_model_data
    temp_predictor.delete_endpoint()

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        role=model_1.role,
        image_uri=container_uri,
        env=deploy_env,  # will copy 'SAGEMAKER_PROGRAM' env variable with entry point file name
        predictor_cls=PyTorchPredictor
    )

    endpoint_name = name_from_base('inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
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

    finally:
        predictor.delete_endpoint()
