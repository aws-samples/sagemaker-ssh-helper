import logging
import subprocess
import time
from abc import ABC


class SSMProxy(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self, ssh_listen_port: int, extra_args: str = "") -> None:
        super().__init__()
        self.extra_args = extra_args
        self.ssh_listen_port = ssh_listen_port

    def connect_to_ssm_instance(self, instance_id):
        self.logger.info(f"Connecting to {instance_id} with SSM and start SSH port forwarding")

        # The script will create a new SSH key in ~/.ssh/sagemaker-ssh-gw
        #   and transfer the public key ~/.ssh/sagemaker-ssh-gw.pub to the instance via S3
        p = subprocess.Popen(f"sm-local-start-ssh {instance_id}"
                             f" -L localhost:{self.ssh_listen_port}:localhost:22"
                             f" {self.extra_args}"
                             " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                             .split(' '))

        time.sleep(30)  # allow 30 sec to initialize

        self.logger.info(f"Getting remote Python version as a health check")

        output = self.run_command_with_output("python --version 2>&1")
        output_str = output.decode("latin1")

        self.logger.info("Got output from the remote: " + output_str.replace("\n", " "))

        if not output_str.startswith("Python"):
            raise AssertionError("Failed to get Python version")

        return p

    def terminate_waiting_loop(self):
        self.logger.info("Terminating the remote waiting loop / sleep process")
        retval = self.run_command("pkill -f sm-wait")

        if retval != 0:
            raise AssertionError(f"Return value is not zero: {retval}. Do you need to you increase "
                                 f"'connection_wait_time' parameter?")

    def run_command(self, command):
        retval = subprocess.call(f"ssh root@localhost -p {self.ssh_listen_port}"
                                 " -i ~/.ssh/sagemaker-ssh-gw"
                                 " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                                 f" {command}"
                                 .split(' '))
        return retval

    def run_command_with_output(self, command):
        return subprocess.check_output(f"ssh root@localhost -p {self.ssh_listen_port}"
                                       " -i ~/.ssh/sagemaker-ssh-gw"
                                       " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                                       " -o ConnectTimeout=10"
                                       f" {command}"
                                       .split(' '))
