#!/usr/bin/env python3
import aws_cdk as cdk

from sagemaker_ssh_helper.cdk.cdk.cdk_stack import CdkStack
from sagemaker_ssh_helper.cdk.iam_ssm.iam_ssm_stack import IamSsmStack
from sagemaker_ssh_helper.cdk.iam_ssm.iam_ssm_stack_tests import IamSsmStackTests
from sagemaker_ssh_helper.cdk.iam_ssm.ssm_advanced_tier_stack import SsmAdvancedTierStack

app = cdk.App()
CdkStack(app, "CdkStack")
IamSsmStack(app, "SSH-IAM-SSM-Stack")
IamSsmStackTests(app, "SSH-IAM-SSM-Stack-Tests")
SsmAdvancedTierStack(app, "SSM-Advanced-Tier-Stack")

app.synth()
