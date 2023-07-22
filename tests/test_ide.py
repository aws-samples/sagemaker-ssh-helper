import logging
import os
import subprocess
import time

import pytest
from selenium.webdriver.support.wait import WebDriverWait

from sagemaker_ssh_helper.ide import SSHIDE
from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.proxy import SSMProxy

from selenium import webdriver

from selenium.webdriver.common.by import By

import boto3

from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger('sagemaker-ssh-helper:test_ide')


# TODO: add a test for typing SageMaker Studio terminal commands - check conda env is activated (Selenium?)

# See https://docs.aws.amazon.com/sagemaker/latest/dg/notebooks-available-images.html .

SSH_TEST_IMAGES = [
    # 0 - Data Science
    ('test-data-science', 'ssh-test-ds1-ml-m5-large',
     'datascience-1.0', 'ml.m5.large', 'Python 3.7.10'),
    # 1 - Data Science 2.0
    ('test-data-science', 'ssh-test-ds2-ml-m5-large',
     'sagemaker-data-science-38', 'ml.m5.large', 'Python 3.8.13'),
    # 2 - Data Science 3.0
    ('test-data-science', 'ssh-test-ds3-ml-m5-large',
     'sagemaker-data-science-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 3 - Base Python 2.0
    ('test-base-python', 'ssh-test-bp2-ml-m5-large',
     'sagemaker-base-python-38', 'ml.m5.large', 'Python 3.8.12'),
    # 4 - Base Python 3.0
    ('test-base-python', 'ssh-test-bp3-ml-m5-large',
     'sagemaker-base-python-310-v1', 'ml.m5.large', 'Python 3.10.8'),

    # 5 - SparkMagic
    ('test-spark', 'ssh-test-magic-ml-m5-large',
     'sagemaker-sparkmagic', 'ml.m5.large', 'Python 3.7.10'),
    # 6 - SparkAnalytics 1.0
    ('test-spark', 'ssh-test-analytics-ml-m5-large',
     'sagemaker-sparkanalytics-v1', 'ml.m5.large', 'Python 3.8.13'),
    # 7 - SparkAnalytics 2.0
    ('test-spark', 'ssh-test-analytics2-ml-m5-large',
     'sagemaker-sparkanalytics-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 8 - MXNet 1.9 Python 3.8 CPU Optimized
    ('test-mxnet', 'ssh-test-mx19-ml-m5-large',
     'mxnet-1.9-cpu-py38-ubuntu20.04-sagemaker-v1.0', 'ml.m5.large', 'Python 3.8.10'),
    # 9 - MXNet 1.9 Python 3.8 GPU Optimized
    # TODO: https://developer.nvidia.com/blog/updating-the-cuda-linux-gpg-repository-key/
    # ('test-mxnet', 'ssh-test-mx19-ml-g4dn-xlarge',
    #  'mxnet-1.9-gpu-py38-cu112-ubuntu20.04-sagemaker-v1.0', 'ml.g4dn.xlarge', 'Python 3'),

    # 10 - PyTorch 1.12 Python 3.8 CPU Optimized
    ('test-pytorch', 'ssh-test-pt112-ml-m5-large',
     'pytorch-1.12-cpu-py38', 'ml.m5.large', 'Python 3.8.16'),
    # 11 - PyTorch 1.12 Python 3.8 GPU Optimized
    ('test-pytorch', 'ssh-test-pt112-ml-g4dn-xlarge',
     'pytorch-1.12-gpu-py38', 'ml.g4dn.xlarge', 'Python 3.8.16'),
    # 12 - PyTorch 1.13 Python 3.9 CPU Optimized
    ('test-pytorch', 'ssh-test-pt113-ml-m5-large',
     'pytorch-1.13-cpu-py39', 'ml.m5.large', 'Python 3.9.16'),
    # 13 - PyTorch 1.13 Python 3.9 GPU Optimized
    ('test-pytorch', 'ssh-test-pt113-ml-g4dn-xlarge',
     'pytorch-1.13-gpu-py39', 'ml.g4dn.xlarge', 'Python 3.9.16'),

    # 14 - TensorFlow 2.11.0 Python 3.9 CPU Optimized
    ('test-tensorflow', 'ssh-test-tf211-ml-m5-large',
     'tensorflow-2.11.0-cpu-py39-ubuntu20.04-sagemaker-v1.1', 'ml.m5.large', 'Python 3.9.10'),
    # 15 - TensorFlow 2.11.0 Python 3.9 GPU Optimized
    ('test-tensorflow', 'ssh-test-tf211-ml-g4dn-xlarge',
     'tensorflow-2.11.0-gpu-py39-cu112-ubuntu20.04-sagemaker-v1.1', 'ml.g4dn.xlarge', 'Python 3.9.10'),
    # 16 - TensorFlow 2.12.0 Python 3.10 CPU Optimized
    ('test-tensorflow', 'ssh-test-tf212-ml-m5-large',
     'tensorflow-2.12.0-cpu-py310-ubuntu20.04-sagemaker-v1', 'ml.m5.large', 'Python 3.10.10'),
    # 17 - TensorFlow 2.12.0 Python 3.10 GPU Optimized
    ('test-tensorflow', 'ssh-test-tf212-ml-g4dn-xlarge',
     'tensorflow-2.12.0-gpu-py310-cu118-ubuntu20.04-sagemaker-v1', 'ml.g4dn.xlarge', 'Python 3.10.10'),
]


@pytest.mark.parametrize('instances', SSH_TEST_IMAGES)
def test_sagemaker_studio(instances, request):
    user, app_name, image_name, instance_type, expected_version = instances

    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user)

    ide.create_ssh_kernel_app(
        app_name,
        image_name_or_arn=image_name,
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


def test_studio_internet_free_mode(request):
    """
    See https://docs.aws.amazon.com/sagemaker/latest/dg/studio-byoi.html
    """
    logging.info("Building BYO SageMaker Studio image for Internet-free mode")
    subprocess.check_call(
        "sm-docker build . --file tests/byoi_studio/Dockerfile.internet_free --repo smstudio-custom-ssh:custom"
        .split(' '),
        cwd="../"
    )

    logging.info("Creating SageMaker Studio kernel gateway app")

    ide = SSHIDE(request.config.getini('sagemaker_studio_vpc_only_domain'), 'internet-free-user')

    image = ide.create_and_attach_image(
        'custom-image-ssh',
        'smstudio-custom-ssh:custom',
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

    ide.create_ssh_kernel_app(
        "byoi-studio-app",
        image.arn,
        "ml.m5.large",
        recreate=True
    )

    time.sleep(60)

    studio_ids = ide.get_kernel_instance_ids("byoi-studio-app", timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)
        services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
        services_running = services_running.decode('latin1')

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    ide.delete_kernel_app("byoi-studio-app", wait=False)


@pytest.mark.skipif(os.getenv('PYTEST_IGNORE_SKIPS', "false") == "false",
                    reason="Manual test")
def test_studio_notebook_in_firefox(request):
    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-data-science')

    # Get SageMaker Studio Presigned URL with API
    sagemaker_client = boto3.client('sagemaker')
    studio_pre_signed_url_response = sagemaker_client.create_presigned_domain_url(
        DomainId=ide.domain_id,
        UserProfileName=ide.user,
    )
    studio_pre_signed_url = studio_pre_signed_url_response['AuthorizedUrl']
    logging.info(f"Studio pre-signed URL: {studio_pre_signed_url}")

    logging.info("Launching Firefox")
    browser = webdriver.Firefox()

    logging.info("Launching SageMaker Studio")
    browser.get(studio_pre_signed_url)

    logging.info("Checking for SageMaker Studio in Firefox")
    assert "JupyterLab" in browser.title

    logging.info("Waiting for SageMaker Studio to launch")
    kernel_menu_xpath = "//div[@class='lm-MenuBar-itemLabel p-MenuBar-itemLabel' " \
                        "and text()='Kernel']"
    WebDriverWait(browser, 30).until(
        EC.presence_of_element_located((By.XPATH, kernel_menu_xpath))
    )
    time.sleep(15)  # wait until obscurity of the menu item is gone and UI is fully loaded
    kernel_menu_item = browser.find_element(By.XPATH, kernel_menu_xpath)
    logging.info(f"Found SageMaker Studio kernel menu item: {kernel_menu_item}")
    kernel_menu_item.click()

    logging.info("Restarting kernel and running all cells")
    restart_menu_xpath = "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' " \
                         "and text()='Restart Kernel and Run All Cells…']"
    restart_menu_item = browser.find_element(By.XPATH, restart_menu_xpath)
    logging.info(f"Found SageMaker Studio restart kernel menu item: {restart_menu_item}")
    restart_menu_item.click()

    # TODO: check if kernel has been already started, also check that it's a correct kernel and instance type
    # <button type="button" class="bp3-button bp3-minimal jp-Toolbar-kernelName jp-ToolbarButtonComponent minimal jp-Button" aria-disabled="false" title="Switch kernel"><span class="bp3-button-text"><span class="jp-ToolbarButtonComponent-label">No Kernel</span></span></button>
    # <button type="button" class="bp3-button bp3-minimal jp-Toolbar-kernelName jp-ToolbarButtonComponent minimal jp-Button" aria-disabled="false" title=""><span class="bp3-button-text"><span class="jp-ToolbarButtonComponent-label" style="display: none;">Python 3 (Data Science 2.0)</span></span><span class="css-1jyspix newButtonTarget"><span class="css-1vcsdgo">Data Science 2.0</span><span class="css-pyakce">|</span><span>Python 3</span><span class="css-pyakce">|</span><span>2 vCPU +  4 GiB</span></span></button>

    # TODO: check banner if kernel is still starting, wait until banner disappears, then click restart
    # <div class="css-a7sx0c-bannerContainer sagemaker-starting-banner" id="sagemaker-notebook-banner"><div class="css-1qyc1pu-kernelStartingBannerContainer"><div><div class="css-6wrpfe-bannerSpinDiv"></div></div><div><p class="css-g9mx5z-bannerPromptSpanTitle">Starting notebook kernel...</p></div></div></div>

    restart_button_xpath = "//div[@class='jp-Dialog-buttonLabel' " \
                           "and text()='Restart']"
    restart_button = browser.find_element(By.XPATH, restart_button_xpath)
    logging.info(f"Found SageMaker Studio restart button: {restart_button}")
    restart_button.click()

    time.sleep(120)  # Give time to restart

    studio_ids = ide.get_kernel_instance_ids("sagemaker-data-science-ml-m5-large-6590da95dc67eec021b14bedc036",
                                             timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)
        services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
        services_running = services_running.decode('latin1')

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    # TODO: assert the services were restarted by the test, e.g., by checking the SSM timestamp
    # TODO: check if the second restart also successful

    # TODO: restart image (clean-up for the next run)
    # <button type="button" class="bp3-button bp3-minimal jp-ToolbarButtonComponent minimal jp-Button" aria-disabled="false" title="Shut down">...</button>    """

    logging.info("Closing Firefox")
    browser.close()
