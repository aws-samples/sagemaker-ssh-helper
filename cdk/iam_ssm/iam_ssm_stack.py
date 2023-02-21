import os

from aws_cdk import Stack, Aws, triggers
from aws_cdk.aws_iam import PolicyDocument, PolicyStatement, Effect, ManagedPolicy, Role, ServicePrincipal
from constructs import Construct

import aws_cdk.aws_lambda as lambda_


class IamSsmStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sagemaker_role_arn = self.node.try_get_context("sagemaker_role")
        sagemaker_role = Role.from_role_arn(self, "sagemaker_role", role_arn=sagemaker_role_arn)

        user_role_arn = self.node.try_get_context("user_role")
        user_role = Role.from_role_arn(self, "user_role", role_arn=user_role_arn)

        # noinspection PyUnusedLocal
        sagemaker_core_policy = \
            ManagedPolicy(self, "SSHSageMakerCorePolicy",
                          managed_policy_name="SSHSageMakerCorePolicy",
                          document=PolicyDocument(statements=[
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "iam:PassRole",
                                  ],
                                  resources=[sagemaker_role.role_arn],
                                  conditions={
                                      "StringEquals": {
                                          "iam:PassedToService": "sagemaker.amazonaws.com"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "s3:PutObject",
                                      "s3:GetObject",
                                      "s3:DeleteObject",
                                      "s3:CreateBucket",
                                      "s3:DeleteBucket",
                                      "s3:ListBucket"
                                  ],
                                  resources=[
                                      f"arn:{Aws.PARTITION}:s3:::*SageMaker*",
                                      f"arn:{Aws.PARTITION}:s3:::*Sagemaker*",
                                      f"arn:{Aws.PARTITION}:s3:::*sagemaker*",
                                  ],
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "logs:DescribeLogStreams",
                                      "logs:GetLogEvents",
                                  ],
                                  resources=[
                                      f"arn:{Aws.PARTITION}:logs:*:{Aws.ACCOUNT_ID}:log-group:/aws/sagemaker/*",
                                  ],
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "sagemaker:CreateTrainingJob",
                                      "sagemaker:CreateProcessingJob",
                                      "sagemaker:CreateModel",
                                      "sagemaker:CreateEndpointConfig",
                                      "sagemaker:CreateEndpoint",
                                      "sagemaker:CreateTransformJob",
                                      "sagemaker:DescribeTrainingJob",
                                      "sagemaker:DescribeProcessingJob",
                                      "sagemaker:DescribeModel",
                                      "sagemaker:DescribeEndpoint",
                                      "sagemaker:DescribeTransformJob",
                                      "sagemaker:DeleteEndpointConfig",
                                      "sagemaker:DeleteEndpoint",
                                      "sagemaker:InvokeEndpoint",
                                      "sagemaker:StopTrainingJob",
                                  ],
                                  resources=["*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "codebuild:CreateProject",
                                      "codebuild:DeleteProject",
                                      "codebuild:StartBuild",
                                      "codebuild:BatchGetBuilds",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:codebuild:*:{Aws.ACCOUNT_ID}:project/sagemaker-studio-image-build-*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "iam:PassRole",  # NOTE: need to add manually sts:AssumeRole to trust relationship
                                  ],
                                  resources=[user_role.role_arn],
                                  conditions={
                                      "StringEquals": {
                                          "iam:PassedToService": "codebuild.amazonaws.com"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ecr:CreateRepository",
                                      "ecr:DescribeRepositories",
                                      "ecr:BatchCheckLayerAvailability",
                                      "ecr:CompleteLayerUpload",
                                      "ecr:InitiateLayerUpload",
                                      "ecr:PutImage",
                                      "ecr:UploadLayerPart",
                                  ],
                                  resources=[
                                      f"arn:{Aws.PARTITION}:ecr:{Aws.REGION}:{Aws.ACCOUNT_ID}:repository/byoc-ssh"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ecr:GetAuthorizationToken",
                                  ],
                                  resources=["*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "logs:CreateLogStream",
                                      "logs:CreateLogGroup",
                                      "logs:GetLogEvents",
                                      "logs:PutLogEvents",
                                  ],
                                  resources=[
                                      f"arn:{Aws.PARTITION}:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/codebuild/sagemaker-studio-image-build-*:log-stream:*"]
                              ),
                          ]))

        # noinspection PyUnusedLocal
        ssh_client_policy = \
            ManagedPolicy(self, "SSHSageMakerClientPolicy",
                          managed_policy_name="SSHSageMakerClientPolicy",
                          document=PolicyDocument(statements=[
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:DescribeInstanceInformation",
                                      "ssm:ListTagsForResource",
                                  ],
                                  resources=["*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:DeregisterManagedInstance",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:managed-instance/mi-*"],
                                  conditions={
                                      "StringLike": {
                                          "ssm:resourceTag/SSHOwner": "*"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:StartSession",
                                      "ssm:SendCommand",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:managed-instance/mi-*"],
                                  conditions={
                                      "StringEquals": {
                                          "ssm:resourceTag/SSHOwner": "${aws:userid}"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:TerminateSession",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:session/*"],
                                  conditions={
                                      "StringLike": {
                                          "ssm:resourceTag/aws:ssmmessages:session-id": "${aws:userid}"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:StartSession",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*::document/AWS-StartSSHSession"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:SendCommand",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*::document/AWS-RunShellScript"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "logs:StartQuery",
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:logs:*:{Aws.ACCOUNT_ID}:log-group:/aws/sagemaker/*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "logs:GetQueryResults",
                                  ],
                                  resources=["*"]
                              ),
                          ]))

        # noinspection PyUnusedLocal
        ssh_server_policy = \
            ManagedPolicy(self, "SSHSageMakerServerPolicy",
                          managed_policy_name="SSHSageMakerServerPolicy",
                          document=PolicyDocument(statements=[
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "iam:PassRole",
                                  ],
                                  resources=[sagemaker_role.role_arn],
                                  conditions={
                                      "StringEquals": {
                                          "iam:PassedToService": "ssm.amazonaws.com"
                                      }
                                  }
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:AddTagsToResource",
                                  ],
                                  resources=[sagemaker_role.role_arn],
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:CreateActivation",
                                      "ssm:ListAssociations",
                                      "ec2messages:GetMessages",
                                      "ec2messages:AcknowledgeMessage",
                                      "ec2messages:SendReply",
                                      "ec2messages:DeleteMessage",
                                      "ssmmessages:CreateControlChannel",
                                      "ssmmessages:CreateDataChannel",
                                      "ssmmessages:OpenControlChannel",
                                      "ssmmessages:OpenDataChannel"
                                  ],
                                  resources=["*"]
                              ),
                              PolicyStatement(
                                  effect=Effect.ALLOW,
                                  actions=[
                                      "ssm:UpdateInstanceInformation",
                                      "ssm:ListInstanceAssociations"
                                  ],
                                  resources=[f"arn:{Aws.PARTITION}:ssm:*:{Aws.ACCOUNT_ID}:managed-instance/mi-*"],
                                  conditions={
                                      "StringLike": {
                                          "ssm:resourceTag/SSHOwner": "*"
                                      }
                                  }
                              ),
                          ]))

        ssh_server_policy.attach_to_role(sagemaker_role)
        sagemaker_core_policy.attach_to_role(user_role)
        ssh_client_policy.attach_to_role(user_role)

        with open(os.path.join(os.path.dirname(__file__), "trust_relationship_lambda.py")) as lambda_path:
            code = lambda_path.read()

        code = code.replace("<<SAGEMAKER_ROLE_ARN>>", sagemaker_role.role_name)

        role = Role(self, "TrustRelationshipLambdaRole",
                    assumed_by=ServicePrincipal("lambda.amazonaws.com"),
                    inline_policies={
                        "TrustRelationshipLambdaPolicy": PolicyDocument(statements=[
                            PolicyStatement(
                                effect=Effect.ALLOW,
                                actions=["iam:UpdateAssumeRolePolicy"],
                                resources=[sagemaker_role_arn]
                            )
                        ])})

        triggers.TriggerFunction(self, "TrustRelationshipLambdaTrigger",
                                 runtime=lambda_.Runtime.PYTHON_3_7,
                                 role=role,
                                 handler="index.handler",
                                 code=lambda_.Code.from_inline(code))

