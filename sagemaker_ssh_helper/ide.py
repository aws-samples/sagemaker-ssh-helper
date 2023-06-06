import logging
import time

import boto3
from botocore.exceptions import ClientError

from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.manager import SSMManager


class IDEAppStatus:

    def __init__(self, status, failure_reason) -> None:
        super().__init__()
        self.failure_reason = failure_reason
        self.status = status

    def is_pending(self):
        return self.status == 'Pending'

    def is_in_transition(self):
        return self.status == 'Deleting' or self.status == 'Pending'

    def is_deleting(self):
        return self.status == 'Deleting'

    def is_in_service(self):
        return self.status == 'InService'

    def is_deleted(self):
        return self.status == 'Deleted'

    def __str__(self) -> str:
        if self.failure_reason:
            return f"{self.status}, failure reason: {self.failure_reason}"
        return f"{self.status}"


class SSHIDE:
    logger = logging.getLogger('sagemaker-ssh-helper:SSHIDE')

    def __init__(self, domain: str, user: str, region_name: str = None):
        self.user = user
        self.domain = domain
        self.current_region = region_name or boto3.session.Session().region_name
        self.client = boto3.client('sagemaker', region_name=self.current_region)
        self.ssh_log = SSHLog(region_name=self.current_region)

    def create_ssh_kernel_app(self, app_name: str,
                              image_name='sagemaker-datascience-38',
                              instance_type='ml.m5.xlarge',
                              ssh_lifecycle_config='sagemaker-ssh-helper',
                              recreate=False):
        """
        Creates new kernel app with SSH lifecycle config (see kernel-lc-config.sh ).

        Images: https://docs.aws.amazon.com/sagemaker/latest/dg/notebooks-available-images.html .

        Note that doc is not always up-to-date and doesn't list full names,
          e.g., sagemaker-base-python-310 in the doc is sagemaker-base-python-310-v1 in the CreateApp API .

        :param app_name:
        :param image_name: [name] from the images doc above
        :param instance_type:
        :param ssh_lifecycle_config:
        :param recreate:
        """
        self.logger.info(f"Creating kernel app {app_name} with SSH lifecycle config {ssh_lifecycle_config}")
        self.log_urls(app_name)
        status = self.get_kernel_app_status(app_name)
        while status.is_in_transition():
            self.logger.info(f"Waiting for the final status. Current status: {status}")
            time.sleep(10)
            status = self.get_kernel_app_status(app_name)

        self.logger.info(f"Previous app status: {status}")

        if status.is_in_service():
            if recreate:
                self.delete_app(app_name, 'KernelGateway')
            else:
                raise ValueError(f"App {app_name} is in service, pass recreate=True to delete and create again.")

        # Here status is None or 'Deleted' or 'Failed'. Safe to create

        account_id = boto3.client('sts').get_caller_identity().get('Account')
        image_arn = self.resolve_sagemaker_kernel_image_arn(image_name)
        lifecycle_arn = f"arn:aws:sagemaker:{self.current_region}:{account_id}:" \
                        f"studio-lifecycle-config/{ssh_lifecycle_config}"

        self.create_app(app_name, 'KernelGateway', instance_type, image_arn, lifecycle_arn)

    def get_kernel_app_status(self, app_name: str) -> IDEAppStatus:
        """
        :param app_name:
        :return: None | 'InService' | 'Deleted' | 'Deleting' | 'Failed' | 'Pending'
        """
        response = None
        try:
            response = self.client.describe_app(
                DomainId=self.domain,
                AppType='KernelGateway',
                UserProfileName=self.user,
                AppName=app_name,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == 'ResourceNotFound':
                pass
            else:
                raise

        status = None
        failure_reason = None
        if response:
            status = response['Status']
            if 'FailureReason' in response:
                failure_reason = response['FailureReason']
        return IDEAppStatus(status, failure_reason)

    def delete_kernel_app(self, app_name, wait: bool = True):
        self.delete_app(app_name, 'KernelGateway', wait)

    def delete_app(self, app_name, app_type, wait: bool = True):
        self.logger.info(f"Deleting app {app_name}")

        try:
            _ = self.client.delete_app(
                DomainId=self.domain,
                AppType=app_type,
                UserProfileName=self.user,
                AppName=app_name,
            )
        except ClientError as e:
            # probably, already deleted
            code = e.response.get("Error", {}).get("Code")
            message = e.response.get("Error", {}).get("Message")
            self.logger.warning("ClientError code: " + code)
            self.logger.warning("ClientError message: " + message)
            if code == 'AccessDeniedException':
                raise
            return

        status = self.get_kernel_app_status(app_name)
        while wait and status.is_deleting():
            self.logger.info(f"Waiting for the Deleted status. Current status: {status}")
            time.sleep(10)
            status = self.get_kernel_app_status(app_name)
        self.logger.info(f"Status after delete: {status}")
        if wait and not status.is_deleted():
            raise ValueError(f"Failed to delete app {app_name}. Status: {status}")

    def create_app(self, app_name, app_type, instance_type, image_arn, lifecycle_arn: str = None):
        self.logger.info(f"Creating {app_type} app {app_name} on {instance_type} "
                         f"with {image_arn} and lifecycle {lifecycle_arn}")
        resource_spec = {
            'InstanceType': instance_type,
            'SageMakerImageArn': image_arn,
        }
        if lifecycle_arn:
            resource_spec['LifecycleConfigArn'] = lifecycle_arn

        _ = self.client.create_app(
            DomainId=self.domain,
            AppType=app_type,
            AppName=app_name,
            UserProfileName=self.user,
            ResourceSpec=resource_spec,
        )
        status = self.get_kernel_app_status(app_name)
        while status.is_pending():
            self.logger.info(f"Waiting for the InService status. Current status: {status}")
            time.sleep(10)
            status = self.get_kernel_app_status(app_name)

        self.logger.info(f"New app status: {status}")

        if not status.is_in_service():
            raise ValueError(f"Failed to create app {app_name}. Status: {status}")

    def resolve_sagemaker_kernel_image_arn(self, image_name):
        sagemaker_account_id = "470317259841"  # eu-west-1, TODO: check all images
        return f"arn:aws:sagemaker:{self.current_region}:{sagemaker_account_id}:image/{image_name}"

    def get_kernel_instance_ids(self, app_name, timeout_in_sec):
        self.logger.info("Resolving IDE instance IDs through SSM tags")
        self.log_urls(app_name)
        # FIXME: resolve with domain and user
        result = SSMManager().get_studio_kgw_instance_ids(app_name, timeout_in_sec)
        return result

    def log_urls(self, app_name):
        self.logger.info(f"Remote logs are at {self.get_cloudwatch_url(app_name)}")
        if self.domain and self.user:
            self.logger.info(f"Remote apps metadata is at {self.get_user_metadata_url()}")

    def get_cloudwatch_url(self, app_name):
        return self.ssh_log.get_ide_cloudwatch_url(self.domain, self.user, app_name)

    def get_user_metadata_url(self):
        return self.ssh_log.get_ide_metadata_url(self.domain, self.user)
