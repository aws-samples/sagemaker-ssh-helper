import logging

import pytest
import sagemaker
from sagemaker import Predictor
from sagemaker.deserializers import JSONDeserializer
from sagemaker.pytorch import PyTorch, PyTorchPredictor
from sagemaker.serializers import JSONSerializer
from sagemaker.utils import name_from_base


@pytest.mark.manual("Not working yet")
def test_clean_inference_from_registry(request):
    role = request.config.getini('sagemaker_role')

    # Training

    estimator = PyTorch(entry_point='train_clean.py',
                        source_dir='source_dir/training_clean/',
                        role=role,
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

    package: sagemaker.model.ModelPackage = model.register(content_types=['text/csv'],
                                                           response_types=['test/csv'],
                                                           model_package_name='inference-registry',
                                                           inference_instances=['ml.m5.xlarge'],
                                                           transform_instances=['ml.m5.xlarge'])

    sagemaker.Session().wait_for_model_package(package.name)
    model_package_arn = package.model_package_arn
    logging.info(f"Registered package: {model_package_arn}")

    # Inference

    model_package = sagemaker.model.ModelPackage(role=role, model_package_arn=model_package_arn)

    endpoint_name = name_from_base('inference-registry')

    # FIXME: replace with model.deploy to make it work
    model_package.deploy(initial_instance_count=1,
                         instance_type='ml.m5.xlarge',
                         endpoint_name=endpoint_name)

    # Note: when using model_package, deploy() returns None, need construct the predictor manually
    predictor: Predictor = PyTorchPredictor(endpoint_name)

    predictor.serializer = JSONSerializer()
    predictor.deserializer = JSONDeserializer()

    predicted_value = predictor.predict(data=[1])
    assert predicted_value == [43]

    predictor.delete_endpoint()
