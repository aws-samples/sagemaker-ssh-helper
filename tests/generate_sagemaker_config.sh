#!/bin/bash

mkdir -p /root/.config/sagemaker

cat > /root/.config/sagemaker/config.yaml <<EOF
SchemaVersion: '1.0'
SageMaker:
  TrainingJob:
    RoleArn: '$SAGEMAKER_ROLE'
  Model:
    ExecutionRoleArn: '$SAGEMAKER_ROLE'
  ProcessingJob:
    RoleArn: '$SAGEMAKER_ROLE'
EOF
