import logging
import os
import subprocess
import time
from abc import ABC

import psutil


class SSMProxy(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self, ssh_listen_port: int, extra_args: str = "", region_name: str = None) -> None:
        super().__init__()
        self.p = None
        self.region_name = region_name
        self.extra_args = extra_args
        self.ssh_listen_port = ssh_listen_port

    def connect_to_ssm_instance(self, instance_id) -> None:
        self.logger.info(f"Connecting to {instance_id} with SSM and start SSH forwarding "
                         f"on local port {self.ssh_listen_port} with extra args: '{self.extra_args}'")

        env = os.environ.copy()
        if self.region_name:
            self.logger.info(f"Overriding default region: {self.region_name}")
            env["AWS_REGION"] = self.region_name
            env["AWS_DEFAULT_REGION"] = self.region_name

        # The script will create a new SSH key in ~/.ssh/sagemaker-ssh-gw
        #   and transfer the public key ~/.ssh/sagemaker-ssh-gw.pub to the instance via S3
        self.p = subprocess.Popen(f"sm-local-start-ssh {instance_id}"
                                  f" -L localhost:{self.ssh_listen_port}:localhost:22"
                                  f" {self.extra_args}"
                                  " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                                  .split(' '), env=env)

        time.sleep(30)  # allow 30 sec to initialize

        self.logger.info(f"Getting remote Python version as a health check")

        output = self.run_command_with_output("python --version 2>&1")
        output_str = output.decode("latin1")

        self.logger.info("Got output from the remote: " + output_str.replace("\n", " "))

        if not output_str.startswith("Python"):
            raise AssertionError("Failed to get Python version")

    def terminate_waiting_loop(self):
        self.logger.info("Terminating the remote waiting loop / sleep process")
        retval = self.run_command("pkill -f sm-wait")

        if retval == 1:
            for i in range(0, 3):
                times_left = 3 - i
                times = "times" if times_left > 1 else "time"
                self.logger.warning(f"No sm-wait processes were found. Trying {times_left} more {times}.")
                time.sleep(15)
                proc_list = self.run_command_with_output("ps -fC sm-wait")
                self.logger.info(f"List of sm-wait-processes: {proc_list}")
                retval = self.run_command("pkill -f sm-wait")
                if retval != 1:
                    break

        if retval != 0:
            raise AssertionError(f"Return value is not zero: {retval}. Do you need to you increase "
                                 f"'connection_wait_time' parameter?")
        self.logger.info("Successfully terminated the waiting loop")

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

    def disconnect(self):
        self.logger.info(f"Disconnecting proxy and stopping SSH port forwarding")
        parent = psutil.Process(self.p.pid)
        try:
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except psutil.NoSuchProcess:
            pass
