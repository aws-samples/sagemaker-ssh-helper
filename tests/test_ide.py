import logging

from sagemaker_ssh_helper.manager import SSMManager
from sagemaker_ssh_helper.proxy import SSMProxy

logger = logging.getLogger('sagemaker-ssh-helper')


def test_sagemaker_studio(request):
    kernel_gateway_name = request.config.getini('kernel_gateway_name')

    studio_ids = SSMManager().get_studio_kgw_instance_ids(kernel_gateway_name, timeout_in_sec=300)
    studio_id = studio_ids[0]

    ssm_proxy = SSMProxy(10022)
    ssm_proxy.connect_to_ssm_instance(studio_id)

    services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
    services_running = services_running.decode('latin1')

    python_version = ssm_proxy.run_command_with_output("/opt/conda/bin/python --version")
    python_version = python_version.decode('latin1')

    ssm_proxy.disconnect()

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running

    assert "Python 3.8" in python_version


def test_notebook_instance(request):
    notebook_ids = SSMManager().get_notebook_instance_ids("sagemaker-ssh-helper", timeout_in_sec=300)
    studio_id = notebook_ids[0]

    ssm_proxy = SSMProxy(17022)
    ssm_proxy.connect_to_ssm_instance(studio_id)

    _ = ssm_proxy.run_command("apt-get install -q -y net-tools")

    services_running = ssm_proxy.run_command_with_output("netstat -nptl")
    services_running = services_running.decode('latin1')

    python_version = ssm_proxy.run_command_with_output("/opt/conda/bin/python --version")
    python_version = python_version.decode('latin1')

    ssm_proxy.disconnect()

    assert "0.0.0.0:22" in services_running

    assert "Python 3.8" in python_version
