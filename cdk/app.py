#!/usr/bin/env python3
import aws_cdk as cdk

from cdk.cdk_stack import CdkStack
from iam_ssm.iam_ssm_stack import IamSsmStack
from iam_ssm.ssm_advanced_tier_stack import SsmAdvancedTierStack

app = cdk.App()
CdkStack(app, "CdkStack")
IamSsmStack(app, "SSH-IAM-SSM-Stack")
SsmAdvancedTierStack(app, "SSM-Advanced-Tier-Stack")

app.synth()
