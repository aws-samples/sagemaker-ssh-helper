import os

from aws_cdk import Stack, Aws
from aws_cdk.aws_iam import Role, PolicyDocument, PolicyStatement, Effect, ServicePrincipal
from constructs import Construct

import aws_cdk.aws_lambda as lambda_
import aws_cdk.triggers as triggers


class SsmAdvancedTierStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open(os.path.join(os.path.dirname(__file__), "advanced_tier_lambda.py")) as lambda_path:
            code = lambda_path.read()

        role = Role(self, "SSMAdvancedTierLambdaRole",
                    assumed_by=ServicePrincipal("lambda.amazonaws.com"),
                    inline_policies={
                        "SSMAdvancedTierLambdaPolicy": PolicyDocument(statements=[
                            PolicyStatement(
                                effect=Effect.ALLOW,
                                actions=["ssm:UpdateServiceSetting"],
                                resources=[f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:servicesetting/ssm/managed-instance/activation-tier"]
                            )
                        ])})

        triggers.TriggerFunction(self, "SSMAdvancedTierTrigger",
                                 runtime=lambda_.Runtime.PYTHON_3_7,
                                 role=role,
                                 handler="index.handler",
                                 code=lambda_.Code.from_inline(code))
