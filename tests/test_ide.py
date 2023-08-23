import logging
import os
import re
import subprocess
import time
from pathlib import Path

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
    ('test-data-science', 'ssh-test-ds1-cpu',
     'datascience-1.0', 'ml.m5.large', 'Python 3.7.10'),
    # 1 - Data Science 2.0
    ('test-data-science', 'ssh-test-ds2-cpu',
     'sagemaker-data-science-38', 'ml.m5.large', 'Python 3.8.13'),
    # 2 - Data Science 3.0
    ('test-data-science', 'ssh-test-ds3-cpu',
     'sagemaker-data-science-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 3 - Base Python 2.0
    ('test-base-python', 'ssh-test-bp2-cpu',
     'sagemaker-base-python-38', 'ml.m5.large', 'Python 3.8.12'),
    # 4 - Base Python 3.0
    ('test-base-python', 'ssh-test-bp3-cpu',
     'sagemaker-base-python-310-v1', 'ml.m5.large', 'Python 3.10.8'),

    # 5 - SparkMagic
    ('test-spark', 'ssh-test-magic-cpu',
     'sagemaker-sparkmagic', 'ml.m5.large', 'Python 3.7.10'),
    # 6 - SparkAnalytics 1.0
    ('test-spark', 'ssh-test-analytics-cpu',
     'sagemaker-sparkanalytics-v1', 'ml.m5.large', 'Python 3.8.13'),
    # 7 - SparkAnalytics 2.0
    ('test-spark', 'ssh-test-analytics2-cpu',
     'sagemaker-sparkanalytics-310-v1', 'ml.m5.large', 'Python 3.10.6'),

    # 8 - MXNet 1.9 Python 3.8 CPU Optimized
    ('test-mxnet', 'ssh-test-mx19-cpu',
     'mxnet-1.9-cpu-py38-ubuntu20.04-sagemaker-v1.0', 'ml.m5.large', 'Python 3.8.10'),
    # 9 - MXNet 1.9 Python 3.8 GPU Optimized
    # TODO: https://developer.nvidia.com/blog/updating-the-cuda-linux-gpg-repository-key/
    # ('test-mxnet', 'ssh-test-mx19-gpu',
    #  'mxnet-1.9-gpu-py38-cu112-ubuntu20.04-sagemaker-v1.0', 'ml.g4dn.xlarge', 'Python 3'),

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
     'tensorflow-2.12.0-cpu-py310-ubuntu20.04-sagemaker-v1', 'ml.m5.large', 'Python 3.10.10'),
    # 17 - TensorFlow 2.12.0 Python 3.10 GPU Optimized
    ('test-tensorflow', 'ssh-test-tf212-gpu',
     'tensorflow-2.12.0-gpu-py310-cu118-ubuntu20.04-sagemaker-v1', 'ml.g4dn.xlarge', 'Python 3.10.10'),
]


@pytest.mark.parametrize('instances', SSH_TEST_IMAGES)
def test_sagemaker_studio(instances, request):
    user, app_name, image_name, instance_type, expected_version = instances

    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), user)

    # TODO:
    #  os.env["LOCAL_USER_ID"] -> ./.sm-ssh-owner
    #  ide.upload_UI("./.sm-ssh-owner", "/.sm-ssh-owner") - cannot upload dot file in UI?

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


# noinspection DuplicatedCode
def test_studio_multiple_users(request):
    ide_ds = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-data-science')
    ide_pt = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-pytorch')

    ide_ds.create_ssh_kernel_app(
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

    studio_ids = ide_ds.get_kernel_instance_ids('ssh-test-user', timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)

        user_profile_name = ssm_proxy.run_command_with_output("sm-ssh-ide get-user-profile-name")
        user_profile_name = user_profile_name.decode('latin1')
        logger.info(f"Collected SageMaker Studio profile name: {user_profile_name}")

    ide_ds.delete_kernel_app('ssh-test-user', wait=False)
    ide_pt.delete_kernel_app('ssh-test-user', wait=False)

    assert "test-data-science" in user_profile_name


# noinspection DuplicatedCode
def test_studio_default_domain_multiple_users(request):
    ide_ds = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-data-science')
    ide_pt = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-pytorch')

    ide_ds.create_ssh_kernel_app(
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
    studio_ids = SSHIDE("", 'test-data-science').get_kernel_instance_ids('ssh-test-user', timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)

        user_profile_name = ssm_proxy.run_command_with_output("sm-ssh-ide get-user-profile-name")
        user_profile_name = user_profile_name.decode('latin1')
        logger.info(f"Collected SageMaker Studio profile name: {user_profile_name}")

    ide_ds.delete_kernel_app('ssh-test-user', wait=False)
    ide_pt.delete_kernel_app('ssh-test-user', wait=False)

    assert "test-data-science" in user_profile_name


def test_studio_notebook_in_firefox(request):
    ide = SSHIDE(request.config.getini('sagemaker_studio_domain'), 'test-data-science')

    # Get SageMaker Studio Presigned URL with API
    sagemaker_client = boto3.client('sagemaker')
    studio_pre_signed_url_response = sagemaker_client.create_presigned_domain_url(
        DomainId=ide.domain_id,
        UserProfileName=ide.user,
    )
    studio_pre_signed_url = studio_pre_signed_url_response['AuthorizedUrl']

    logging.info("Launching Firefox")
    browser = webdriver.Firefox()

    logging.info("Launching SageMaker Studio")
    browser.get(studio_pre_signed_url)

    logging.info("Waiting for SageMaker Studio to launch")
    WebDriverWait(browser, 600).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='space-menu']"))
    )
    kernel_menu_item = browser.find_element(By.XPATH, "//div[@id='space-menu']")
    logging.info(f"Found SageMaker Studio space menu item: {kernel_menu_item.text}")
    assert kernel_menu_item.text == 'test-data-science / Personal Studio'

    time.sleep(60)  # wait until obscurity of the menu items is gone and UI is fully loaded

    logging.info("Checking the kernel name")
    kernel_item = browser.find_element(
        By.XPATH,
        "//button[@class='bp3-button bp3-minimal jp-Toolbar-kernelName "
        "jp-ToolbarButtonComponent minimal jp-Button']"
    )
    logging.info(f"Found Kernel name: {kernel_item.text}")
    assert kernel_item.text == "Data Science 2.0\n|\nPython 3\n|\n2 vCPU + 8 GiB"

    dist_file_name_pattern = 'sagemaker_ssh_helper-.*-py3-none-any.whl'
    dist_file_name = [f for f in os.listdir('../dist') if re.match(dist_file_name_pattern, f)][0]
    logging.info(f"Found dist file: {dist_file_name}")

    # TODO: File -> Reload notebook from Disk
    # TODO: ide.add_new_cell([
    #  f"%%sh"
    #  f"pip3 install -U ./{dist_file_name}"
    #  ])

    upload_file(browser, os.path.abspath("../SageMaker_SSH_IDE.ipynb"))
    logging.info("IDE notebook uploaded")
    upload_file(browser, os.path.abspath(Path("../dist/", dist_file_name)))
    logging.info("Dist file uploaded")

    kernel_menu_item = browser.find_element(
        By.XPATH,
        "//div[@class='lm-MenuBar-itemLabel p-MenuBar-itemLabel' "
        "and text()='Kernel']"
    )
    logging.info(f"Found SageMaker Studio kernel menu item: {kernel_menu_item.text}")
    kernel_menu_item.click()

    logging.info("Restarting kernel and running all cells")
    restart_menu_item = browser.find_element(
        By.XPATH,
        "//div[@class='lm-Menu-itemLabel p-Menu-itemLabel' "
        "and text()='Restart Kernel and Run All Cells…']")
    logging.info(f"Found SageMaker Studio restart kernel menu item: {restart_menu_item.text}")
    restart_menu_item.click()

    # TODO: check banner if kernel is still starting, wait until banner disappears, then click restart
    # <div class="css-a7sx0c-bannerContainer sagemaker-starting-banner" id="sagemaker-notebook-banner"><div class="css-1qyc1pu-kernelStartingBannerContainer"><div><div class="css-6wrpfe-bannerSpinDiv"></div></div><div><p class="css-g9mx5z-bannerPromptSpanTitle">Starting notebook kernel...</p></div></div></div>

    restart_button = browser.find_element(
        By.XPATH,
        "//div[@class='jp-Dialog-buttonLabel' "
        "and text()='Restart']"
    )
    logging.info(f"Found SageMaker Studio restart button: {restart_button.text}")
    restart_button.click()

    time.sleep(120)  # Give time to restart

    studio_ids = ide.get_kernel_instance_ids("sagemaker-data-science-ml-m5-large-6590da95dc67eec021b14bedc036",
                                             timeout_in_sec=300)
    studio_id = studio_ids[0]

    with SSMProxy(10022) as ssm_proxy:
        ssm_proxy.connect_to_ssm_instance(studio_id)
        services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
        services_running = services_running.decode('latin1')

    # TODO: File -> Save Notebook
    # TODO: ide.download_ssh("/root/SageMaker_SSH_IDE-DS2-CPU.ipynb",
    #  "./output/SageMaker_SSH_IDE-DS2-CPU.ipynb")
    # See: https://github.com/aws-samples/sagemaker-ssh-helper/issues/18

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    # TODO: assert the services were restarted by the test, e.g., by checking the SSM timestamp
    # TODO: check if the second restart also successful

    # TODO: restart image (clean-up for the next run)
    # <button type="button" class="bp3-button bp3-minimal jp-ToolbarButtonComponent minimal jp-Button" aria-disabled="false" title="Shut down">...</button>    """

    logging.info("Closing Firefox")
    browser.close()


def upload_file(browser, file_abs_path):
    file_drop_area = browser.find_element(
        By.XPATH,
        "//ul[@class='jp-DirListing-content']"
    )
    logging.info(f"Found file browser to drop the file to: {file_drop_area.text}")
    time.sleep(2)
    file_input = browser.execute_script(Path('js/drop_studio_file.js').read_text(), file_drop_area, 0, 0)
    logging.info(f"Created a file upload item: {file_input}")
    file_input.send_keys(file_abs_path)
    time.sleep(5)  # Give time to overwrite dialog to apper
    confirm_overwrite(browser)


def confirm_overwrite(browser):
    overwrite_button = browser.find_elements(
        By.XPATH,
        "//div[@class='jp-Dialog-buttonLabel' "
        "and text()='Overwrite']"
    )
    if len(overwrite_button) > 0:
        logging.info(f"Found overwrite dialog button: {overwrite_button[0].text}")
        overwrite_button[0].click()
