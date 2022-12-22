import logging

import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorch
from sagemaker.serializers import JSONSerializer
from sagemaker.utils import name_from_base


# noinspection DuplicatedCode
def test_clean_train_warm_pool(request):
    logging.info("Starting training")

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

    logging.info("Finished training")

    assert estimator.model_data.find("model.tar.gz") != -1


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

    predictor.delete_model()
    predictor.delete_endpoint()


def test_clean_inference_mms(request):
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

    bucket = sagemaker.Session().default_bucket()
    job_name = estimator.latest_training_job.name
    model_data_prefix = f"s3://{bucket}/{job_name}/mms/"

    mdm = MultiDataModel(
        name=model.name,
        model_data_prefix=model_data_prefix,
        model=model
    )

    endpoint_name = name_from_base('inference-mms')

    predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                      instance_type='ml.m5.xlarge',
                                      endpoint_name=endpoint_name,
                                      wait=True)

    models_count = 10

    for i in range(1, models_count):
        model_name = f"model_{i}.tar.gz"
        # Note: we need a repacked model data here, not an estimator data
        # If inference script and training scripts are in the different source dirs,
        # MMS will fail to find an inference script inside the trained model, so we need a repacked model
        logging.info(f"Adding model {model_name} from repacked source {model.repacked_model_data} "
                     f"(trained model source: {model.model_data})")
        mdm.add_model(model_data_source=model.repacked_model_data, model_data_path=model_name)

    # noinspection DuplicatedCode
    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()

    predicted_value = predictor.predict(data=[1], target_model="model_1.tar.gz")
    assert predicted_value == [43]
    predicted_value = predictor.predict(data=[2], target_model="model_2.tar.gz")
    assert predicted_value == [44]

    predictor.delete_model()
    predictor.delete_endpoint()
