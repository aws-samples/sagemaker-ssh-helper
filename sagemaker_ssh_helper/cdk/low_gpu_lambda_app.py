#!/usr/bin/env python3
import aws_cdk as cdk

from sagemaker_ssh_helper.cdk.low_gpu.low_gpu_lambda_stack import LowGPULambdaStack

app = cdk.App()
LowGPULambdaStack(app, "Low-GPU-Lambda-Stack")

app.synth()
