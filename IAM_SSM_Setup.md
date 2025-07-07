## <a name="setup"></a>Setting up your AWS account with IAM and SSM configuration

> **NOTE**: This section involves AWS IAM changes and should be completed by an AWS system admin.
If you plan to use these settings in production, please, carefully review them with your security team and make sure that you apply [the least privilege permissions](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege).

SageMaker SSH Helper relies on the AWS Systems Manager service to create SSH tunnels between your client and the SageMaker component. The setup is described in the following sections.

### Setup scenarios

* [Automated setup with CDK and Cloud9](#automated-setup-with-cdk-and-cloud9)
* [Manual setup](#manual-setup)

### Automated setup with CDK and Cloud9

a. From AWS Console, pop up [CloudShell](https://aws.amazon.com/cloudshell/) environment. Alternatively, you can the commands run in your local terminal. In this case, make sure you've installed Node.js and CDK and fulfilled [all other CDK prerequisites](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html#getting_started_prerequisites). In both cases you need to have an admin role.

b. Define your SageMaker role, local user role, AWS account ID and AWS Region as variables by executing the following commands in the terminal line by line:

```shell
SAGEMAKER_ROLE_ARN=...
USER_ROLE_ARN=...
ACCOUNT_ID=...
REGION=...
```

Note that if you connect to AWS from your local CLI as an IAM user, you will need to assume a `USER_ROLE_ARN` when connecting to SageMaker. 

> **NOTE:** Using environment variables to set up access keys and assume roles on the local machine is not recommeneded
> unless you know what you are doing. **Consider [configuring AWS CLI through AWS config file](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-role.html#cli-role-overview)**.

Roughly speaking, the SageMaker role is the role assumed by a cloud compute resource and the user role is the role assumed by you on your local laptop.

b. Execute the following commands (you can copy-paste them as a whole script):

```shell
pip install 'sagemaker-ssh-helper[cdk]'
npm install -g aws-cdk

cdk bootstrap aws://"$ACCOUNT_ID"/"$REGION"

IAM_APP="python -m sagemaker_ssh_helper.cdk.iam_ssm_app"

AWS_REGION="$REGION" cdk -a "$IAM_APP" deploy SSH-IAM-SSM-Stack \
  -c sagemaker_role="$SAGEMAKER_ROLE_ARN" \
  -c user_role="$USER_ROLE_ARN"

SSM_APP="python -m sagemaker_ssh_helper.cdk.advanced_tier_app"

AWS_REGION="$REGION" cdk -a "$SSM_APP" deploy SSM-Advanced-Tier-Stack
```

In the above code we define local variable `APP` to execute CDK apps, and export `AWS_REGION` environment variable upon execution that is set to `REGION` local variable defined earlier.

Local variables `SAGEMAKER_ROLE_ARN` and `USER_ROLE_ARN` are passed as parameters to the app.

c. To enable SageMaker SSH Helper in additional AWS Regions, run these commands per region (adjust `REGION` variable each time):

```shell
REGION=...
```

```shell
cdk bootstrap aws://"$ACCOUNT_ID"/"$REGION"

AWS_REGION="$REGION" cdk -a "$SSM_APP" deploy SSM-Advanced-Tier-Stack
```

*Note:* If you will run the jobs from SageMaker Studio instead of your local machine, specify `USER_ROLE_ARN` the same as `SAGEMAKER_ROLE_ARN`.

To understand more what CDK bootstrapping does, see [the documentation](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html).

### Manual setup

#### 1. Setup Systems Manager (SSM)

a. Enable advanced instances tier to use managed instances (such as SageMaker managed containers): 
   
Go to AWS Console -> Systems Manager -> Fleet Manager -> Account management -> Instance tier settings -> Change account setting -> Confirm change from Standard-Tier to Advanced-Tier.

Repeat for each AWS Region that you plan to use with SageMaker SSH Helper.

*Note:* You need to turn on advanced tier to make to use of Systems Manager Session Manager which is required for SSH Helper to work. Advanced instances tier comes at small extra fee. Review [the pricing page](https://aws.amazon.com/systems-manager/pricing/#On-Premises_Instance_Management) for details. 


#### 2. Update your SageMaker IAM role (used with the `role` Estimator parameter)

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
                "ssm:ListInstanceAssociations",
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
                "ssm:UpdateInstanceInformation"
            ],
            "Resource": "arn:aws:ssm:*:<<ACCOUNT_ID>>:managed-instance/mi-*",
            "Effect": "Allow"
        }
    ]
}
```

*Note:* you can find your full SageMaker Role ARN at the "Summary" section of IAM console, when you look at your role. It may look like this: `arn:aws:iam::<<account_id>>:role/service-role/AmazonSageMaker-ExecutionRole-<<timestamp>>`.


#### 3. Make sure that the local user role also has all necessary permissions

a. Attach the inline policy named `SSHSageMakerClientPolicy`. Replace `<<ACCOUNT_ID>>` with your AWS account ID:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "logs:GetQueryResults",
                "ssm:DescribeInstanceInformation",
                "ssm:ListTagsForResource",
                "ssm:GetCommandInvocation"
            ],
            "Resource": "*",
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

For more details about these policies, see the question "[How SageMaker SSH Helper protects users from impersonating each other?](FAQ.md#how-sagemaker-ssh-helper-protects-users-from-impersonating-each-other)" in FAQ.

#### 4. (Optional) Connecting from SageMaker Studio 

If you want to run and debug the SageMaker jobs from SageMaker Studio, or connect from the JupyterServer to KernelGateway, instead of doing to from your local IDE, attach both `SSHSageMakerServerPolicy` and `SSHSageMakerClientPolicy` to the SageMaker execution role.

In this case, SageMaker Studio, or Jupyter Server, becomes the client, which you connect from and run `sm-ssh` command at, and the remote job, or Kernel Gateway, respectively, becomes the server, which you `connect` to, by providing the resource name like `xxx.yyy.sagemaker` as an argument.
