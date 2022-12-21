# Frequently Asked Questions

We often see a lot of questions that surface repeatedly. This repository is an attempt to gather some of those and provide some answers!

## General Questions

### Is Windows supported?

The solution was primarily designed for developers who are using Linux and macOS.
However, it's possible also to make it working on Windows.

Basic scenarios, which require only SSM without SSH, work on Windows without 
any additional configuration.

To be able to connect from your local machine with SSH and start port forwarding with 
the scripts like `sm-local-ssh-ide` and `sm-local-ssh-training`, please consider that 
you need Bash interpreter to execute them. They don't work in PowerShell.

We recommend obtaining Bash by installing [Git for Windows](https://gitforwindows.org/) distribution.
The next steps are:

1. Run "Git Bash" application as Administrator.

2. Find the path where pip has installed your library and 
execute `sm-local-install-force` once:

```shell
$ cd ~/AppData/Local/Packages/PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0/LocalCache/local-packages/Python310/site-packages/sagemaker_ssh_helper
$ ./sm-local-install-force
```

4. Now you may close Git Bash and start again as a normal user.
5. Don't forget to repeat steps 1-4 after you install a new version of SageMaker SSH Helper.

The scripts like `sm-local-ssh-ide` and `sm-local-ssh-training` will now work from the 
Git Bash session under a regular user, and you may continue to work in your local IDE 
on Windows as usual.


### For Training, should I use Warm Pools or SageMaker SSH Helper?

SageMaker [Warm Pools](https://docs.aws.amazon.com/sagemaker/latest/dg/train-warm-pools.html) is a built-in SageMaker Training feature which is great when you want to use the SageMaker API to:
  1. Run a series of relatively short training jobs, each job outputting a different model based on different input data (like a model per customer).
  2. Interactively iterate over a series of training jobs, changing code and hyperparameters between jobs. Job launch time will be less than 30sec. When using warm pools, all training jobs are audited and logged. Warm Pools is a built-in product feature, which you can use after you [opt-in](https://docs.aws.amazon.com/sagemaker/latest/dg/train-warm-pools.html#train-warm-pools-resource-limits). You’re billed as long as the warm pool didn’t expire.

[SageMaker SSH Helper](https://github.com/aws-samples/sagemaker-ssh-helper) is a field solution for SageMaker, focused on interactive work. Enabling use cases like: 

 1. Shell access to the SageMaker training container to monitor and troubleshoot using OS tools. 
 2. Setup remote development/debugging experience, using your IDE to code, and run processes in the SageMaker container. 

SSH Helper's interactive nature allows you to iterate in seconds, by running multiple commands/experiment reusing one running training job. SSH Helper requires [setting up your AWS account with IAM and SSM configuration](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md). You’re billed as long the training job is running. 

### How can I do remote development on a SageMaker training job, using SSH Helper?
Start a SM Training job that will run a dummy training script which sleeps forever, then use remote development to carry out any activities on the training container. (Note, this idea and the script ‘train_placeholder.py’ is also introduced in the documentation in the section “Remote code execution with PyCharm / VSCode over SSH (https://github.com/aws-samples/sagemaker-ssh-helper#remote-code-execution-with-pycharm--vscode-over-ssh)”).

### Can I also use this solution to connect into my jobs from SageMaker Studio?

Yes, requires adding same IAM permissions to SageMaker role as described in the [IAM_SSM_Setup.md](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md) for your local role (section 3).

### How SageMaker SSH Helper protects users from impersonating each other?

This logic is enforced by IAM policy. See the step 3b in [IAM_SSM_Setup.md](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md) 
for a policy example.

It works as follows: the SageMaker SSH Helper assigns on behalf of the user the tag `SSHOwner`
with the value that equals a local user ID (see [the source code for SSH wrappers](https://github.com/aws-samples/sagemaker-ssh-helper/blob/57b1f6369ce9e523a7951d23753a9f7f5a6a2022/sagemaker_ssh_helper/wrapper.py#L62)).
For integration with SageMaker Studio the user ID is passed in [the notebook](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/SageMaker_SSH_IDE.ipynb) as the argument to 
`sm-ssh-ide init-ssm` command. 

When a user attempts to connect to an instance, IAM will authorize the user based 
on their ID and the value of the `SSHOwner` tag. The user will be denied to access the instance 
if the instance doesn't belong to them.

Another important part of it is the IAM policy with `ssm:AddTagsToResource` action, described in the step 1d.
Limiting this action only to SageMaker role as a resource will allow adding and updating tags only for
the newly created activations (instances) and not for existing ones that may already belong to other users.

### How can I change the SSH authorized keys bucket and location when running `sm-local-ssh-*` commands?
The public key is transferred to the container through the default SageMaker bucket with the S3 URI that looks 
like `s3://sagemaker-eu-west-1-/ssh-authorized-keys/`.
If you want to change the location to your own bucket and path, export the variable like this:
```
export SSH_AUTHORIZED_KEYS_PATH=s3://DOC-EXAMPLE-BUCKET/ssh-keys-jane-doe/  
sm-local-ssh-ide <<kernel_gateway_app_name>>
sm-local-ssh-training connect <<training_job_name>>

```

## AWS SSM Troubleshooting
### I’m getting an API throttling error in the logs: `An error occurred (ThrottlingException) when calling the CreateActivation operation (reached max retries: 4): Rate exceeded`

This error happens when too many instances are trying to register to SSM at the same time - This will likely happen when you run a SageMaker training job with multiple instances.  
As a workaround, for SageMaker training job, you should connect to any of the nodes that successfully registered in SSM (say “algo-1”), then from there you could hope over to other nodes with the existing passwordless SSH.  
You could also submit an AWS Support ticket to increase the API rate limit, but for the reason stated above, we don’t think that’s needed.

### How can I see which SSM commands are running in the container?
Login into the container and run:  
`tail -f  /var/log/amazon/ssm/amazon-ssm-agent.log`

### How can I clean up System Manager after receiving `ERROR Registration failed due to error registering the instance with AWS SSM. RegistrationLimitExceeded: Registration limit of 20000 reached for SSM On-prem managed instances.`
SageMaker containers are transient in nature. SM SSH Helper registers this container to SSM as a "managed instances". Currently, there's no built-in machinsm to deregister them when a job is completed. This accumulation of registrations might cause you to arrive at an SSM registration limit. To resolve this consider cleaning up stale, SM SSH Helper related registrations, manually via the UI, or using [deregister_old_instances_from_ssm.py](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/deregister_old_instances_from_ssm.py).  
WARNING: you should be careful NOT deregister managed instances that are not related to SM SSH Helper. [deregister_old_instances_from_ssm.py](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/deregister_old_instances_from_ssm.py) includes a number of filters to deregister only SM SSH Helper relevant managed instances. It's recommended you review the current registered manage instances in the AWS Console Fleet manager, before actually removing them.  
Deregistering requires an administrator/poweruser IAM privileges. 

### There's a big delay between getting the mi-* instance ID and until I can successfully start a session to the container. 
This can happen if there's SSM API throttling taking place during instance initialization. In such a case, after you are able to shell into the container you'll be able to identify this by grepping for this printout during SSM agent initialization:  

`grep Throttling /var/log/amazon/ssm/amazon-ssm-agent.log`  
```
2022-12-15 12:37:17 INFO [ssm-agent-worker] Entering SSM Agent hibernate - ThrottlingException: Rate exceeded status code: 400, request id: 56ae2c79-bb35-4903-ab49-59cf9e131aca
```
You should submit an AWS Support ticket to identify the relevant API limit and increase it.