## Overview

SageMaker SSH Helper is a library that helps you to securely connect to Amazon SageMaker's training jobs, processing jobs, 
realtime inference endpoints, and SageMaker Studio notebook containers for fast interactive experimentation, 
remote debugging, and advanced troubleshooting.

The two most common scenarios for the library are:
1. Open a terminal session into a container running in SageMaker to diagnose a stuck training job, use CLI commands 
like nvidia-smi, or iteratively fix and re-execute your training script within seconds. 
2. Remote debug a code running in SageMaker from your local favorite IDE like 
PyCharm Professional Edition or Visual Studio Code.

Other scenarios include but not limited to connecting to a remote Jupyter Notebook in SageMaker Studio from your IDE 
or start a VNC session to SageMaker Studio to run GUI apps.

## How it works
SageMaker SSH helper uses AWS Systems Manager (SSM) Session Manager, to register the SageMaker container in SSM, followed 
by creating an SSM session between your client machine and the SageMaker container. You can then create an SSH connection 
on top of the SSM session, that allows opening a Linux shell, and/or configuring bidirectional SSH port forwarding to 
enable applications like remote development/debugging/desktop, and others.

![Screenshot](images/layers.png)

See detailed architecture diagrams of the complete flow of participating components 
in [Training Diagram](Flows.md), and [IDE integration with SageMaker Studio diagram](Flows_IDE.md).

## Getting started

To get started, your AWS system administrator must set up needed IAM and SSM configuration in your AWS account as shown 
in [Setting up your AWS account with IAM and SSM configuration](IAM_SSM_Setup.md).

> **Note**: This solution is a sample AWS content. You should not use this content in your production accounts, in a production 
> environment or on production or other critical data. If you plan to use the solution in production, please, carefully review it with your security team. 
> You are responsible for testing, securing, and optimizing the sample content 
> as appropriate for production grade use based on your specific business requirements, including any quality control 
practices and standards.


## Use Cases
SageMaker SSH Helper supports a variety of use cases:
- [Connecting to SageMaker training jobs with SSM](#training) - open a shell to the training job to examine its file systems,
monitor resources, produce thread-dumps for stuck jobs, and interactively run your train script.
- [Connecting to SageMaker inference endpoints with SSM](#inference)
- [Connecting to SageMaker processing jobs with SSM](#processing)  
- [Remote debugging with PyCharm Debug Server over SSH](#pycharm-debug-server)  
- [Remote code execution with PyCharm / VSCode over SSH](#remote-interpreter)
- [Local IDE integration with SageMaker Studio over SSH for PyCharm / VSCode](#studio)  

If you want to add a new use case or a feature, see [CONTRIBUTING](CONTRIBUTING.md).

## <a name="training"></a>Connecting to SageMaker training jobs with SSM

The initial thing you need to do is to add SageMaker SSH Helper library to your project (steps 1 and 2).

### Step 1 - Unpacking into your project folder
As an ML developer, download the repo as an archive and unpack it to the root of your project (outside your source directory).
Let say you have a PyTorch estimator defined as below:

```python
estimator = PyTorch(entry_point='train.py',
                    source_dir='code',
                    role=role,
                    framework_version='1.9.1',
                    py_version='py38',
                    instance_count=1,
                    instance_type='ml.m5.xlarge')
```

After unpacking `sagemaker-ssh-helper-VERSION.zip` next to the `code/` directory, your project structure should look like this:
```shell
./code/
    train.py
./sagemaker-ssh-helper-VERSION/
    sagemaker_ssh_helper/
        __init.py__
        log.py
        ...
    setup.py
    ...
./sagemaker-ssh-helper-VERSION.zip
./start_job.py
```

### Step 2 - pip install the library
Install the library from the unpacked directory:

```shell
pip install ./sagemaker-ssh-helper-VERSION/
```

### Step 3 - Modify the start training job code
1. Add import for SSHEstimatorWrapper
2. Add a `dependencies` parameter to the Estimator object.
3. Add an `SSHEstimatorWrapper.create(estimator,...)` call before calling `fit()` and add SageMaker SSH Helper 
as `dependencies`.
4. Add a call to `ssh_wrapper.get_instance_ids()` to get the SSM instance(s) id. We'll use this as the target 
to connect to later on.   

For example:

```python
from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper  # <--NEW--

estimator = PyTorch(entry_point='train.py',
                    source_dir='code',
                    dependencies=[SSHEstimatorWrapper.dependency_dir()],  # <--NEW--
                    role=role,
                    framework_version='1.9.1',
                    py_version='py38',
                    instance_count=1,
                    instance_type='ml.m5.xlarge')

ssh_wrapper = SSHEstimatorWrapper.create(estimator, connection_wait_time_seconds=600)  # <--NEW--

estimator.fit(wait=False)

instance_ids = ssh_wrapper.get_instance_ids() # <--NEW--
print(f'To connect over SSM run: aws ssm start-session --target {instance_ids[0]}')  # <--NEW--
```

*Note:* `connection_wait_time_seconds` is the amount of time the SSH helper will wait inside SageMaker before it continues normal execution. It's useful for training jobs, when you want to connect before training starts.
If you don't want to wait, set it to 0.

### Step 4 - Modify your training script
Add into your `train.py` the following lines at the top:

```python
import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()
```

The `setup_and_start_ssh()` will start an SSM agent that will connect the training instance to AWS Systems Manager.

### Step 5 - Connecting over SSM
Once you launched the job, you'll need to wait, a few minutes, for the SageMaker container to start and the SSM agent to start successfully. Then you'll need to have the ID of the managed instance. The instance id is prefixed by `mi-` and will appear in the job's CloudWatch log like this:

```
Successfully registered the instance with AWS SSM using Managed instance-id: mi-01234567890abcdef
``` 

*Tip:* To fetch the instance IDs from the logs in an automated way, call the Python method of `ssh_wrapper`:

```python
instance_ids = ssh_wrapper.get_instance_ids()
```

With the instance id at hand, you will be able to connect to the training container using the command line or the AWS web console:  

A. Connecting using command line:  

1. Make sure that the latest AWS CLI **v2** is installed, as described in 
[the documentation for AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
   
2. Install AWS Session Manager CLI plugin as described in [the SSM documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).

3. Run this command (replace the target value with the instance id for your SageMaker job). Example:
  ```
  aws ssm start-session --target mi-0d8404fdeef955ca3
  ```

B. Connecting using the AWS Web Console:  

  1. In AWS Web Console, navigate to Systems Manager > Fleet Manager.     
  2. Select the node, then Node actions > Start terminal session.

Once connected to the container, you would want to switch to the root user with `sudo su - -c bash`  

*Tip:* Here are some useful commands:  
- `ps afx` - Show running list of processes.
- `ls -l /opt/ml/input/data` - Show input channels.
- `ls -l /opt/ml/code` - Show your training code  
- Also see the below section [Generating a thread dump for stuck training jobs](#gdb).

### <a name="gdb"></a>Generating a thread dump for stuck training jobs
In case your training job is stuck, it can be useful to observe what where its threads are waiting/busy.
This can be done without connecting to a python debugger beforehand.

1. Having connected to the container as root, find the process id (pid) of the training job:  
`pgrep --newest -f train.py`  
2. Install GNU debugger:  
`apt-get -y install gdb python3.9-dbg`  
3. Start the GNU debugger with python support:  
`gdb python`
`source /usr/share/gdb/auto-load/usr/bin/python3.9-dbg-gdb.py`  
4. Connect to the process (replace 361 with your pid):  
`attach 361`  
5. Show C low-level thread dump:  
`info threads`  
6. Show Python high-level thread dump:  
`py-bt`  
7. It might also be useful to observe what system calls the process is making:
`apt-get install strace`
8. Trace the process (replace 361 with your pid):  
`sudo strace -p 361`

## <a name="inference"></a>Connecting to SageMaker inference endpoints with SSM

Adding SageMaker SSH Helper to inference endpoint is similar to training with the following differences.

1. Wrap your model into `SSHModelWrapper` before calling `deploy()` and add SSH Helper to `dependencies`:

```python
from sagemaker_ssh_helper.wrapper import SSHModelWrapper  # <--NEW--

model = estimator.create_model(entry_point='inference.py',
                               source_dir='source_dir/',
                               dependencies=[SSHModelWrapper.dependency_dir()])  # <--NEW--

ssh_wrapper = SSHModelWrapper.create(model, connection_wait_time_seconds=0)  # <--NEW--

predictor = model.deploy(initial_instance_count=1,
                         instance_type='ml.m5.xlarge',
                         endpoint_name=endpoint_name)    
```

*Note:* For the inference endpoint, which is always up and running, there's not too much value 
in setting `connection_wait_time_seconds`, so it's usually set to `0`.

Similar to training jobs, you can fetch the instance ids for connecting to the endpoint with SSM with 
the following API:

```python
instance_ids = ssh_wrapper.get_instance_ids()
```

2. Add the following lines at the top of your `inference.py` script:

```python
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()
```

*Note:* adding `lib` dir to Python path is required, because SageMaker inference is putting dependencies 
into the `code/lib` directory, while SageMaker training put libs directly to `code`. 

### Multi-model endpoints

For multi-model endpoints, the setup procedure is slightly different from regular endpoints:

```python
from sagemaker_ssh_helper.wrapper import SSHModelWrapper  # <--NEW--

model = estimator.create_model(entry_point='inference.py',
                               source_dir='source_dir/',
                               dependencies=[SSHModelWrapper.dependency_dir()])  # <--NEW--

mdm = MultiDataModel(
    name=model.name,
    model_data_prefix=model_data_prefix,
    model=model
)

ssh_wrapper = SSHMultiModelWrapper.create(mdm, connection_wait_time_seconds=0)  # <--NEW--

predictor: Predictor = mdm.deploy(initial_instance_count=1,
                                  instance_type='ml.m5.xlarge',
                                  endpoint_name=endpoint_name)


mdm.add_model(model_data_source=model.repacked_model_data, model_data_path=model_name)

predictor.predict(data=..., target_model=model_name)
```

*Important:* Make sure that you're passing to `add_model()` a model ready for deployment located at `model.repacked_model_data`,
not the `estimator.model_data`.

Also note that SageMaker SSH Helper will be lazy loaded together with your model upon the first prediction request.
So you should try to connect only after calling `predict()`.

The `inference.py` script is the same as for SageMaker SSH Helper with regular endpoints.

If you are using PyTorch containers, make sure you select the latest versions, 
e.g. 1.12, 1.11, 1.10 (1.10.2), 1.9 (1.9.1).
This code might not work if you use PyTorch 1.8, 1.7 or 1.6.

## <a name="processing"></a>Connecting to SageMaker processing jobs with SSM

SageMaker SSH Helper supports both Script Processors and Framework processors and setup procedure is similar 
to training jobs and inference endpoints.

#### A. Framework processors

The code to set up a framework processor (e.g. PyTorch) is the following:

```python
from sagemaker_ssh_helper.wrapper import SSHProcessorWrapper  # <--NEW--

torch_processor = PyTorchProcessor(
    base_job_name='ssh-pytorch-processing',
    framework_version='1.9.1',
    py_version='py38',
    role=role,
    instance_count=1,
    instance_type="ml.m5.xlarge"
)

ssh_wrapper = SSHProcessorWrapper.create(torch_processor, connection_wait_time_seconds=600)  # <--NEW--

torch_processor.run(
    source_dir="source_dir/",
    dependencies=[SSHProcessorWrapper.dependency_dir()],  # <--NEW--
    code="process_framework.py"
)
```

Also add the following lines at the top of `process.py`:

```python
import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()
```

#### B. Script Processors

The code to set up a script processor (e.g. PySpark) is the following:

```python
from sagemaker_ssh_helper.wrapper import SSHProcessorWrapper  # <--NEW--

spark_processor = PySparkProcessor(
    base_job_name='ssh-spark-processing',
    framework_version="3.0",
    role=role,
    instance_count=1,
    instance_type="ml.m5.xlarge"
)

ssh_wrapper = SSHProcessorWrapper.create(spark_processor, connection_wait_time_seconds=600)  # <--NEW--

spark_processor.run(
    submit_app="source_dir/process.py",
    inputs=[ssh_wrapper.augmented_input()]  # <--NEW--
)
```

Also add the following lines at the top of `process.py`:

```python
import sys
sys.path.append("/opt/ml/processing/input/")

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()
```

## <a name="pycharm-debug-server"></a>Remote debugging with PyCharm Debug Server over SSH

This procedure uses PyCharm's Professional feature: [Remote debugging with the Python remote debug server configuration](https://www.jetbrains.com/help/pycharm/remote-debugging-with-product.html#remote-debug-config)

1. On the local machine, make sure that the latest AWS CLI **v2** is installed, as described in 
[the documentation for AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
   
2. Install AWS Session Manager CLI plugin as described in [the SSM documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).

3. In PyCharm, go to the Run/Debug Configurations (Run -> Edit Configurations...), add a new Python Debug Server.
Choose the fixed port, e. g. `12345`.

4. Take the correct version of `pydevd-pycharm` package from the configuration window 
and install it either through `requirements.txt` or by calling `pip` from your source code.

5. Add commands to connect to the Debug Server to your code:
```python
import pydevd_pycharm
pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True, suspend=True)
```
*Tip*: Check the argument's description in [the library source code](https://github.com/JetBrains/intellij-community/blob/dee787ef05d1187a71b7667652f6b25f3f573a1b/python/helpers/pydev/pydevd.py#L1663).

6. Set extra breakpoints in your code with PyCharm, if needed
7. Start the Debug Server in PyCharm
8. Submit your code to SageMaker with SSH Helper as described in previous sections.
Make sure you allow enough time for manually setting up the connection
(do not set `connection_wait_time_seconds` to 0, recommended minimum value is 600, i.e. 10 minutes).
Don't worry to set it to higher values, e.g. to 30 min, because you will be able to terminate the waiting loop 
once you connect.

9. Start the port forwarding script once SSH helper connects to SSM and starts waiting inside the training job:
```shell
sm-local-ssh-training connect <<training_job_name>>
```
It will reverse-forward the remote debugger port `12345` to your local machine's Debug Server port.
The local port `11022` will be connected to the remote SSH server port, 
to allow you easily connect with SSH from command line.  

Check the source code of the script `sm-local-ssh-training` if you want to change the default ports.

While this script is running, you may connect with SSH to the specified local port:

```bash
ssh -i ~/.ssh/sagemaker-ssh-gw -p 11022 root@localhost
```

*Tip:* If you log in to the node with SSH and don't see a `sm-sleep` process, the training script has already started 
and failed to connect to the PyCharm Debug Server, so you need to increase the `connection_wait_time_seconds`, 
otherwise the debugger will miss your breakpoints.

10. Stop the waiting loop – connect to the instance and terminate the loop.

As already mentioned in the step 8, make sure you've put enough timeout to allow the port forwarding script set up a tunnel 
before execution of your script continues.

You can use the following CLI command from your local machine to stop the waiting loop (the `sm-sleep` remote process):
```shell
sm-local-ssh-training stop-waiting
```

11. After you stop the waiting loop, your code will continue running and will connect to your PyCharm Debug server.

## <a name="remote-interpreter"></a>Remote code execution with PyCharm / VSCode over SSH

Follow the following steps from the section [Remote debugging with PyCharm Debug Server](#pycharm-debug-server):
1, 2 and 8, 9, 10.

Before terminating the waiting loop (step 10), make sure you configured and connected to SSH host and port 
`localhost:11022` from your IDE as the remote Python interpreter. 
Provide `~/.ssh/sagemaker-ssh-gw` as the private key.

 * [Instructions for PyCharm](https://www.jetbrains.com/help/pycharm/remote-debugging-with-product.html#remote-interpreter)
 * [Instructions for VSCode](https://code.visualstudio.com/docs/remote/ssh)

Note, that after you finished the waiting loop, your training script will run only once, and you will be able 
to execute additional code only while your script is running.
Once the script finishes, you will need to submit another training job and repeat the procedure again.

But there's a useful trick: submit a dummy script with the infinite loop, and while this loop will be running, you can 
run your real training script again and again with the remote interpreter.
Setting `max_run` parameter of the estimator is highly recommended in this case.

A dummy script `train_paceholder.py` may look like this:

```python
import time

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

while True:
    time.sleep(10)
```

Make also sure that you're aware of [SageMaker Managed Warm Pools](https://docs.amazonaws.cn/en_us/sagemaker/latest/dg/train-warm-pools.html) 
feature, which is also helpful in such a scenario.

## <a name="studio"></a>Local IDE integration with SageMaker Studio over SSH for PyCharm / VSCode

1. Inside SageMaker Studio checkout (unpack) this repo and run [SageMaker_SSH_IDE.ipynb](SageMaker_SSH_IDE.ipynb)

2. On the local machine, make sure that the latest AWS CLI **v2** is installed, as described in 
[the documentation for AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
   
3. Install AWS Session Manager CLI plugin as described in [the SSM documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).

4. Follow the steps 1 and 2 of the section [SSH to SageMaker training jobs](#training)
to install the library on your local machine.

5. Start SSH tunnel and port forwarding from a terminal session as follows:

```shell
sm-local-ssh-ide <<kernel_gateway_app_name>>
```

The parameter <<kernel_gateway_app_name>> is either taken from SageMaker Studio when you run notebook [SageMaker_SSH_IDE.ipynb](SageMaker_SSH_IDE.ipynb), 
or you can find it in the list of running apps in AWS Console under Amazon SageMaker -> Control Panel -> User Details.
It looks like this: `datascience-1-0-ml-g4dn-xlarge-afdb4b3051726e2ee18a399903fb`.

The local port `10022` will be connected to the remote SSH server port, to let you connect with SSH from IDE.  
In addition, the local port `8889` will be connected to remote Jupyter notebook port, the port `5901` to the remote VNC server 
and optionally the remote port `443` will be connected to your local PyCharm license server address
(check the source of the script `sm-local-ssh-ide` and modify it with your server address).

5. Connect local PyCharm or VSCode with remote Python interpreter by using `root@localhost:10022` as SSH parameters.
Also provide `~/.ssh/sagemaker-ssh-gw` as the private key.

 * [Instructions for PyCharm](https://www.jetbrains.com/help/pycharm/remote-debugging-with-product.html#remote-interpreter)
 * [Instructions for VSCode](https://code.visualstudio.com/docs/remote/ssh)

You can check that connection is working by running the SSH command in command line:

```bash
ssh -i ~/.ssh/sagemaker-ssh-gw -p 10022 root@localhost
```

Now with PyCharm or VSCode you can run and debug the code remotely inside the kernel gateway app.

Moreover, in PyCharm you may now configure a remote Jupyter Server as 
http://127.0.0.1:8889/?token=<<your_token>>. You will find the remote token as the output 
of the [SageMaker_SSH_IDE.ipynb](SageMaker_SSH_IDE.ipynb) notebook. 

You can also start the VNC session to [vnc://localhost:5901](vnc://localhost:5901) (e.g. with Screen Sharing app).

### Troubleshooting

* Check that `sshd` process is started in SageMaker Studio notebook by running a command in the image terminal:
```bash
ps xfa | grep sshd
```
If it's not started, there might be some errors in the output of the notebook, and you might get this error on 
the local machine:
```
Connection closed by UNKNOWN port 65535
```
Check carefully the notebook output in SageMaker Studio or try to stop and start SSM & services again.
