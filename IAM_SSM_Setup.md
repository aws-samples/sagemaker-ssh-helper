## <a name="setup"></a>Setting up your AWS account with IAM and SSM configuration

> **NOTE**: This section involves AWS IAM changes and should be completed by an AWS system admin.
If you plan to use these settings in production, please, carefully review them with your security team.

SageMaker SSH Helper relies on the AWS Systems Manager service to create SSH tunnels between your client and the 
SageMaker component. To allow that the following setup is required:  

**1. Update your SageMaker IAM role (used with the `role` Estimator parameter)**

a. Go to AWS Console -> IAM -> Roles -> your sagemaker execution role.

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

c. On the tab "Trust permissions", add `AmazonSSMManagedInstanceCore` and `CloudWatchLogsFullAccess` 
managed policies to the role.
 
d. Add to the role a new inline policy named `SageMakerSSMPolicy` as follows, replacing `<<SAGEMAKER_ROLE_ARN>>` 
     with the arn of the role you're editing:

```json
{
   "Version": "2012-10-17",
   "Statement": [
       {
           "Effect": "Allow",
           "Action": "iam:PassRole",
           "Resource": "<<SAGEMAKER_ROLE_ARN>>"
       },
       {
           "Effect": "Allow",
           "Action": "ssm:CreateActivation",
           "Resource": "*"
       },
       {
        "Effect": "Allow",
        "Action": "ssm:AddTagsToResource",
        "Resource": "<<SAGEMAKER_ROLE_ARN>>"
       }
   ]
}
```

> *Note:* you can find your full SageMaker Role ARN at the "Summary" section of IAM console, when you look at your role.
> It may look like this: `arn:aws:iam::<<account_id>>:role/service-role/AmazonSageMaker-ExecutionRole-<<timestamp>>`.

---

**2. Setup Systems Manager (SSM)**

> Note: These steps are needed if you haven't setup SSM before. 
> Pay attention to the step "2h. Enable advanced instances tier".
   
a. Create a new minimal EC2 instance, with amazon linux 2 AMI (you need it for successful setup and for verification).

b. Navigate in AWS Console to Systems Manager > Quick Setup and press 'Get started' button
   
c. From Configuration types select 'Host Management' 

d. If you have enabled AWS Organizations before, choose 'Current account'

e. Leave everything else as default and choose 'Create'. It will take several minutes to complete. 
   Make sure "Configuration association status" shows all associations are successful and not failing or pending.

f. (Optional) Verify that Systems Manager is successfully set up by connecting to the previously created EC2 instance:
   Systems Manager > Sessions Manager > Start session. In the [Target instances] table filter using the instance id (e.g., Instance ID: "i-0b900fbc0fe61e9e8") check it, and click start session. Verify you we're able to start a session.

g. Terminate the created EC2 instance (not needed anymore).

h. Enable advanced instances tier to use managed instances (such as SageMaker managed containers): 
   Systems Manager > Fleet Manager > Account management > Instance tier settings > Change account setting > Confirm change from Standard-Tier to Advanced-Tier

---

**3. Make sure that the local user role also has all necessary permissions**

a. For quick setup you may want to try the solution either with `AdministratorAccess` managed policy or 
    at least with the following policies: `AmazonSSMAutomationRole`, `CloudWatchLogsReadOnlyAccess`,
    `AmazonSageMakerFullAccess`, `AmazonS3FullAccess`.

> NOTE: you can test the solution with elevated privileges like `AdministratorAccess`,
> but for stronger security you should always scope permissions to the least privilege principle.
> For more information see [Apply least-privilege permissions](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)
> section of the IAM documentation.

b. (Optional) To prevent users from accessing each other's instances, 
    add to their role a new inline policy named `SSMDenyAccessNotOwner`.
    It helps to make sure that the local user/role, i.e. which fires the training job,
    is the same one that is connecting via SSH:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Deny",
            "Action": "ssm:StartSession",
            "Resource": "arn:aws:ssm:*:*:managed-instance/*",
            "Condition": {
                "StringNotEquals": {
                    "ssm:resourceTag/SSHOwner": "${aws:userid}"
                }
            }
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Deny",
            "Action": "ssm:SendCommand",
            "Resource": "arn:aws:ssm:*:*:managed-instance/*",
            "Condition": {
                "StringNotEquals": {
                    "ssm:resourceTag/SSHOwner": "${aws:userid}"
                }
            }
        }
    ]
}
```
