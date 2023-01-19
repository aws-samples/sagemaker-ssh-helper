import logging

import sagemaker
from sagemaker.pytorch import PyTorch
from sagemaker.utils import name_from_base

from sagemaker_ssh_helper.wrapper import SSHModelWrapper, SSHTransformerWrapper
import test_util


def test_clean_batch_inference(request):
    # noinspection DuplicatedCode
    sagemaker_session = sagemaker.Session()
    bucket = sagemaker_session.default_bucket()

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

    transformer_input = sagemaker_session.upload_data(path='data/batch_transform/input',
                                                      bucket=bucket,
                                                      key_prefix='batch-transform/input')

    transformer_output = f"s3://{bucket}/batch-transform/output"

    transformer = model.transformer(instance_count=1,
                                    instance_type="ml.m5.xlarge",
                                    accept='text/csv',
                                    strategy='SingleRecord',
                                    assemble_with='Line',
                                    output_path=transformer_output)

    transformer.transform(data=transformer_input,
                          content_type='text/csv',
                          split_type='Line',
                          join_source="Input")

    test_util._cleanup_dir("./output", recreate=True)
    sagemaker_session.download_data(path='output', bucket=bucket,
                                    key_prefix='batch-transform/output')


def test_batch_ssh(request):
    # noinspection DuplicatedCode
    sagemaker_session = sagemaker.Session()
    bucket = sagemaker_session.default_bucket()

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

    transformer_input = sagemaker_session.upload_data(path='data/batch_transform/input',
                                                      bucket=bucket,
                                                      key_prefix='batch-transform/input')

    transformer_output = f"s3://{bucket}/batch-transform/output"

    ssh_model_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=3600)

    transformer = model.transformer(instance_count=1,
                                    instance_type="ml.m5.xlarge",
                                    accept='text/csv',
                                    strategy='SingleRecord',
                                    assemble_with='Line',
                                    output_path=transformer_output)

    ssh_transformer_wrapper = SSHTransformerWrapper.create(transformer, ssh_model_wrapper)

    transform_job_name = name_from_base('ssh-batch-transform')

    transformer.transform(data=transformer_input,
                          job_name=transform_job_name,
                          content_type='text/csv',
                          split_type='Line',
                          join_source="Input",
                          wait=False)

    ssh_transformer_wrapper.start_ssm_connection_and_continue(16022, 90)
    ssh_transformer_wrapper.wait_transform_job()

    test_util._cleanup_dir("./output", recreate=True)
    sagemaker_session.download_data(path='output', bucket=bucket,
                                    key_prefix='batch-transform/output')
