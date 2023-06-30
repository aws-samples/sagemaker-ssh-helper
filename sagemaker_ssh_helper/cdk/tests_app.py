#!/usr/bin/env python3
import aws_cdk as cdk

from sagemaker_ssh_helper.cdk.iam_ssm.iam_ssm_stack_tests import IamSsmStackTests

app = cdk.App()
IamSsmStackTests(app, "SSH-IAM-SSM-Stack-Tests")

app.synth()
