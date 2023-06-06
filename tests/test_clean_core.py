import logging
import os
from datetime import timedelta
from typing import Optional

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
                        max_run=int(timedelta(minutes=15).total_seconds()),
                        keep_alive_period_in_seconds=1800,
                        container_log_level=logging.INFO)
    estimator.fit()

    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


# noinspection DuplicatedCode
def test_clean_inference():
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

    predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_mms(instance_type):
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

    model_1 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean/')

    _ = model_1.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_1 = model_1.repacked_model_data

    # MUST have the same entry point file name as for the model_1
    model_2 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean_model2/')

    _ = model_2.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_2 = model_2.repacked_model_data

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

    predictor: Optional[Predictor] = None
    try:
        predictor = mdm.deploy(
            initial_instance_count=1,
            instance_type='ml.m5.xlarge',
            endpoint_name=endpoint_name,
            wait=True
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

    finally:
        if predictor:
            predictor.delete_endpoint(delete_endpoint_config=False)


# noinspection DuplicatedCode
@pytest.mark.parametrize("instance_type", ["ml.m5.xlarge"])
def test_clean_inference_mms_without_model(instance_type):
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

    model_1 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean/')

    model_1_description = model_1.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_1 = model_1.repacked_model_data
    container_uri = model_1_description['Image']
    deploy_env = model_1_description['Environment']

    # MUST have the same entry point file name as for the model_1
    model_2 = estimator.create_model(entry_point='inference_clean.py',
                                     source_dir='source_dir/inference_clean_model2/')

    _ = model_2.prepare_container_def(instance_type='ml.m5.xlarge')
    repacked_model_data_2 = model_2.repacked_model_data

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm_name = name_from_base('model-mms')

    mdm = MultiDataModel(
        name=mdm_name,
        model_data_prefix=model_data_prefix,
        image_uri=container_uri,
        # entry_point=model_1.entry_point,  # NOTE: entry point ignored
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
        predictor.delete_endpoint(delete_endpoint_config=False)
