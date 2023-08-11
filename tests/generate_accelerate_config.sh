#!/bin/bash

mkdir -p /root/.cache/huggingface/accelerate/

cat > /root/.cache/huggingface/accelerate/default_config.yaml <<EOF
base_job_name: accelerate-sagemaker-1
compute_environment: AMAZON_SAGEMAKER
distributed_type: 'NO'
ec2_instance_type: ml.p3.2xlarge
gpu_ids: all
iam_role_name: $SAGEMAKER_ROLE
mixed_precision: 'no'
num_machines: 1
profile: default
py_version: py38
pytorch_version: 1.10.2
region: eu-west-1
transformers_version: 4.17.0
use_cpu: false
EOF
