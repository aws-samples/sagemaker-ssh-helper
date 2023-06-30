#!/usr/bin/env python3
import aws_cdk as cdk

from sagemaker_ssh_helper.cdk.iam_ssm.iam_ssm_stack import IamSsmStack

app = cdk.App()
IamSsmStack(app, "SSH-IAM-SSM-Stack")

app.synth()
