import logging

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.proxy import SSMProxy

logger = logging.getLogger('sagemaker-ssh-helper')


def test_sagemaker_studio(request):
    kernel_gateway_name = request.config.getini('kernel_gateway_name')

    studio_ids = SSHLog().get_studio_kgw_ssm_instance_ids(kernel_gateway_name, retry=30)
    studio_id = studio_ids[0]

    ssm_proxy = SSMProxy(10022)
    ssm_proxy.connect_to_ssm_instance(studio_id)

    services_running = ssm_proxy.run_command_with_output("sm-ssh-ide status")
    services_running = services_running.decode('latin1')

    ssm_proxy.disconnect()

    assert "127.0.0.1:8889" in services_running
    assert "127.0.0.1:5901" in services_running
