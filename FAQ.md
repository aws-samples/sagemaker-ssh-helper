# Frequently Asked Questions

We often see a lot of questions that surface repeatedly. This repository is an attempt to gather some of those and provide some answers!

## General Questions

### Is it working on Windows?

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

*Q: How can I do remote development on a SageMaker training job, using SSH Helper?*
*A:* Start a SM Training job that will run a dummy training script which sleeps forever, then use remote development to carry out any activities on the training container. (Note, this idea and the script ‘train_placeholder.py’ is also introduced in the documentation in the section “Remote code execution with PyCharm / VSCode over SSH (https://github.com/aws-samples/sagemaker-ssh-helper#remote-code-execution-with-pycharm--vscode-over-ssh)”).

### Can I also use this solution to connect into my jobs from SageMaker Studio?

Yes, requires adding same IAM permissions to SageMaker role as described in the [IAM_SSM_Setup.md](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md) for your local role (section 3).

### I’m getting an API throttling error in the logs: `An error occurred (ThrottlingException) when calling the CreateActivation operation (reached max retries: 4): Rate exceeded`

This error happens when too many instances are trying to register to SSM at the same time - This will likely happen when you run a SageMaker training job with multiple instances.  
As a workaround, for SageMaker training job, you should connect to any of the nodes that successfully registered in SSM (say “algo-1”), then from there you could hope over to other nodes with the existing passwordless SSH.  
You could also submit an AWS Support ticket to increase the API rate limit, but for the reason stated above, we don’t think that’s needed.
