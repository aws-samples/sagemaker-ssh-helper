import logging
import os
import re
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import pytest
from selenium.webdriver.firefox.options import Options

from sagemaker_ssh_helper.browser_automation import JupyterNotebook, SageMakerStudioAutomation
from sagemaker_ssh_helper.ide import SSHIDE
from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.proxy import SSMProxy

from selenium import webdriver

from sagemaker_ssh_helper.wrapper import SSHIDEWrapper

logger = logging.getLogger('sagemaker-ssh-helper:test_ide')


# TODO: add a test for typing SageMaker Studio terminal commands - check conda env is activated

# See https://docs.aws.amazon.com/sagemaker/latest/dg/notebooks-available-images.html .

SSH_TEST_IMAGES = [
    # 0 - Data Science
    ('test-data-science', 'ssh-test-ds1-cpu',
     'datascience-1.0', 'ml.m5.large', '** Deprecated **'),
    # 1 - Data Science 2.0
    ('test-data-science', 'ssh-test-ds2-cpu',
     'sagemaker-data-science-38', 'ml.m5.large', 'Python 3.8.18'),
    # 2 - Data Science 3.0
    ('test-data-science', 'ssh-test-ds3-cpu',
     'sagemaker-data-science-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 3 - Base Python 2.0
    ('test-base-python', 'ssh-test-bp2-cpu',
     'sagemaker-base-python-38', 'ml.m5.large', 'Python 3.8.12'),
    # 4 - Base Python 3.0
    ('test-base-python', 'ssh-test-bp3-cpu',
     'sagemaker-base-python-310-v1', 'ml.m5.large', 'Python 3.10.8'),

    # 5 - SparkMagic (deprecated)
    ('test-spark', 'ssh-test-magic-cpu',
     'sagemaker-sparkmagic', 'ml.m5.large', '** Deprecated **'),
    # 6 - SparkAnalytics 1.0
    ('test-spark', 'ssh-test-analytics-cpu',
     'sagemaker-sparkanalytics-v1', 'ml.m5.large', 'Python 3.8.13'),  # noqa
    # 7 - SparkAnalytics 2.0
    ('test-spark', 'ssh-test-analytics2-cpu',
     'sagemaker-sparkanalytics-310-v1', 'ml.m5.large', 'Python 3.10.6'),  # noqa

    # 8 - MXNet 1.9 Python 3.8 CPU Optimized
    ('test-mxnet', 'ssh-test-mx19-cpu',
     'mxnet-1.9-cpu-py38-ubuntu20.04-sagemaker-v1.0', 'ml.m5.large', '** Deprecated **'),
    # 9 - MXNet 1.9 Python 3.8 GPU Optimized
    ('test-mxnet', 'ssh-test-mx19-gpu',
     'mxnet-1.9-gpu-py38-cu112-ubuntu20.04-sagemaker-v1.0', 'ml.g4dn.xlarge', '** Deprecated **'),

    # 10 - PyTorch 1.12 Python 3.8 CPU Optimized
    ('test-pytorch', 'ssh-test-pt112-cpu',
     'pytorch-1.12-cpu-py38', 'ml.m5.large', 'Python 3.8.16'),
    # 11 - PyTorch 1.12 Python 3.8 GPU Optimized
    ('test-pytorch', 'ssh-test-pt112-gpu',
     'pytorch-1.12-gpu-py38', 'ml.g4dn.xlarge', 'Python 3.8.16'),
    # 12 - PyTorch 1.13 Python 3.9 CPU Optimized
    ('test-pytorch', 'ssh-test-pt113-cpu',
     'pytorch-1.13-cpu-py39', 'ml.m5.large', 'Python 3.9.16'),
    # 13 - PyTorch 1.13 Python 3.9 GPU Optimized
    ('test-pytorch', 'ssh-test-pt113-gpu',
     'pytorch-1.13-gpu-py39', 'ml.g4dn.xlarge', 'Python 3.9.16'),

    # 14 - TensorFlow 2.11.0 Python 3.9 CPU Optimized
    ('test-tensorflow', 'ssh-test-tf211-cpu',
     'tensorflow-2.11.0-cpu-py39-ubuntu20.04-sagemaker-v1.1', 'ml.m5.large', 'Python 3.9.10'),
    # 15 - TensorFlow 2.11.0 Python 3.9 GPU Optimized
    ('test-tensorflow', 'ssh-test-tf211-gpu',
     'tensorflow-2.11.0-gpu-py39-cu112-ubuntu20.04-sagemaker-v1.1', 'ml.g4dn.xlarge', 'Python 3.9.10'),
    # 16 - TensorFlow 2.12.0 Python 3.10 CPU Optimized
    ('test-tensorflow', 'ssh-test-tf212-cpu',
     'tensorflow-2.12.0-cpu-py310-ubuntu20.04-sagemaker-v1.0', 'ml.m5.large', 'Python 3.10.10'),
    # 17 - TensorFlow 2.12.0 Python 3.10 GPU Optimized
    ('test-tensorflow', 'ssh-test-tf212-gpu',
     'tensorflow-2.12.0-gpu-py310-cu118-ubuntu20.04-sagemaker-v1.0', 'ml.g4dn.xlarge', 'Python 3.10.10'),

    # 18 - SageMaker Distribution v0 CPU - TODO

    # 19 - SageMaker Distribution v0 GPU - TODO
]


@pytest.mark.parametrize('instances', SSH_TEST_IMAGES)
def test_sagemaker_studio(instances, request):
    user, app_name, image_name, instance_type, expected_version = instances

    if 'Deprecated' in expected_version:
        return

    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user)

    time_stamp_before_app_created = int(time.time())

    ide.create_ssh_kernel_app(
        app_name,
        image_name_or_arn=image_name,
        instance_type=instance_type,
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    time.sleep(30)  # Give time for CPU load to normalize

    ide_wrapper = SSHIDEWrapper.attach(
        ide.domain_id, ide.user, app_name,
        not_earlier_than_timestamp=time_stamp_before_app_created
    )

    with ide_wrapper.start_ssm_connection(10022, timeout=timedelta(minutes=5)) as ssm_proxy:
        ide_wrapper.print_ssh_info()

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


@pytest.mark.parametrize('instances', SSH_TEST_IMAGES)
@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Manual test")
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

        services_running = ssm_proxy.run_command_with_output("netstat -nptl")  # noqa
        services_running = services_running.decode('latin1')

        python_version = ssm_proxy.run_command_with_output("/opt/conda/bin/python --version")
        python_version = python_version.decode('latin1')

    assert "0.0.0.0:22" in services_running

    assert "Python 3.8" in python_version


def test_studio_internet_free_mode(request):
    """
    See https://docs.aws.amazon.com/sagemaker/latest/dg/studio-byoi.html
    """
    logging.info("Building BYO SageMaker Studio image for Internet-free mode")
    subprocess.check_call(
        "sm-docker build . --file tests/byoi_studio/Dockerfile.internet_free --repo smstudio-custom-ssh:custom"  # noqa
        .split(' '),
        cwd="../"
    )

    logging.info("Creating SageMaker Studio kernel gateway app")

    ide = SSHIDE(request.config.getini('sagemaker_studio_vpc_only_domain'), 'internet-free-user')

    image = ide.create_and_attach_image(
        'custom-image-ssh',
        'smstudio-custom-ssh:custom',  # noqa
        request.config.getini('sagemaker_role'),
        app_image_config_name='custom-image-config-ssh',
        kernel_specs=[
            {
                "Name": "python3",  # SHOULD match the output of `jupyter-kernelspec list` during the container build
                "DisplayName": "Python 3 - with SageMaker SSH Helper"
            }
        ],
        file_system_config={
            "MountPath": "/root",
            "DefaultUid": 0,
            "DefaultGid": 0
        }
    )

    assert image.arn is not None
    assert image.version_arn is not None

    ide.delete_app("byoi-studio-app", 'KernelGateway', wait=True)

    time_stamp_before_app_created = int(time.time())

    ide.create_ssh_kernel_app(
        "byoi-studio-app",
        image.arn,
        "ml.m5.large",
        recreate=True
    )

    ide_wrapper = SSHIDEWrapper.attach(
        ide.domain_id, ide.user, "byoi-studio-app",
        not_earlier_than_timestamp=time_stamp_before_app_created
    )

    with ide_wrapper.start_ssm_connection(10022, timeout=timedelta(minutes=5)) as ssm_proxy:
        services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
        services_running = services_running.decode('latin1')

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    ide.delete_kernel_app("byoi-studio-app", wait=False)


# noinspection DuplicatedCode
def test_studio_multiple_users(request):
    ide_tf = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-tensorflow')
    ide_pt = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-pytorch')

    ide_tf.create_ssh_kernel_app(
        'ssh-test-user',
        image_name_or_arn='sagemaker-data-science-310-v1',
        instance_type='ml.m5.large',
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    # Give a head start
    time.sleep(60)

    ide_pt.create_ssh_kernel_app(
        'ssh-test-user',
        image_name_or_arn='sagemaker-data-science-310-v1',
        instance_type='ml.m5.large',
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    # Give time for instance ID to propagate
    time.sleep(60)

    ide_wrapper = SSHIDEWrapper.attach(
        ide_tf.domain_id, ide_tf.user, "ssh-test-user"
    )

    with ide_wrapper.start_ssm_connection(10022, timeout=timedelta(minutes=5)) as ssm_proxy:
        user_profile_name = ssm_proxy.run_command_with_output("sm-ssh-ide get-user-profile-name")
        user_profile_name = user_profile_name.decode('latin1')
        logger.info(f"Collected SageMaker Studio profile name: {user_profile_name}")

    ide_tf.delete_kernel_app('ssh-test-user', wait=False)
    ide_pt.delete_kernel_app('ssh-test-user', wait=False)

    assert "test-tensorflow" in user_profile_name


# noinspection DuplicatedCode
def test_studio_default_domain_multiple_users(request):
    ide_tf = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-tensorflow')
    ide_pt = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-pytorch')

    ide_tf.create_ssh_kernel_app(
        'ssh-test-user',
        image_name_or_arn='sagemaker-data-science-310-v1',
        instance_type='ml.m5.large',
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    # Give a head start
    time.sleep(60)

    ide_pt.create_ssh_kernel_app(
        'ssh-test-user',
        image_name_or_arn='sagemaker-data-science-310-v1',
        instance_type='ml.m5.large',
        ssh_lifecycle_config='sagemaker-ssh-helper-dev',
        recreate=True
    )

    # Give time for instance ID to propagate
    time.sleep(60)

    # Empty domain "" to fetch the latest profile, useful when switching between many AWS accounts with the same profile
    ide_wrapper = SSHIDEWrapper.attach(
        "", ide_tf.user, "ssh-test-user"
    )

    with ide_wrapper.start_ssm_connection(10022, timeout=timedelta(minutes=5)) as ssm_proxy:
        user_profile_name = ssm_proxy.run_command_with_output("sm-ssh-ide get-user-profile-name")
        user_profile_name = user_profile_name.decode('latin1')
        logger.info(f"Collected SageMaker Studio profile name: {user_profile_name}")

    ide_tf.delete_kernel_app('ssh-test-user', wait=False)
    ide_pt.delete_kernel_app('ssh-test-user', wait=False)

    assert "test-tensorflow" in user_profile_name


@pytest.mark.parametrize('user_profile_name', ['test-firefox'])
def test_studio_notebook_in_firefox(request, user_profile_name):
    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user_profile_name)
    local_user_id = os.environ['LOCAL_USER_ID']
    jb_server_host = os.environ['JB_LICENSE_SERVER_HOST']

    options = Options()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", os.path.abspath("../tests/output/"))
    firefox = webdriver.Firefox(options)

    browser_automation = SageMakerStudioAutomation(ide, firefox)
    browser_automation.launch_sagemaker_studio()

    dist_file_name_pattern = 'sagemaker_ssh_helper-.*-py3-none-any.whl'
    dist_file_name = [f for f in os.listdir('../dist') if re.match(dist_file_name_pattern, f)][0]
    logging.info(f"Found dist file: {dist_file_name}")

    notebook = JupyterNotebook(Path("../SageMaker_SSH_IDE.ipynb"))
    notebook.insert_code_cell(0, [
        f"%%sh\n",
        f"pip3 install -U ./{dist_file_name}"
    ])
    notebook.insert_code_cell(0, [
        f"%%sh\n",
        f"echo '{jb_server_host}' > ~/.sm-jb-license-server"
    ])
    notebook.insert_code_cell(0, [
        f"%%sh\n",
        f"echo '{local_user_id}' > ~/.sm-ssh-owner"
    ])
    ide_notebook_path = Path("../tests/output/SageMaker_SSH_IDE-DS2-CPU.ipynb")
    notebook.save_as(ide_notebook_path)

    browser_automation.upload_file_with_overwrite(ide_notebook_path)
    browser_automation.upload_file_with_overwrite(Path("../dist/", dist_file_name))

    # rename to keep original and to compare with the output later
    os.rename("../tests/output/SageMaker_SSH_IDE-DS2-CPU.ipynb",
              "../tests/output/SageMaker_SSH_IDE-DS2-CPU-Original.ipynb")

    browser_automation.open_file_from_path("/SageMaker_SSH_IDE-DS2-CPU.ipynb", 'ml.m5.large')

    for retries in range(0, 1):
        current_time_stamp = int(time.time())

        browser_automation.restart_kernel_and_run_all_cells()

        data_science_kernel = "sagemaker-data-science-ml-m5-large-6590da95dc67eec021b14bedc036"  # noqa
        studio_id = ide.get_kernel_instance_id(
            data_science_kernel,
            timeout_in_sec=300,
            not_earlier_than_timestamp=current_time_stamp
        )
        ssh_timestamp = SSMManager().get_ssh_instance_timestamp(studio_id)

        assert ssh_timestamp > current_time_stamp

        time.sleep(120)  # Give time for agent to connect

        ide_wrapper = SSHIDEWrapper.attach(
            ide.domain_id, ide.user, data_science_kernel
        )

        with ide_wrapper.start_ssm_connection(10022, timeout=timedelta(minutes=5)) as ssm_proxy:
            services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
            services_running = services_running.decode('latin1')

        assert "127.0.0.1:8889" in services_running
        assert "127.0.0.1:5901" in services_running

    browser_automation.save_current_file()
    browser_automation.download_current_file()

    browser_automation.close_sagemaker_studio()
