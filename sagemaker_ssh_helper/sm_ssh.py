"""
The high-level interface for SageMaker SSH Helper.
Run `sm-ssh -h` for the help.

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""

import argparse
import os
import subprocess
import sys

from boto3 import Session


class SageMakerSecureShellHelper:
    resources = ["ide", "space-ide", "training", "processing", "transform", "inference", "notebook"]

    @staticmethod
    def fqdn_to_type(fqdn: str) -> str:
        if fqdn.endswith(".studio.sagemaker") or fqdn == "studio.sagemaker":
            return "ide"
        elif fqdn.endswith(".space.sagemaker") or fqdn == "space.sagemaker":
            return "space-ide"
        elif fqdn.endswith(".notebook.sagemaker") or fqdn == "notebook.sagemaker":
            return "notebook"
        elif fqdn.endswith(".training.sagemaker") or fqdn == "training.sagemaker":
            return "training"
        elif fqdn.endswith(".processing.sagemaker") or fqdn == "processing.sagemaker":
            return "processing"
        elif fqdn.endswith(".transform.sagemaker") or fqdn == "transform.sagemaker":
            return "transform"
        elif fqdn.endswith(".inference.sagemaker") or fqdn == "inference.sagemaker":
            return "inference"
        else:
            return "all"

    @classmethod
    def type_to_fqdn(cls, resource_type):
        if resource_type == "ide":
            return "studio.sagemaker"
        elif resource_type == "space-ide":
            return "space.sagemaker"
        elif resource_type == "notebook":
            return "notebook.sagemaker"
        elif resource_type == "training":
            return "training.sagemaker"
        elif resource_type == "processing":
            return "processing.sagemaker"
        elif resource_type == "transform":
            return "transform.sagemaker"
        elif resource_type == "inference":
            return "inference.sagemaker"
        else:
            raise Exception(f"Unknown resource type: {resource_type}")

    @staticmethod
    def fqdn_to_name(fqdn: str):
        if fqdn.count('.') > 1:
            return fqdn.split('.')[0]
        else:
            return ''

    @staticmethod
    def fqdn_to_studio_domain_id(fqdn: str) -> str:
        if fqdn.count('.') == 4:
            return fqdn.split('.')[2]
        if fqdn.count('.') == 3:
            return fqdn.split('.')[1]
        else:
            return ''

    @staticmethod
    def fqdn_to_studio_user_or_space_name(fqdn: str) -> str:
        if fqdn.count('.') == 4:
            return fqdn.split('.')[1]
        if fqdn.count('.') == 3:
            return fqdn.split('.')[0]
        else:
            return ''

    @classmethod
    def _get_arguments(cls, fqdn, resource, command):
        domain_id = ""
        user_profile_or_space_name = ""

        if resource.endswith("ide"):
            domain_id = SageMakerSecureShellHelper.fqdn_to_studio_domain_id(fqdn)
            user_profile_or_space_name = SageMakerSecureShellHelper.fqdn_to_studio_user_or_space_name(fqdn)
        if domain_id and user_profile_or_space_name:
            arguments = ["bash", "sm-local-ssh-ide", "--domain-id", domain_id, "--user-profile-or-space-name", user_profile_or_space_name]
        else:
            arguments = ["bash", f"sm-local-ssh-{resource}"]

        if resource == "ide":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "app"))
        elif resource == "space-ide":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "space-app"))
        elif resource == "notebook":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "notebook"))
        elif resource == "training":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "job"))
        elif resource == "processing":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "job"))
        elif resource == "transform":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "job"))
        elif resource == "inference":
            arguments.append(cls._sm_ssh_command_to_local_ssh_command(command, "endpoint"))
        else:
            raise ValueError(f"ERROR: unknown resource type: {resource}")

        return arguments

    @staticmethod
    def _sm_ssh_command_to_local_ssh_command(command, name_type):
        if command == "start-proxy":
            return f"proxy-host"
        elif command == "connect":
            return f"connect-{name_type}"
        else:
            raise ValueError(f"ERROR: unknown name type: {name_type}")

    def list(self, fqdn):
        self.print_version()
        print(f"Listing SageMaker instances for {fqdn}")
        resource_type = SageMakerSecureShellHelper.fqdn_to_type(fqdn)
        region = Session().region_name
        print(f"  Region: {region}")
        print(f"  Type: {resource_type}")
        print(f"  FQDN: {fqdn}")

        import logging
        logging.basicConfig(level=logging.WARNING)
        from sagemaker_ssh_helper.interactive_sagemaker import InteractiveSageMaker, SageMaker
        from sagemaker_ssh_helper.manager import SSMManager
        from sagemaker_ssh_helper.log import SSHLog
        manager = SSMManager(redo_attempts=0)
        log = SSHLog(redo_attempts=0)
        sagemaker = SageMaker()
        interactive_sagemaker = InteractiveSageMaker(sagemaker, manager, log)

        for resource in self.resources:
            if resource_type == resource or resource_type == "all":
                # if-then-else branch for every resource type:
                if resource.endswith("ide"):
                    domain_id = SageMakerSecureShellHelper.fqdn_to_studio_domain_id(fqdn)
                    user_profile_or_space_name = SageMakerSecureShellHelper.fqdn_to_studio_user_or_space_name(fqdn)
                    interactive_sagemaker.print_studio_ide_apps_for_user_and_domain(domain_id, user_profile_or_space_name)
                    break
                elif resource == "notebook":
                    interactive_sagemaker.print_notebook_instances()
                elif resource == "training":
                    interactive_sagemaker.print_training_jobs()
                elif resource == "processing":
                    interactive_sagemaker.print_processing_jobs()
                elif resource == "transform":
                    interactive_sagemaker.print_transform_jobs()
                elif resource == "inference":
                    interactive_sagemaker.print_endpoints()
                else:
                    raise ValueError(f"ERROR: unknown resource type: {resource}")

    @staticmethod
    def print_version():
        print(f"SageMaker SSH Helper v{read_version()}")

    @staticmethod
    def start_proxy(fqdn):
        resource_type = SageMakerSecureShellHelper.fqdn_to_type(fqdn)
        if resource_type == "all":
            print("ERROR: resource type 'all' is only valid for 'list' command")
            return
        resource_name = SageMakerSecureShellHelper.fqdn_to_name(fqdn)
        if resource_name == "":
            print("ERROR: empty resource type is only valid for 'list' command")
            return
        arguments = SageMakerSecureShellHelper._get_arguments(fqdn, resource_type, "start-proxy")
        arguments.append(fqdn)
        subprocess.check_call(arguments, env=os.environ, bufsize=0)

    def connect_ports(self, fqdn, extra_args):
        self.print_version()
        print(f"Connecting to SageMaker containers for {fqdn} using SSH")
        resource_type = SageMakerSecureShellHelper.fqdn_to_type(fqdn)
        print(f"  Type: {resource_type}")
        print(f"  FQDN: {fqdn}")

        if resource_type == "all":
            print("ERROR: resource type 'all' is only valid for 'list' command")
            return

        resource_name = SageMakerSecureShellHelper.fqdn_to_name(fqdn)
        print(f"  Resource: {resource_name}")

        if resource_name == "":
            print("ERROR: empty resource type is only valid for 'list' command")
            return

        arguments = self._get_arguments(fqdn, resource_type, "connect")
        arguments.append(resource_name)
        subprocess.check_call(arguments + extra_args, env=os.environ, bufsize=0)


def read_version():
    with open(os.path.join(os.path.dirname(__file__), 'VERSION'), 'r') as f:
        return f.read().strip()


def main():
    # parse arguments
    parser = argparse.ArgumentParser(
        description='SageMaker SSH Helper "army-knife" tool to securely connect to Amazon SageMaker training jobs, '
                    'processing jobs, and realtime inference endpoints as well as SageMaker Studio Notebooks '
                    'and SageMaker Notebook Instances for fast interactive experimentation, '
                    'remote debugging, and advanced troubleshooting'
    )
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s v{read_version()}')
    parser.add_argument('command', choices=['list', 'start-proxy', 'connect'])
    parser.add_argument('fqdn', nargs='?', default='sagemaker',
                        help='fully qualified domain name, e.g., ssh-training-job.training.sagemaker, '
                             'studio.sagemaker, etc. (default: sagemaker)')
    args, extra_args = parser.parse_known_args()

    os.environ["SM_SSH_PYTHON"] = sys.executable

    if args.command == 'list':
        SageMakerSecureShellHelper().list(args.fqdn)
    elif args.command == 'start-proxy':
        SageMakerSecureShellHelper.start_proxy(args.fqdn)
    elif args.command == 'connect':
        SageMakerSecureShellHelper().connect_ports(args.fqdn, extra_args)


if __name__ == '__main__':
    main()
