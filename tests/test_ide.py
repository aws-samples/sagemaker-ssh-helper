import logging
import subprocess
import time

import pytest

from sagemaker_ssh_helper.ide import SSHIDE
from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.proxy import SSMProxy

logger = logging.getLogger('sagemaker-ssh-helper:test_ide')


# TODO: add a test for typing SageMaker Studio terminal commands - check conda env is activated (Selenium?)

# See https://docs.aws.amazon.com/sagemaker/latest/dg/notebooks-available-images.html .

SSH_TEST_INSTANCES = [
    # 0
    ('test-data-science', 'ssh-test-ds1-ml-m5-large',
     'datascience-1.0', 'ml.m5.large', 'Python 3.7.10'),
    # 1
    ('test-data-science', 'ssh-test-ds2-ml-m5-large',
     'sagemaker-data-science-38', 'ml.m5.large', 'Python 3.8.13'),
    # 2
    ('test-data-science', 'ssh-test-ds3-ml-m5-large',
     'sagemaker-data-science-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 3
    ('test-base-python', 'ssh-test-bp2-ml-m5-large',
     'sagemaker-base-python-38', 'ml.m5.large', 'Python 3.8.12'),
    # 4
    ('test-base-python', 'ssh-test-bp3-ml-m5-large',
     'sagemaker-base-python-310-v1', 'ml.m5.large', 'Python 3.10.8'),

    # 5
    ('test-spark', 'ssh-test-magic-ml-m5-large',
     'sagemaker-sparkmagic', 'ml.m5.large', 'Python 3.7.10'),
    # 6
    ('test-spark', 'ssh-test-analytics-ml-m5-large',
     'sagemaker-sparkanalytics-v1', 'ml.m5.large', 'Python 3.8.13'),
    # 7
    ('test-spark', 'ssh-test-analytics2-ml-m5-large',
     'sagemaker-sparkanalytics-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 8
    ('test-mxnet', 'ssh-test-mx19-ml-m5-large',
     'mxnet-1.9-cpu-py38-ubuntu20.04-sagemaker-v1.0', 'ml.m5.large', 'Python 3.8.10'),
    # 9 - TODO: https://developer.nvidia.com/blog/updating-the-cuda-linux-gpg-repository-key/
    # ('test-mxnet', 'ssh-test-mx19-ml-g4dn-xlarge',
    #  'mxnet-1.9-gpu-py38-cu112-ubuntu20.04-sagemaker-v1.0', 'ml.g4dn.xlarge', 'Python 3'),

    # 10
    ('test-pytorch', 'ssh-test-pt112-ml-m5-large',
     'pytorch-1.12-cpu-py38', 'ml.m5.large', 'Python 3.8.16'),
    # 11
    ('test-pytorch', 'ssh-test-pt112-ml-g4dn-xlarge',
     'pytorch-1.12-gpu-py38', 'ml.g4dn.xlarge', 'Python 3.8.16'),
    # 12
    ('test-pytorch', 'ssh-test-pt113-ml-m5-large',
     'pytorch-1.13-cpu-py39', 'ml.m5.large', 'Python 3.9.16'),
    # 13
    ('test-pytorch', 'ssh-test-pt113-ml-g4dn-xlarge',
     'pytorch-1.13-gpu-py39', 'ml.g4dn.xlarge', 'Python 3.9.16'),

    # 14
    ('test-tensorflow', 'ssh-test-tf211-ml-m5-large',
     'tensorflow-2.11.0-cpu-py39-ubuntu20.04-sagemaker-v1.1', 'ml.m5.large', 'Python 3.9.10'),
    # 15
    ('test-tensorflow', 'ssh-test-tf211-ml-g4dn-xlarge',
     'tensorflow-2.11.0-gpu-py39-cu112-ubuntu20.04-sagemaker-v1.1', 'ml.g4dn.xlarge', 'Python 3.9.10'),
    # 16
    ('test-tensorflow', 'ssh-test-tf212-ml-m5-large',
     'tensorflow-2.12.0-cpu-py310-ubuntu20.04-sagemaker-v1', 'ml.m5.large', 'Python 3.10.10'),
    # 17
    ('test-tensorflow', 'ssh-test-tf212-ml-g4dn-xlarge',
     'tensorflow-2.12.0-gpu-py310-cu118-ubuntu20.04-sagemaker-v1', 'ml.g4dn.xlarge', 'Python 3.10.10'),
]


@pytest.mark.parametrize('instances', SSH_TEST_INSTANCES)
def test_sagemaker_studio(instances, request):
    user, app_name, image_name, instance_type, expected_version = instances

    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user)

    ide.create_ssh_kernel_app(
        app_name,
        image_name=image_name,
        instance_type=instance_type,
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    # Need to wait here, otherwise it will try to connect to an old offline instance
    # TODO: more robust mechanism?
    time.sleep(60)

    studio_ids = ide.get_kernel_instance_ids(app_name, timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)

        services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
        services_running = services_running.decode('latin1')

        output = ssm_proxy.run_command_with_output("sm-ssh-ide env-diagnostics")
        output = output.decode('latin1')
        logger.info(f"Collected env diagnostics for {image_name}: {output}")

        python_version = ssm_proxy.run_command_with_output("sm-ssh-ide get-studio-python-version")
        python_version = python_version.decode('latin1')
        logger.info(f"Collected SageMaker Studio Python version: {python_version}")

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    assert expected_version in python_version

    ide.delete_kernel_app(app_name, wait=False)


@pytest.mark.parametrize('instances', SSH_TEST_INSTANCES)
@pytest.mark.manual
def test_sagemaker_studio_cleanup(instances, request):
    user, app_name, image_name, instance_type, expected_version = instances

    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user)
    ide.delete_kernel_app(app_name, wait=False)


def test_notebook_instance():
    notebook_ids = SSMManager().get_notebook_instance_ids("sagemaker-ssh-helper", timeout_in_sec=300)
    studio_id = notebook_ids[0]

    with SSMProxy(17022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)

        _ = ssm_proxy.run_command("apt-get install -q -y net-tools")

        services_running = ssm_proxy.run_command_with_output("netstat -nptl")
        services_running = services_running.decode('latin1')

        python_version = ssm_proxy.run_command_with_output("/opt/conda/bin/python --version")
        python_version = python_version.decode('latin1')

    assert "0.0.0.0:22" in services_running

    assert "Python 3.8" in python_version


def test_called_process_error_with_output():
    got_error = False
    try:
        # should fail, because we're not connected to a remote kernel
        subprocess.check_output("sm-local-ssh-ide run-command python --version".split(' '), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output = e.output.decode('latin1').strip()
        logger.info(f"Got error (expected): {output}")
        got_error = True
        assert output == "ssh: connect to host localhost port 10022: Connection refused"
    assert got_error
