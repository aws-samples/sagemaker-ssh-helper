#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.cdk_stack import CdkStack
from iam_ssm.iam_ssm_stack import IamSsmStack
from iam_ssm.iam_ssm_stack_tests import IamSsmStackTests
from iam_ssm.ssm_advanced_tier_stack import SsmAdvancedTierStack

app = cdk.App()
CdkStack(app, "CdkStack")
IamSsmStack(app, "SSH-IAM-SSM-Stack")
IamSsmStackTests(app, "SSH-IAM-SSM-Stack-Tests")
SsmAdvancedTierStack(app, "SSM-Advanced-Tier-Stack")

app.synth()
