from aws_cdk import Stack, Duration
import aws_cdk.aws_events as events
import aws_cdk.aws_events_targets as targets
from aws_cdk.aws_iam import Role, PolicyDocument, PolicyStatement, Effect, ServicePrincipal
from aws_cdk.aws_sns import Topic
from constructs import Construct

import aws_cdk.aws_lambda as lambda_


class LowGPULambdaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sns_notification_topic_arn = self.node.try_get_context("sns_notification_topic_arn")
        sns_topic = Topic.from_topic_arn(self, "SNSNotificationTopic", sns_notification_topic_arn)

        role = Role(
            self, "LowGPULambdaRole",
            assumed_by=ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "LowGPULambdaRolePolicy": PolicyDocument(statements=[
                    PolicyStatement(
                        effect=Effect.ALLOW,
                        actions=["sagemaker:DescribeTrainingJob"],
                        resources=["*"]
                    ),
                    PolicyStatement(
                        effect=Effect.ALLOW,
                        actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                        resources=["*"]
                    ),
                    PolicyStatement(
                        effect=Effect.ALLOW,
                        actions=["sns:Publish"],
                        resources=[sns_topic.topic_arn]
                    )
                ])})

        # noinspection PyTypeChecker
        runtime: lambda_.Runtime = lambda_.Runtime.PYTHON_3_8

        low_gpu_lambda = lambda_.Function(
            self, "LowGPULambda",
            runtime=runtime,
            code=lambda_.AssetCode("./venv-lambda/lib/python3.8/site-packages/"),
            handler="sagemaker_ssh_helper.cdk.low_gpu.low_gpu_lambda.handler",
            role=role,
            environment={
                "SNS_NOTIFICATION_TOPIC_ARN": sns_topic.topic_arn

            },
            timeout=Duration.seconds(60),
        )

        low_gpu_rule = events.Rule(
            self, "profiler-low-gpu-checker-rule",
            event_pattern=events.EventPattern(
                source=["aws.sagemaker"],
                detail_type=events.Match.exact_string("SageMaker Processing Job State Change")
            )
        )

        low_gpu_rule.add_target(
            targets.LambdaFunction(low_gpu_lambda, retry_attempts=1)
        )
