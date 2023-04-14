from aws_cdk import Stack, Aws
from aws_cdk.aws_iam import PolicyDocument, PolicyStatement, Effect, ManagedPolicy, Role
from constructs import Construct


class IamSsmStackTests(Stack):

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
                                      "sagemaker:CreateHyperParameterTuningJob",
                                      "sagemaker:DescribeTrainingJob",
                                      "sagemaker:DescribeProcessingJob",
                                      "sagemaker:DescribeModel",
                                      "sagemaker:DescribeEndpoint",
                                      "sagemaker:DescribeTransformJob",
                                      "sagemaker:DescribeHyperParameterTuningJob",
                                      "sagemaker:ListTrainingJobsForHyperParameterTuningJob",
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

        sagemaker_core_policy.attach_to_role(user_role)
