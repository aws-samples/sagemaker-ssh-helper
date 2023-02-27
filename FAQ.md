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

3. Now you may close Git Bash and start again as a normal user.
4. Don't forget to repeat steps 1-4 after you install a new version of SageMaker SSH Helper.

The scripts like `sm-local-ssh-ide` and `sm-local-ssh-training` will now work from the 
Git Bash session under a regular user, and you may continue to work in your local IDE 
on Windows as usual.

### Are SageMaker notebook instances supported?

Yes, the setup is similar to SageMaker Studio. Run [SageMaker_SSH_Notebook.ipynb](SageMaker_SSH_Notebook.ipynb) on the notebook instance and `sm-local-ssh-notebook connect <<notebook-instance-name>>` your local machine. 

Review the instructions for [SageMaker Studio integration with PyCharm / VSCode](README.md#studio) for the rest of  details.

### How do you start the SSM session without knowing EC2 instance or container ID?

Indeed, when you run a SageMaker job, there are no EC2 instances or generic containers visible in AWS console, because the instances and containers are managed by the SageMaker service.
The trick that SageMaker SSH Helper is using is [the hybrid activations](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-managedinstances.html), with SageMaker containers effectively becoming managed instances when SSM agent starts, akin to on-premises instances. The managed instances have an ID that starts with 'mi-' prefix and once they connect to the Systems Manager, you're able to see them in AWS Console in Systems Manager -> Node Manager -> Fleet Manager section.


### For Training, should I use Warm Pools or SageMaker SSH Helper?

SageMaker [Warm Pools](https://docs.aws.amazon.com/sagemaker/latest/dg/train-warm-pools.html) is a built-in SageMaker Training feature which is great when you want to use the SageMaker API to:

1. Run a series of relatively short training jobs, each job outputting a different model based on different input data (like a model per customer).
2. Interactively iterate over a series of training jobs, changing code and hyperparameters between jobs. Job launch time will be less than 30sec. When using warm pools, all training jobs are audited and logged. Warm Pools is a built-in product feature, which you can use after you [opt in](https://docs.aws.amazon.com/sagemaker/latest/dg/train-warm-pools.html#train-warm-pools-resource-limits). 

You’re billed as long as the warm pool didn't expire.

[SageMaker SSH Helper](https://github.com/aws-samples/sagemaker-ssh-helper) is a field solution for SageMaker, focused on interactive work. Enabling use cases like: 

1. The shell access to the SageMaker training container to monitor and troubleshoot using OS tools. 
2. Setup remote development/debugging experience, using your IDE to code, and run processes in the SageMaker container. 

SSH Helper's interactive nature allows you to iterate in seconds, by running multiple commands/experiment reusing one running training job. SSH Helper requires [setting up your AWS account with IAM and SSM configuration](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md). You’re billed as long the training job is running. 

### How can I do remote development on a SageMaker training job, using SSH Helper?
Start a SageMaker Training job that will run a dummy training script which sleeps forever, then use remote development 
to carry out any activities on the training container. Note, this idea and the script `train_placeholder.py` is also 
introduced in the documentation in the section [Remote code execution with PyCharm / VSCode over SSH](https://github.com/aws-samples/sagemaker-ssh-helper#remote-code-execution-with-pycharm--vscode-over-ssh).

### Can I also use this solution to connect into my jobs from SageMaker Studio?

Yes, requires adding same IAM permissions to SageMaker role as described in the [IAM_SSM_Setup.md](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/IAM_SSM_Setup.md) for your local role (section 3).

### How SageMaker SSH Helper protects users from impersonating each other?

This logic is enforced by IAM policy. See the manual step 3 in [IAM_SSM_Setup.md](IAM_SSM_Setup.md#manual-setup) 
for a policy example.

It works as follows: the SageMaker SSH Helper assigns on behalf of the user the tag `SSHOwner`
with the value that equals a local user ID (see [the source code for SSH wrappers](https://github.com/aws-samples/sagemaker-ssh-helper/blob/57b1f6369ce9e523a7951d23753a9f7f5a6a2022/sagemaker_ssh_helper/wrapper.py#L62)).
For integration with SageMaker Studio the user ID is passed in [the notebook](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/SageMaker_SSH_IDE.ipynb) as the argument to 
`sm-ssh-ide init-ssm` command. 

When a user attempts to connect to an instance, IAM will authorize the user based 
on their ID and the value of the `SSHOwner` tag. The user will be denied to access the instance 
if the instance doesn't belong to them.

Another important part of it is the IAM policy with `ssm:AddTagsToResource` action, described in the manual step 2.
Limiting this action only to SageMaker role as a resource will allow adding and updating tags only for
the newly created activations (instances) and not for existing ones that may already belong to other users.

### How to troubleshoot jobs that are failing with the exception or error?
When the job is failing, the container stops, and you're not able to connect to the container anymore with SSM or SSH.

To troubleshoot this situation, use the trick with `train_placeholder.py` described in the [README.md](README.md), and start your training script from the terminal or with the remote interpreter while the dummy script is running.

A variation of this solution is to create a wrapper script, which executes your training script and sleeps forever after the training script exits. This is how after getting an error in CloudWatch you will be able to connect to the same container with SSM/SSH and troubleshoot its state.

### I see folders like Desktop, Documents, Downloads, Pictures in SageMaker Studio, is it fine?

Yes, it's fine. They don't contain any of your local data. These are the freshly created folders by the VNC server and XFC4 remote desktop environment. You will see them if you connect to SageMaker Studio with VNC client after running `sm-local-ssh-ide` command, as described [in the IDE integration section of the documentation](README.md#a-namestudioalocal-ide-integration-with-sagemaker-studio-over-ssh-for-pycharm--vscode).

## API Questions
### How can I change the SSH authorized keys bucket and location when running `sm-local-ssh-*` commands?
The **public** key is transferred to the container through the default SageMaker bucket with the S3 URI that looks 
like `s3://sagemaker-eu-west-1-555555555555/ssh-authorized-keys/`.
If you want to change the location to your own bucket and path, export the variable like this:
```
export SSH_AUTHORIZED_KEYS_PATH=s3://DOC-EXAMPLE-BUCKET/ssh-public-keys-jane-doe/  
sm-local-ssh-ide <<kernel_gateway_app_name>>
sm-local-ssh-training connect <<training_job_name>>
```

### What if I want to train and deploy a model as a simple Estimator in my own container, without passing entry_point and source_dir?

In some cases, you don't want to pass any external scripts or libraries to the training job or the inference endpoint and want to put everything into [your own container](https://sagemaker-examples.readthedocs.io/en/latest/advanced_functionality/scikit_bring_your_own/scikit_bring_your_own.html) during the build time.
In this case, make sure that SageMaker SSH Helper is installed in your `Dockerfile`:
```dockerfile
RUN pip --no-cache-dir install sagemaker-ssh-helper  # <--NEW--
```

**Important:** Make sure that the version installed into the container matches the version of the library on your local machine.

The code for running estimators and inference will look like this:
```python
from sagemaker.estimator import Estimator
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHModelWrapper  # <--NEW--

role = ...
estimator = Estimator(image_uri=f"555555555555.dkr.ecr.eu-west-1.amazonaws.com/byoc-ssh:latest",
                      role=role,
                      instance_count=1,
                      instance_type='ml.m5.xlarge',
                      max_run=60 * 30)

training_input = ...

ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)  # <--NEW--
estimator.fit({'training': training_input}, wait=False)

...

model = estimator.create_model()

ssh_model_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)  # <--NEW--

endpoint_name = ...
predictor = model.deploy(initial_instance_count=1,
                         instance_type='ml.m5.xlarge',
                         endpoint_name=endpoint_name,
                         wait=True)
```

### What if I want to deploy a Multi Data Model without passing a reference to a Model object, only with image_uri?

In this case, you either manually pack the inference code to your model artifact during training or provide all the inference code inside the inference image.

Your code then should look like this:

```python
from sagemaker.multidatamodel import MultiDataModel
from sagemaker.pytorch import PyTorchPredictor
from sagemaker_ssh_helper.wrapper import SSHMultiModelWrapper  # <--NEW--

model_data_prefix = "s3://DOC-EXAMPLE-BUCKET/mms/"
repacked_model_data = ...
model_name = ...
model_role = ...
model_path = ...
endpoint_name = ...

mdm = MultiDataModel(
    name=model_name,
    model_data_prefix=model_data_prefix,
    image_uri='555555555555.dkr.ecr.eu-west-1.amazonaws.com/byoc:latest',
    role=model_role
)

ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)  # <--NEW--

mdm.deploy(initial_instance_count=1,
           instance_type='ml.m5.xlarge',
           wait=True)

predictor = PyTorchPredictor(endpoint_name)

mdm.add_model(model_data_source=repacked_model_data, model_data_path=model_path)

predicted_value = predictor.predict(data=..., target_model=model_path)
```

*Note:* Your repacked model should also contain the SageMaker SSH Helper library files, and you need to import and start it from your inference script just as you do for the normal inference.

See [#7](https://github.com/aws-samples/sagemaker-ssh-helper/issues/7) for this request.

### What if I want to use an estimator in a hyperparameter tuning job (HPO) and connect to a stuck training job with SSM?

In this case, `wrapper.get_instance_ids()` won't really work because you don't call `fit()` directly on the estimator and SSH Helper does not understand what training job you are trying to connect to.

You should use extra lower-level APIs to fetch the training job name of your interest first, and then either use `SSMManager` (recommended) or `SSHLog` (slower) to fetch their instance ids from the code:

```python
import time

from sagemaker.mxnet import MXNet
from sagemaker.tuner import HyperparameterTuner

from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper

estimator = MXNet(...)

_ = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=0)

objective_metric_name = ...
hyperparameter_ranges = ...
metric_definitions = ...

tuner = HyperparameterTuner(estimator,
                            objective_metric_name,
                            hyperparameter_ranges,
                            metric_definitions,
                            ...
                            )

tuner.fit(wait=False)

time.sleep(15)  # allow training jobs to start

analytics = tuner.analytics()
training_jobs = analytics.training_job_summaries()
training_job_name = training_jobs[0]['TrainingJobName']

instance_ids = SSMManager().get_training_instance_ids(training_job_name, 300)

print(f'To connect over SSM run: aws ssm start-session --target {instance_ids[0]}')
```

*Note:* If you want to connect to a stuck training job from the command line with SSH, use `sm-local-ssh-training` script, as for any other regular training job.

### How to start a job with SageMaker SSH Helper in an AWS Region different from my default one?

Define the SSH wrapper as usual, e.g.:

```python
import boto3
import sagemaker
from sagemaker.pytorch import PyTorchProcessor

from sagemaker_ssh_helper.wrapper import SSHProcessorWrapper

wait_time = ...
role = ...

boto3_session = boto3.session.Session(region_name='eu-west-2')  # <-- AWS Region override
sagemaker_session = sagemaker.Session(boto_session=boto3_session)

torch_processor = PyTorchProcessor(
    sagemaker_session=sagemaker_session,
    base_job_name='ssh-pytorch-processing',
    framework_version='1.9.1',
    py_version='py38',
    role=role,
    instance_count=1,
    instance_type="ml.m5.xlarge",
    max_runtime_in_seconds=60 * 60 * 3,
)

ssh_wrapper = SSHProcessorWrapper.create(torch_processor, connection_wait_time_seconds=wait_time)
```

When calling `ssh_wrapper.get_instance_ids()`, the region will be taken automatically from the wrapper.

However, when you connect to the containers from CLI with `aws ssm start-session` command or with `sm-local-ssh-*` commands, you need to redefine the AWS Region like this:
```text
AWS_REGION=eu-west-2 AWS_DEFAULT_REGION=eu-west-2 \
  sm-local-ssh-processing connect <<processing_job_name>>
```
We set both `AWS_REGION` and `AWS_DEFAULT_REGION`, because depending on your environment, either of this variable can be already set, and it can override another one.

### How to configure an AWS CLI profile to work with SageMaker SSH Helper?

You can control AWS CLI settings with [environment variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), in particular, this is how to select the AWS CLI profile with `sm-local-ssh-*` tools:

```shell
AWS_PROFILE=<<profile_name>> sm-local-ssh-ide <<kernel_gateway_app_name>> 
```

### How do I automate my pipeline with SageMaker SSH Helper end-to-end?
There’s plenty of methods already available for you to automate everything.
Take a loot at the [end-to-end automated tests](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/tests/test_end_to_end.py) as an example.

There's `get_instance_ids()` method already mentioned in the documentation. Underlying automation methods are available in the [SSMManager class](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/manager.py) and the [SSHLog class](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/log.py).

Also check the method `start_ssm_connection_and_continue()` from the [SSHEnvironmentWrapper class](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/wrapper.py) - it automates creating the SSH tunnel, running remote commands and stopping the waiting loop as well as graceful disconnect. Underlying implementation is in the [SSMProxy class](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/proxy.py).


## AWS SSM Troubleshooting
### I’m getting an API throttling error in the logs: `An error occurred (ThrottlingException) when calling the CreateActivation operation (reached max retries: 4): Rate exceeded`

This error happens when too many instances are trying to register to SSM at the same time - This will likely happen when you run a SageMaker training job with multiple instances.  
As a workaround, for SageMaker training job, you should connect to any of the nodes that successfully registered in SSM (say “algo-1”), then from there you could hope over to other nodes with the existing passwordless SSH.  
You could also submit an AWS Support ticket to increase the API rate limit, but for the reason stated above, we don’t think that’s needed.

### How can I see which SSM commands are running in the container?
Login into the container and run:  
`tail -f  /var/log/amazon/ssm/amazon-ssm-agent.log`

### How can I clean up System Manager after receiving `ERROR Registration failed due to error registering the instance with AWS SSM. RegistrationLimitExceeded: Registration limit of 20000 reached for SSM On-prem managed instances.`
SageMaker containers are transient in nature. SM SSH Helper registers this container to SSM as a "managed instances". Currently, there's no built-in mechanism to deregister them when a job is completed. This accumulation of registrations might cause you to arrive at an SSM registration limit. To resolve this, consider cleaning up stale, SM SSH Helper related registrations, manually via the UI, or using [deregister_old_instances_from_ssm.py](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/deregister_old_instances_from_ssm.py).  
WARNING: you should be careful NOT deregister managed instances that are not related to SM SSH Helper. [deregister_old_instances_from_ssm.py](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/sagemaker_ssh_helper/deregister_old_instances_from_ssm.py) includes a number of filters to deregister only SM SSH Helper relevant managed instances. It's recommended you review the current registered manage instances in the AWS Console Fleet manager, before actually removing them.  
Deregistering requires an administrator / power user IAM privileges. 

### There's a big delay between getting the mi-* instance ID and until I can successfully start a session to the container. 
This can happen if there's SSM API throttling taking place during instance initialization. In such a case, after you are able to shell into the container you'll be able to identify this by grepping for this printout during SSM agent initialization:  

`grep Throttling /var/log/amazon/ssm/amazon-ssm-agent.log`  
```
2022-12-15 12:37:17 INFO [ssm-agent-worker] Entering SSM Agent hibernate - ThrottlingException: Rate exceeded status code: 400, request id: 56ae2c79-bb35-4903-ab49-59cf9e131aca
```
You should submit an AWS Support ticket to identify the relevant API limit and increase it.

### I get an error about advanced-instances tier configured incorrectly

An error message looks like this:
```text
An error occurred (BadRequest) when calling the StartSession operation: Enable advanced-instances tier to use Session Manager with your on-premises instances
```

First, check that your instance shows as an advanced instance in Fleet Manager.
If it doesn't show up there, you've probably missed the manual step 1 in [IAM_SSM_Setup.md](IAM_SSM_Setup.md#manual-setup).

Also check that you're connecting from the same AWS region. Run the following command on your local machine and check that the region is the same as in your AWS console:
```shell
aws configure list | grep region 
```