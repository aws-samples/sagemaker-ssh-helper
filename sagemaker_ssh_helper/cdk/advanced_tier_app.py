#!/usr/bin/env python3
import aws_cdk as cdk

from sagemaker_ssh_helper.cdk.iam_ssm.ssm_advanced_tier_stack import SsmAdvancedTierStack

app = cdk.App()
SsmAdvancedTierStack(app, "SSM-Advanced-Tier-Stack")

app.synth()
