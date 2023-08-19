import logging
import os
import socket
import subprocess
import sys
import time
from abc import ABC
from queue import Queue, Empty
from threading import Thread
from typing import Optional

import psutil


class SSMProxy(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self, ssh_listen_port: int, extra_args: str = "", region_name: str = None,
                 cloudwatch_url: str = None) -> None:
        super().__init__()
        self.cloudwatch_url = cloudwatch_url
        self.p: Optional[subprocess.Popen] = None
        self.q: Optional[Queue] = None
        self.t: Optional[Thread] = None
        self.region_name = region_name
        self.extra_args = extra_args
        self.ssh_listen_port = ssh_listen_port

    def connect_to_ssm_instance(self, instance_id) -> None:
        self.logger.info(
            f"Connecting to {instance_id} with SSM and starting SSH port forwarding "
            f"on local port {self.ssh_listen_port}"
            + (f" with extra args: '{self.extra_args}'" if self.extra_args else '')
        )

        env = os.environ.copy()
        if self.region_name:
            self.logger.info(f"Setting AWS Region for SSH: {self.region_name}")
            env["AWS_REGION"] = self.region_name
            env["AWS_DEFAULT_REGION"] = self.region_name

        env["LC_ALL"] = "C"

        # The script will create a new SSH key in ~/.ssh/sagemaker-ssh-gw
        #   and transfer the public key ~/.ssh/sagemaker-ssh-gw.pub to the instance via S3
        self.p = subprocess.Popen(
            f"sm-local-start-ssh {instance_id}"
            f" -N -L localhost:{self.ssh_listen_port}:localhost:22"
            " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            f" {self.extra_args}"
            .split(' '),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            close_fds=('posix' in sys.builtin_module_names)
        )

        def enqueue_output(out, queue):
            for line in iter(out.readline, b''):
                queue.put(line)
            out.close()

        #
        self.q = Queue()
        self.t = Thread(target=enqueue_output, args=(self.p.stdout, self.q))
        self.t.daemon = True  # thread dies with the program
        self.t.start()

        self.logger.info(f"Getting remote system information as a health check")

        output = self.run_command_with_output("uname -a 2>&1")
        output_str = output.decode("latin1")

        self.logger.info("Got output from the remote: " + output_str.replace("\n", " "))

        if not output_str.startswith("Linux"):
            raise ValueError("Failed to get system version. Got instead: " + output_str)

    def terminate_waiting_loop(self):
        self.logger.info("Terminating the remote waiting loop / sleep process")
        retval = self.run_command("sm-wait stop")
        if retval != 0:
            proc_list = self.run_command_with_output("sm-wait list")
            self.logger.info(f"List of sm-wait-processes: {proc_list}")
            raise ValueError(
                f"Return value for `sm-wait stop` is not zero: {retval}. Check remote logs for more details."
            )
        self.logger.info("Successfully terminated the waiting loop")

    def run_command(self, command):
        retval = subprocess.call(
            f"ssh -4 root@localhost -p {self.ssh_listen_port}"
            " -i ~/.ssh/sagemaker-ssh-gw"
            " -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
            f" {command}"
            .split(' '))
        return retval

    def run_command_with_output(self, command):
        self.logger.info(f"Running command and capturing output: '{command}'")
        self._wait_for_tcp_port(timeout=90)

        try:
            # Pre-fetching the key to avoid the 'Warning: Permanently added ... to the list of known hosts' in output
            retval = os.system(f"ssh-keyscan -4 -H -p {self.ssh_listen_port} localhost >>~/.ssh/known_hosts")  # nosec start_process_with_a_shell
            if retval != 0:
                self.logger.error(f"Failed to fetch host key. Return value is not zero: {retval}.")
                # No exception here, need to try the command anyway

            env = os.environ.copy()
            env["LC_ALL"] = "C"

            return subprocess.check_output(
                f"ssh -4 root@localhost -p {self.ssh_listen_port}"
                " -i ~/.ssh/sagemaker-ssh-gw"
                " -o PasswordAuthentication=no"
                " -o ConnectTimeout=10"
                f" {command}"
                .split(' '),
                stderr=subprocess.STDOUT,
                env=env
            )
        except subprocess.CalledProcessError as e:
            out = e.output.decode('latin1')
            proxy_out = self.fetch_proxy_output()
            error = ValueError(
                f"Failed to run command: {command}. "
                f"Return code: {e.returncode}. "
                f"\n---Begin proxy output:---\n{proxy_out}---End proxy output--- "
                f"\n---Begin output:---\n{out}---End output---. "
                f"Check your local log, stdout, and stderr "
                f"as well as remote logs{' at ' + self.cloudwatch_url if self.cloudwatch_url else ''} "
                f"for more details, if needed."
            )
            self.logger.error(f"Failed to run command: {e}", exc_info=error)
            raise error from e

    def fetch_proxy_output(self):
        array_of_byte_strings = []
        while True:
            try:
                line = self.q.get(timeout=2)
                array_of_byte_strings += [line]
            except Empty:
                break
        proxy_out = "".join([x.decode('latin1') for x in array_of_byte_strings])
        return proxy_out

    def _wait_for_tcp_port(self, timeout=45):
        # Use 127.0.0.1 here to avoid AF_INET6 resolution that can give errors
        self.logger.info(f"Waiting for connection to become available on 127.0.0.1:{self.ssh_listen_port}")
        is_timeout = True
        for i in range(0, timeout):
            try:
                with socket.create_connection(("127.0.0.1", self.ssh_listen_port), 2):
                    is_timeout = False
                    self.logger.info(f"Connection to 127.0.0.1:{self.ssh_listen_port} is successful")
                    break
            except ConnectionRefusedError:
                time.sleep(1)
        if is_timeout:
            self.logger.warning(f"Timeout waiting for connection on 127.0.0.1:{self.ssh_listen_port}")

    def disconnect(self):
        self.logger.info(f"Disconnecting proxy and stopping SSH port forwarding")
        parent = psutil.Process(self.p.pid)
        try:
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
        except psutil.NoSuchProcess:
            pass

    def __enter__(self, *args):
        """
        Usage:

        with SSMProxy(local_port) as ssm_proxy:
            ssm_proxy.connect_to_ssm_instance(instance_id)
            ...

        """
        return self

    def __exit__(self, *args):
        self.disconnect()
