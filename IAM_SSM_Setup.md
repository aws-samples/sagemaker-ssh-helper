## <a name="setup"></a>Setting up your AWS account with IAM and SSM configuration

> **NOTE**: This section involves AWS IAM changes and should be completed by an AWS system admin.
If you plan to use these settings in production, please, carefully review them with your security team.

SageMaker SSH Helper relies on the AWS Systems Manager service to create SSH tunnels between your client and the SageMaker component. The setup is described in the following sections.

### Manual setup

**1. Setup Systems Manager (SSM)**

a. Enable advanced instances tier to use managed instances (such as SageMaker managed containers): 
   Systems Manager > Fleet Manager > Account management > Instance tier settings > Change account setting > Confirm change from Standard-Tier to Advanced-Tier.

Repeat for each AWS Region that you plan to use with SageMaker SSH Helper.

> *Note:* Advanced instances tier comes at small extra fee. Review [the pricing page](https://aws.amazon.com/systems-manager/pricing/#On-Premises_Instance_Management) for details.

---

**2. Update your SageMaker IAM role (used with the `role` Estimator parameter)**

a. Go to AWS Console -> IAM -> Roles -> your SageMaker execution role.

b. On the tab "Trust relationships", add trust relationship with SSM, so it will look like this:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "sagemaker.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        },
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ssm.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

c. Add to the role a new inline policy named `SSHSageMakerServerPolicy` as follows, replacing `<<SAGEMAKER_ROLE_ARN>>` with the arn of the role you're editing and `<<ACCOUNT_ID>>` with your AWS account ID:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": "ssm.amazonaws.com"
                }
            },
            "Action": "iam:PassRole",
            "Resource": "<<SAGEMAKER_ROLE_ARN>>",
            "Effect": "Allow"
        },
        {
            "Action": "ssm:AddTagsToResource",
            "Resource": "<<SAGEMAKER_ROLE_ARN>>",
            "Effect": "Allow"
        },
        {
            "Action": [
                "ec2messages:AcknowledgeMessage",
                "ec2messages:DeleteMessage",
                "ec2messages:GetMessages",
                "ec2messages:SendReply",
                "ssm:CreateActivation",
                "ssm:ListAssociations",
                "ssmmessages:CreateControlChannel",
                "ssmmessages:CreateDataChannel",
                "ssmmessages:OpenControlChannel",
                "ssmmessages:OpenDataChannel"
            ],
            "Resource": "*",
            "Effect": "Allow"
        },
        {
            "Condition": {
                "StringLike": {
                    "ssm:resourceTag/SSHOwner": "*"
                }
            },
            "Action": [
                "ssm:ListInstanceAssociations",
                "ssm:UpdateInstanceInformation"
            ],
            "Resource": "arn:aws:ssm:*:<<ACCOUNT_ID>>:managed-instance/mi-*",
            "Effect": "Allow"
        }
    ]
}
```

> *Note:* you can find your full SageMaker Role ARN at the "Summary" section of IAM console, when you look at your role.
> It may look like this: `arn:aws:iam::<<account_id>>:role/service-role/AmazonSageMaker-ExecutionRole-<<timestamp>>`.

---

**3. Make sure that the local user role also has all necessary permissions**

a. For quick setup you may want to try the solution either with `AdministratorAccess` managed policy or 
    at least with the following policies: `AmazonSSMAutomationRole`, `CloudWatchLogsReadOnlyAccess`,
    `AmazonSageMakerFullAccess`, `AmazonS3FullAccess`.

> NOTE: you can test the solution with elevated privileges like `AdministratorAccess`,
> but for stronger security you should always scope permissions to the least privilege principle.
> For more information see [Apply least-privilege permissions](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)
> section of the IAM documentation.

b. Alternatively, attach the inline policy named `SSHSageMakerClientPolicy`. It follows the least privilege principle and helps to make sure that the local user/role, i.e. which fires the training job, is the same one that is connecting via SSH. Replace `<<ACCOUNT_ID>>` with your AWS account ID:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "logs:GetQueryResults",
                "ssm:DescribeInstanceInformation",
                "ssm:ListTagsForResource"
            ],
            "Resource": "*",
            "Effect": "Allow"
        },
        {
            "Condition": {
                "StringLike": {
                    "ssm:resourceTag/SSHOwner": "*"
                }
            },
            "Action": "ssm:DeregisterManagedInstance",
            "Resource": "arn:aws:ssm:*:<<ACCOUNT_ID>>:managed-instance/mi-*",
            "Effect": "Allow"
        },
        {
            "Condition": {
                "StringEquals": {
                    "ssm:resourceTag/SSHOwner": "${aws:userid}"
                }
            },
            "Action": [
                "ssm:SendCommand",
                "ssm:StartSession"
            ],
            "Resource": "arn:aws:ssm:*:<<ACCOUNT_ID>>:managed-instance/mi-*",
            "Effect": "Allow"
        },
        {
            "Condition": {
                "StringLike": {
                    "ssm:resourceTag/aws:ssmmessages:session-id": "${aws:userid}"
                }
            },
            "Action": "ssm:TerminateSession",
            "Resource": "arn:aws:ssm:*:<<ACCOUNT_ID>>:session/*",
            "Effect": "Allow"
        },
        {
            "Action": "ssm:StartSession",
            "Resource": "arn:aws:ssm:*::document/AWS-StartSSHSession",
            "Effect": "Allow"
        },
        {
            "Action": "ssm:SendCommand",
            "Resource": "arn:aws:ssm:*::document/AWS-RunShellScript",
            "Effect": "Allow"
        },
        {
            "Action": "logs:StartQuery",
            "Resource": "arn:aws:logs:*:<<ACCOUNT_ID>>:log-group:/aws/sagemaker/*",
            "Effect": "Allow"
        }
    ]
}
```

*Note:* If you will run the jobs from SageMaker Studio instead of your local machine, attach both `SSHSageMakerServerPolicy` and `SSHSageMakerClientPolicy` to the SageMaker execution role.


### Automated setup with CDK and Cloud9

a. Create the [Cloud9](https://docs.aws.amazon.com/cloud9/latest/user-guide/create-environment-main.html) environment.

b. Execute the following commands, replacing `<<SAGEMAKER_ROLE_ARN>>` with the arn of your SageMaker role, `<<USER_ROLE_ARN>>` with your local user role, `<<ACCOUNT_ID>>` with your AWS account ID, `<<REGION>>` with your AWS Region, and `<<VERSION>>` with [the release version](https://github.com/aws-samples/sagemaker-ssh-helper/releases) of the SageMaker SSH Helper (e.g., `v1.9.2`):

```shell
git clone --depth 1 --branch <<VERSION>> https://github.com/aws-samples/sagemaker-ssh-helper.git

cd sagemaker-ssh-helper/
pip install '.[cdk]'

cd cdk/

cdk bootstrap aws://<<ACCOUNT_ID>>/<<REGION>> \
  -c sagemaker_role=<<SAGEMAKER_ROLE_ARN>> \
  -c user_role=<<USER_ROLE_ARN>>

cdk deploy --all \
  -c sagemaker_role=<<SAGEMAKER_ROLE_ARN>> \
  -c user_role=<<USER_ROLE_ARN>>
```

c. For each additional region, repeat bootstrapping command and deploy command for the advanced tier stack:

```shell

cdk bootstrap aws://<<ACCOUNT_ID>>/<<REGION>> \
  -c sagemaker_role=<<SAGEMAKER_ROLE_ARN>> \
  -c user_role=<<USER_ROLE_ARN>>

AWS_REGION=<<REGION>> cdk deploy SSM-Advanced-Tier-Stack \
  -c sagemaker_role=<<SAGEMAKER_ROLE_ARN>> \
  -c user_role=<<USER_ROLE_ARN>>
```

*Note:* If you will run the jobs from SageMaker Studio instead of your local machine, specify `<<USER_ROLE_ARN>>` the same as `<<SAGEMAKER_ROLE_ARN>>`.