import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import boto3
from sagemaker_ssh_helper.sm_ssh import SageMakerSecureShellHelper

from sagemaker_ssh_helper.ide import IDEAppStatus, SSHIDE
from sagemaker_ssh_helper.log import SSHLog
from sagemaker_ssh_helper.manager import SSMManager


class SageMakerCoreApp:
    def __init__(self):
        self.ssh_owner = None
        self.ssm_instance_id = None
        self.app_type = None
        self.ping_status = "Unknown"
        self.resource_type = None

    def set_ssm_instance_id(self, ssm_instance_id):
        self.ssm_instance_id = ssm_instance_id

    def set_ssh_owner(self, ssh_owner):
        self.ssh_owner = ssh_owner

    def set_ping_status(self, ping_status):
        self.ping_status = ping_status


class SageMakerStudioApp(SageMakerCoreApp):
    def __init__(self, domain_id: str, user_profile_name: str, app_name: str, app_type: str,
                 app_status: IDEAppStatus) -> None:
        super().__init__()
        self.app_status = app_status
        self.app_type = app_type
        self.app_name = app_name
        self.user_profile_name = user_profile_name
        self.domain_id = domain_id
        self.resource_type = "ide"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {5}.{4}.{3}.{6}".format(
            self.ping_status if self.ssm_instance_id else "-",
            self.app_type,
            str(self.app_status),
            self.domain_id,
            self.user_profile_name,
            self.app_name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMakerEndpoint(SageMakerCoreApp):
    def __init__(self, name, endpoint_status):
        super().__init__()
        self.endpoint_status = endpoint_status
        self.name = name
        self.resource_type = "inference"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {3}.{4}".format(
            self.ping_status if self.ssm_instance_id else "-",
            "InferenceEndpoint",
            str(self.endpoint_status),
            self.name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMakerTrainingJob(SageMakerCoreApp):
    def __init__(self, training_job_name: str, training_job_status: str):
        super().__init__()
        self.training_job_name = training_job_name
        self.training_job_status = training_job_status
        self.resource_type = "training"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {3}.{4}".format(
            self.ping_status if self.ssm_instance_id else "-",
            "TrainingJob",
            self.training_job_status,
            self.training_job_name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMakerProcessingJob(SageMakerCoreApp):
    def __init__(self, processing_job_name: str, processing_job_status: str):
        super().__init__()
        self.processing_job_name = processing_job_name
        self.processing_job_status = processing_job_status
        self.resource_type = "processing"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {3}.{4}".format(
            self.ping_status if self.ssm_instance_id else "-",
            "ProcessingJob",
            self.processing_job_status,
            self.processing_job_name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMakerNotebookInstance(SageMakerCoreApp):
    def __init__(self, name: str, status: str) -> None:
        super().__init__()
        self.name = name
        self.status = status
        self.resource_type = "notebook"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {3}.{4}".format(
            self.ping_status if self.ssm_instance_id else "-",
            "NotebookInstance",
            self.status,
            self.name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMakerTransformJob(SageMakerCoreApp):
    def __init__(self, transform_job_name: str, transform_job_status: str):
        super().__init__()
        self.transform_job_name = transform_job_name
        self.transform_job_status = transform_job_status
        self.resource_type = "transform"

    def __str__(self) -> str:
        return "{0:<16} {1:<18} {2:<12} {3}.{4}".format(
            self.ping_status if self.ssm_instance_id else "-",
            "InferenceJob",
            self.transform_job_status,
            self.transform_job_name,
            SageMakerSecureShellHelper.type_to_fqdn(self.resource_type)
        )


class SageMaker:
    def __init__(self, region: str = None) -> None:
        super().__init__()
        self.region = region
        self.sagemaker_client = boto3.client('sagemaker', region_name=self.region)

    def list_ide_apps(self) -> List[SageMakerStudioApp]:
        next_page_id = ""
        result = []
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_apps.html  # noqa
            if next_page_id == "":
                apps_response = self.sagemaker_client.list_apps()
            else:
                apps_response = self.sagemaker_client.list_apps(NextToken=next_page_id)
            next_page_id = apps_response.get('NextToken')
            apps_list = apps_response['Apps']
            for app_dict in apps_list:
                domain_id = app_dict["DomainId"]
                app_name = app_dict['AppName']
                app_type = app_dict['AppType']
                if 'SpaceName' in app_dict:
                    logging.info("Don't support spaces: skipping app %s of type %s" % (app_name, app_type))
                    pass
                elif app_type in ['JupyterServer', 'KernelGateway']:
                    user_profile_name = app_dict['UserProfileName']
                    logging.info("Found app %s of type %s for user %s" % (app_name, app_type, user_profile_name))
                    app_status = SSHIDE(domain_id, user_profile_name, self.region).get_app_status(app_name, app_type)
                    result.append(SageMakerStudioApp(
                        domain_id, user_profile_name,
                        app_dict['AppName'], app_dict['AppType'],
                        app_status
                    ))
                else:
                    logging.info("Unsupported app type %s" % app_type)
                    pass  # We don't support other types like 'DetailedProfiler'
        return result

    def list_endpoints(self) -> List[SageMakerEndpoint]:
        next_page_id = ""
        result = []
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_endpoints.html  # noqa
            if next_page_id == "":
                endpoints_response = self.sagemaker_client.list_endpoints()
            else:
                endpoints_response = self.sagemaker_client.list_endpoints(NextToken=next_page_id)
            next_page_id = endpoints_response.get('NextToken')
            endpoints_list = endpoints_response['Endpoints']
            for endpoint in endpoints_list:
                result.append(SageMakerEndpoint(
                    endpoint['EndpointName'],
                    endpoint['EndpointStatus']
                ))
        return result

    def list_training_jobs(self) -> List[SageMakerTrainingJob]:
        next_page_id = ""
        result = []
        oldest_creation_time = datetime.now() - timedelta(days=30)
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_training_jobs.html  # noqa
            if next_page_id == "":
                jobs_response = self.sagemaker_client.list_training_jobs(
                    CreationTimeAfter=oldest_creation_time
                )
            else:
                jobs_response = self.sagemaker_client.list_training_jobs(
                    CreationTimeAfter=oldest_creation_time, NextToken=next_page_id
                )
            next_page_id = jobs_response.get('NextToken')
            jobs_list = jobs_response['TrainingJobSummaries']
            for job in jobs_list:
                result.append(SageMakerTrainingJob(
                    job['TrainingJobName'],
                    job['TrainingJobStatus']
                ))
        return result

    def list_processing_jobs(self):
        next_page_id = ""
        result = []
        oldest_creation_time = datetime.now() - timedelta(days=30)
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_processing_jobs.html  # noqa
            if next_page_id == "":
                jobs_response = self.sagemaker_client.list_processing_jobs(
                    CreationTimeAfter=oldest_creation_time
                )
            else:
                jobs_response = self.sagemaker_client.list_processing_jobs(
                    CreationTimeAfter=oldest_creation_time, NextToken=next_page_id
                )
            next_page_id = jobs_response.get('NextToken')
            jobs_list = jobs_response['ProcessingJobSummaries']
            for job in jobs_list:
                result.append(SageMakerProcessingJob(
                    job['ProcessingJobName'],
                    job['ProcessingJobStatus']
                ))
        return result

    def list_transform_jobs(self):
        next_page_id = ""
        result = []
        oldest_creation_time = datetime.now() - timedelta(days=30)
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_transform_jobs.html  # noqa
            if next_page_id == "":
                jobs_response = self.sagemaker_client.list_transform_jobs(
                    CreationTimeAfter=oldest_creation_time
                )
            else:
                jobs_response = self.sagemaker_client.list_transform_jobs(
                    CreationTimeAfter=oldest_creation_time, NextToken=next_page_id
                )
            next_page_id = jobs_response.get('NextToken')
            jobs_list = jobs_response['TransformJobSummaries']
            for job in jobs_list:
                result.append(SageMakerTransformJob(
                    job['TransformJobName'],
                    job['TransformJobStatus']
                ))
        return result

    def list_notebook_instances(self):
        next_page_id = ""
        result = []
        while next_page_id is not None:
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/list_notebook_instances.html  # noqa
            if next_page_id == "":
                instances_response = self.sagemaker_client.list_notebook_instances()
            else:
                instances_response = self.sagemaker_client.list_notebook_instances(NextToken=next_page_id)
            next_page_id = instances_response.get('NextToken')
            instances_list = instances_response['NotebookInstances']
            for instance in instances_list:
                result.append(SageMakerNotebookInstance(
                    instance['NotebookInstanceName'],
                    instance['NotebookInstanceStatus']
                ))
        return result


class InteractiveSageMaker:
    def __init__(self, sagemaker: SageMaker, manager: SSMManager,
                 log: Optional[SSHLog] = None) -> None:
        super().__init__()
        self.sagemaker = sagemaker
        self.manager = manager
        self.log = log

    def list_studio_ide_apps_for_user_and_domain(self, domain_id: Optional[str], user_profile_name: Optional[str]):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        sagemaker_apps = self.sagemaker.list_ide_apps()
        result = []
        for sagemaker_app in sagemaker_apps:
            if (sagemaker_app.domain_id == domain_id or domain_id is None or domain_id == "") \
                    and (sagemaker_app.user_profile_name == user_profile_name or user_profile_name is None
                         or user_profile_name == ""):
                instance_id = self._find_latest_app_instance_id(managed_instances, sagemaker_app)
                if instance_id:
                    tags = managed_instances[instance_id]
                    sagemaker_app.set_ssm_instance_id(instance_id)
                    sagemaker_app.set_ssh_owner(tags['SSHOwner'])
                    sagemaker_app.set_ping_status(tags[SSMManager.PING_STATUS])
                result.append(sagemaker_app)
        return result

    def print_studio_ide_apps_for_user_and_domain(self, domain_id: str, user_profile_name: str):
        apps: List[SageMakerStudioApp] = self.list_studio_ide_apps_for_user_and_domain(domain_id, user_profile_name)
        for app in apps:
            print(app)

    def list_studio_ide_apps_for_user(self, user_profile_name: str):
        return self.list_studio_ide_apps_for_user_and_domain(None, user_profile_name)

    def list_studio_ide_apps(self):
        return self.list_studio_ide_apps_for_user_and_domain(None, None)

    @staticmethod
    def _find_latest_instance_id(managed_instances: Dict[str, Dict[str, str]],
                                 arn_substring: str, arn_tail: str):
        result = None
        max_timestamp = -1
        for managed_instance_id in managed_instances:
            tags = managed_instances[managed_instance_id]
            arn = tags['SSHResourceArn'] if 'SSHResourceArn' in tags else ''
            timestamp = int(tags['SSHTimestamp']) if 'SSHTimestamp' in tags else 0
            if (arn_substring in arn and arn.endswith(arn_tail)
                    and timestamp > max_timestamp):
                result = managed_instance_id
                max_timestamp = timestamp
        return result

    @staticmethod
    def _find_latest_app_instance_id(managed_instances: Dict[str, Dict[str, str]], sagemaker_app: SageMakerStudioApp):
        result = None
        max_timestamp = -1
        for managed_instance_id in managed_instances:
            tags = managed_instances[managed_instance_id]
            arn = tags['SSHResourceArn'] if 'SSHResourceArn' in tags else ''
            timestamp = int(tags['SSHTimestamp']) if 'SSHTimestamp' in tags else 0
            if (':app/' in arn and arn.endswith(f"/{sagemaker_app.app_name}")
                    and f"/{sagemaker_app.user_profile_name}/" in arn
                    and f"/{sagemaker_app.domain_id}/" in arn
                    and timestamp > max_timestamp):
                result = managed_instance_id
                max_timestamp = timestamp
        return result

    def print_endpoints(self):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        apps: List[SageMakerEndpoint] = self.list_endpoints(managed_instances)
        for app in apps:
            print(app)

    def list_endpoints(self, managed_instances: Dict[str, Dict[str, str]]) -> List[SageMakerEndpoint]:
        sagemaker_endpoints = self.sagemaker.list_endpoints()
        result = []
        for sagemaker_endpoint in sagemaker_endpoints:
            instance_ids = self.log.get_endpoint_ssm_instance_ids(
                sagemaker_endpoint.name,
                timeout_in_sec=0
            )
            if instance_ids:
                instance_id = instance_ids[0]
                tags = managed_instances[instance_id]
                sagemaker_endpoint.set_ssm_instance_id(instance_id)
                sagemaker_endpoint.set_ssh_owner(tags['SSHOwner'])
                sagemaker_endpoint.set_ping_status(tags[SSMManager.PING_STATUS])
            result.append(sagemaker_endpoint)
        return result

    def print_training_jobs(self):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        apps: List[SageMakerTrainingJob] = self.list_training_jobs(managed_instances)
        for app in apps:
            print(app)

    def list_training_jobs(self, managed_instances: Dict[str, Dict[str, str]]) -> List[SageMakerTrainingJob]:
        sagemaker_training_jobs = self.sagemaker.list_training_jobs()
        result = []
        for job in sagemaker_training_jobs:
            instance_id = self._find_latest_instance_id(
                managed_instances, ":training-job/", f"/{job.training_job_name}"
            )
            if instance_id:
                tags = managed_instances[instance_id]
                job.set_ssm_instance_id(instance_id)
                job.set_ssh_owner(tags['SSHOwner'])
                job.set_ping_status(tags[SSMManager.PING_STATUS])
            result.append(job)
        return result

    def print_notebook_instances(self):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        apps: List[SageMakerNotebookInstance] = self.list_notebook_instances(managed_instances)
        for app in apps:
            print(app)

    def print_processing_jobs(self):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        apps: List[SageMakerProcessingJob] = self.list_processing_jobs(managed_instances)
        for app in apps:
            print(app)

    def list_processing_jobs(self, managed_instances: Dict[str, Dict[str, str]]) -> List[SageMakerProcessingJob]:
        sagemaker_processing_jobs = self.sagemaker.list_processing_jobs()
        result = []
        for job in sagemaker_processing_jobs:
            instance_id = self._find_latest_instance_id(
                managed_instances, ":processing-job/", f"/{job.processing_job_name}"
            )
            if instance_id:
                tags = managed_instances[instance_id]
                job.set_ssm_instance_id(instance_id)
                job.set_ssh_owner(tags['SSHOwner'])
                job.set_ping_status(tags[SSMManager.PING_STATUS])
            result.append(job)
        return result

    def print_transform_jobs(self):
        managed_instances = self.manager.list_all_instances_and_fetch_tags()
        apps: List[SageMakerTransformJob] = self.list_transform_jobs(managed_instances)
        for app in apps:
            print(app)

    def list_transform_jobs(self, managed_instances: Dict[str, Dict[str, str]]) -> List[SageMakerTransformJob]:
        sagemaker_transform_jobs = self.sagemaker.list_transform_jobs()
        result = []
        for job in sagemaker_transform_jobs:
            instance_id = self._find_latest_instance_id(
                managed_instances, ":transform-job/", f"/{job.transform_job_name}"
            )
            if instance_id:
                tags = managed_instances[instance_id]
                job.set_ssm_instance_id(instance_id)
                job.set_ssh_owner(tags['SSHOwner'])
                job.set_ping_status(tags[SSMManager.PING_STATUS])
            result.append(job)
        return result

    def list_notebook_instances(self, managed_instances):
        sagemaker_notebook_instances = self.sagemaker.list_notebook_instances()
        result = []
        for instance in sagemaker_notebook_instances:
            instance_id = self._find_latest_instance_id(
                managed_instances, ":notebook-instance/", f"/{instance.name}"
            )
            if instance_id:
                tags = managed_instances[instance_id]
                instance.set_ssm_instance_id(instance_id)
                instance.set_ssh_owner(tags['SSHOwner'])
                instance.set_ping_status(tags[SSMManager.PING_STATUS])
            result.append(instance)
        return result
