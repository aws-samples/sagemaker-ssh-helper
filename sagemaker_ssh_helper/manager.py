import logging
import time
from abc import abstractmethod, ABC

import boto3
from typing import Dict

import re


class SSMManagerBase(ABC):
    logger = logging.getLogger('sagemaker-ssh-helper:SSMManagerBase')

    def __init__(self, region_name: str = None,
                 sleep_between_retries_in_seconds: int = 10,
                 redo_attempts: int = 5) -> None:
        super().__init__()
        self.region_name = region_name or boto3.session.Session().region_name
        self.sleep_between_retries_in_seconds = sleep_between_retries_in_seconds
        self.redo_attempts = redo_attempts

    def get_instance_ids(self, arn_resource_type, arn_resource_name,
                         timeout_in_sec=0,
                         expected_count=1,
                         arn_filter_regex: str = None,
                         not_earlier_than_timestamp: int = 0):
        if arn_resource_name.startswith('mi-'):
            self.logger.warning("SageMaker resource name usually doesn't not start with 'mi-', "
                                "did you pass the SSM instance ID by mistake?")
        self.logger.info("Using AWS Region: %s", self.region_name)
        mi_ids = self.get_instance_ids_once(arn_resource_type, arn_resource_name, arn_filter_regex,
                                            not_earlier_than_timestamp)

        while not mi_ids and timeout_in_sec > 0:
            self.logger.info(f"No instance IDs found. Seconds left before time out: {timeout_in_sec}")
            time.sleep(self.sleep_between_retries_in_seconds)
            mi_ids = self.get_instance_ids_once(arn_resource_type, arn_resource_name, arn_filter_regex,
                                                not_earlier_than_timestamp)
            timeout_in_sec -= self.sleep_between_retries_in_seconds

        self.logger.info(f"Got preliminary SSM instance IDs: {mi_ids}")

        redo_attempts = self.redo_attempts
        while len(mi_ids) < expected_count and redo_attempts > 0 and timeout_in_sec > 0:
            self.logger.info(f"Re-fetch results for other instances to catchup. Attempts left: {redo_attempts}")
            time.sleep(30)
            mi_ids = self.get_instance_ids_once(arn_resource_type, arn_resource_name, arn_filter_regex,
                                                not_earlier_than_timestamp)
            redo_attempts -= 1

        self.logger.info(f"Got final SSM instance IDs: {mi_ids}")
        return mi_ids

    @abstractmethod
    def get_instance_ids_once(self, arn_resource_type, arn_resource_name, arn_filter_regex: str = None,
                              not_earlier_than_timestamp: int = 0):
        raise NotImplementedError("Abstract method")


class SSMManager(SSMManagerBase):
    PING_STATUS = '$__SSMManager__.PingStatus'

    logger = logging.getLogger('sagemaker-ssh-helper:SSMManager')

    def __init__(self, region_name=None, sleep_between_retries_in_seconds=10, redo_attempts=5,
                 clock_timestamp_override=None) -> None:
        super().__init__(region_name, sleep_between_retries_in_seconds, redo_attempts)
        self.clock_timestamp_override = clock_timestamp_override

    def list_all_instances_and_fetch_tags(self) -> Dict[str, Dict[str, str]]:
        """
        :return: a mapping of instance ID to the dictionary of tags
        """
        ssm = boto3.client('ssm', region_name=self.region_name)

        result = {}
        next_page_id = ""
        while next_page_id is not None:
            response = ssm.describe_instance_information(
                Filters=[{'Key': 'ResourceType', 'Values': ['ManagedInstance']}],
                NextToken=next_page_id,
                MaxResults=50,
            )
            next_page_id = response.get('NextToken')
            info_list = response['InstanceInformationList']
            if info_list:
                for info in info_list:
                    instance_id = info['InstanceId']
                    tags = ssm.list_tags_for_resource(ResourceType='ManagedInstance', ResourceId=instance_id)
                    tags_dict = {}
                    if 'TagList' in tags:
                        for tag in tags['TagList']:
                            tags_dict[tag['Key']] = tag['Value']
                    tags_dict[SSMManager.PING_STATUS] = info['PingStatus']
                    result[instance_id] = tags_dict

        return result

    def get_training_instance_ids(self, training_job_name, timeout_in_sec=0, expected_count=1):
        self.logger.info(f"Querying SSM instance IDs for training job {training_job_name}, "
                         f"expected instance count = {expected_count}")
        return self.get_instance_ids('training-job', training_job_name, timeout_in_sec,
                                     expected_count)

    def get_processing_instance_ids(self, processing_job_name, timeout_in_sec=0):
        self.logger.info(f"Querying SSM instance IDs for processing job {processing_job_name}")
        return self.get_instance_ids('processing-job', processing_job_name, timeout_in_sec)

    def get_endpoint_instance_ids(self, endpoint_name, timeout_in_sec=0):
        raise AssertionError("Not supported yet.")

    def get_transformer_instance_ids(self, transform_job_name, timeout_in_sec=0):
        self.logger.info(f"Querying SSM instance IDs for transform job {transform_job_name}")
        return self.get_instance_ids('transform-job', transform_job_name, timeout_in_sec)

    def get_studio_instance_ids(self, domain_id, user_profile_or_space_name, app_name, timeout_in_sec=0, not_earlier_than_timestamp: int = 0, is_user_profile=False):
        self.logger.info(f"Querying SSM instance IDs for app '{app_name}' in SageMaker Studio {'kernel gateway' if is_user_profile else 'space'}: '{user_profile_or_space_name}'")
        if not domain_id:
            arn_filter = f":app/.*/{user_profile_or_space_name}/"
        else:
            arn_filter = f":app/{domain_id}/{user_profile_or_space_name}/"

        return self.get_instance_ids('app', f"{app_name}", timeout_in_sec,
                                     arn_filter_regex=arn_filter,
                                     not_earlier_than_timestamp=not_earlier_than_timestamp)

    def get_studio_kgw_instance_ids(self, kgw_name, timeout_in_sec=0, not_earlier_than_timestamp: int = 0):
        self.logger.info(f"Querying SSM instance IDs for SageMaker Studio kernel gateway: '{kgw_name}'")
        return self.get_instance_ids('app', f"{kgw_name}", timeout_in_sec,
                                     not_earlier_than_timestamp)

    def get_studio_app_instance_ids(self, app_name, timeout_in_sec=0):
        self.logger.info(f"Querying SSM instance IDs for SageMaker Studio space {app_name}")
        return self.get_instance_ids('app', f"{app_name}", timeout_in_sec)

    def get_notebook_instance_ids(self, instance_name, timeout_in_sec=0):
        self.logger.info(f"Querying SSM instance IDs for SageMaker notebook instance {instance_name}")
        return self.get_instance_ids('notebook-instance', f"{instance_name}",
                                     timeout_in_sec)

    def get_instance_ids_once(self, arn_resource_type, arn_resource_name,
                              arn_filter_regex: str = None,
                              not_earlier_than_timestamp: int = 0):
        # TODO: use tag filter instead, for faster performance
        all_instances = self.list_all_instances_and_fetch_tags()
        result_pairs = []
        for mi_id in all_instances:
            tags = all_instances[mi_id]
            if "SSHResourceName" not in tags or "SSHResourceArn" not in tags:
                continue
            if f"/{arn_resource_name}" in tags["SSHResourceArn"] and \
                    arn_resource_name == tags["SSHResourceName"] and \
                    f":{arn_resource_type}/" in tags["SSHResourceArn"] and \
                    (not arn_filter_regex or re.search(arn_filter_regex, tags["SSHResourceArn"]) is not None):
                if "SSHTimestamp" in tags:
                    timestamp = int(tags["SSHTimestamp"])
                else:
                    timestamp = 0
                if timestamp < not_earlier_than_timestamp:
                    continue
                result_pairs.append((mi_id, timestamp))

        result_pairs.sort(key=lambda i: i[1], reverse=True)
        result = [i[0] for i in result_pairs]
        return result

    def list_expired_ssh_instances(self, expiration_days=0):
        all_instances = self.list_all_instances_and_fetch_tags()
        logging.info("Found %s instances in SSM", len(all_instances))

        expired_instances = []
        for mi_id in all_instances:
            tags = all_instances[mi_id]
            if "SSHTimestamp" in tags:
                timestamp = int(tags["SSHTimestamp"])
            else:
                timestamp = 0
            if SSMManager.PING_STATUS in tags:
                ping_status = tags[SSMManager.PING_STATUS]
            else:
                ping_status = "Online"
            if ping_status == "Online":
                continue
            if self.clock_timestamp_override is not None:
                expiration_timestamp = self.clock_timestamp_override
            else:
                expiration_timestamp = int(round(time.time()))
            expiration_timestamp -= expiration_days * 3600 * 24
            if timestamp < expiration_timestamp:
                expired_instances.append(mi_id)
                logging.info("Found expired offline SSH instance %s with timestamp %s", mi_id, timestamp)

        logging.info("Found %s expired offline SSH instances", len(expired_instances))
        return expired_instances

    def get_ssh_instance_timestamp(self, instance_id):
        ssm = boto3.client('ssm', region_name=self.region_name)
        tags = ssm.list_tags_for_resource(ResourceType='ManagedInstance', ResourceId=instance_id)
        tag_list = tags['TagList']

        for tag in tag_list:
            if tag['Key'] == 'SSHTimestamp':
                return int(tag['Value'])

        return 0
