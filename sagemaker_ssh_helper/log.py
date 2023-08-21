import logging
import re
import time
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from sagemaker_ssh_helper.aws import AWS
from sagemaker_ssh_helper.manager import SSMManagerBase


class SSHLog(SSMManagerBase):
    logger = logging.getLogger('sagemaker-ssh-helper:SSHLog')

    def __init__(self, region_name=None, sleep_between_retries_in_seconds=10, redo_attempts=5) -> None:
        super().__init__(region_name, sleep_between_retries_in_seconds, redo_attempts)
        self.aws_console = AWS(self.region_name)

    def get_ip_addresses(self, training_job_name, retry=0):
        self.logger.info(f"Querying SSH IP addresses for job {training_job_name}")
        query = "fields @timestamp, @logStream, @message" \
                f"| filter @logStream like '{training_job_name}'" \
                "| filter @message like /SSH Helper Log IP: [0-9]+/" \
                "| sort @timestamp desc" \
                "| limit 20"
        log_group = '/aws/sagemaker/TrainingJobs'
        lines = self._query_log_group(log_group, query)
        ip_addresses = []
        for line in lines:
            message = line[2]['value']
            search = re.search('(\\d+\\.\\d+\\.\\d+\\.\\d+.*)', message)
            if search is None:
                raise AssertionError(f"Cannot find ip address in log message: {message}")
            ip = search.group(1)
            ip_addresses.append(ip)

        while not ip_addresses and retry > 0:
            self.logger.info(f"SSH Helper not yet started? Retrying. Attempts left: {retry}")
            ip_addresses = self.get_ip_addresses(training_job_name, 0)
            time.sleep(10)
            retry -= 1

        return ip_addresses

    def get_training_ssm_instance_ids(self, training_job_name, timeout_in_sec=0, expected_count=1):
        self.logger.warning("SSMManager#get_training_instance_ids() is faster and more stable")
        self.logger.info(f"Querying SSM instance IDs for training job {training_job_name}, "
                         f"expected instance count = {expected_count}")
        return self.get_ssm_instance_ids('/aws/sagemaker/TrainingJobs', training_job_name,
                                         timeout_in_sec=timeout_in_sec,
                                         expected_count=expected_count)

    def get_processing_ssm_instance_ids(self, processing_job_name, timeout_in_sec=0):
        self.logger.warning("SSMManager#get_processing_instance_ids() is faster and more stable")
        self.logger.info(f"Querying SSM instance IDs for processing job {processing_job_name}")
        return self.get_ssm_instance_ids('/aws/sagemaker/ProcessingJobs', processing_job_name,
                                         timeout_in_sec=timeout_in_sec)

    def get_endpoint_ssm_instance_ids(self, endpoint_name, timeout_in_sec=0):
        self.logger.info(f"Querying SSM instance IDs for endpoint {endpoint_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/Endpoints/{endpoint_name}', "AllTraffic/",
                                         timeout_in_sec=timeout_in_sec)

    def get_transformer_ssm_instance_ids(self, transform_job_name, timeout_in_sec=0):
        self.logger.warning("SSMManager#get_transformer_instance_ids() is faster and more stable")
        self.logger.info(f"Querying SSM instance IDs for transform job {transform_job_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/TransformJobs', transform_job_name,
                                         timeout_in_sec=timeout_in_sec)

    def get_studio_kgw_ssm_instance_ids(self, kgw_name, timeout_in_sec=0):
        self.logger.warning("SSMManager#get_studio_kgw_instance_ids() is faster and more stable")
        self.logger.info(f"Querying SSM instance IDs for SageMaker Studio kernel gateway {kgw_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/studio', f"KernelGateway/{kgw_name}",
                                         timeout_in_sec=timeout_in_sec)

    def get_instance_ids_once(self, arn_resource_type, arn_resource_name, arn_filter_regex: str = None):
        if arn_filter_regex:
            raise ValueError("Not supported for SSHLog")
        return self.get_ssm_instance_ids_once(log_group=arn_resource_type, stream_name=arn_resource_name)

    def get_ssm_instance_ids_once(self, log_group, stream_name):
        query = "fields @timestamp, @logStream, @message" \
                f"| filter @logStream like '{stream_name}'" \
                "| filter @message like /Successfully registered the instance with AWS SSM using Managed instance-id/" \
                "| sort @timestamp desc" \
                "| limit 20"
        lines = self._query_log_group(log_group, query)
        mi_ids = []
        for line in lines:
            message = line[2]['value']
            search = re.search('instance-id: (mi-.+)', message)
            if search is None:
                raise AssertionError(f"Cannot find instance id in message: {message}")
            mid = search.group(1)
            mi_ids.append(mid)
        return mi_ids

    def get_ssm_instance_ids(self, log_group, stream_name,
                             retry: int = None, sleep_between_retries_seconds: int = None,
                             timeout_in_sec: int = 900,
                             expected_count=1):
        if sleep_between_retries_seconds:
            self.logger.warning("Parameter sleep_between_retries_seconds is deprecated, "
                                "pass it to the constructor instead")
            self.sleep_between_retries_in_seconds = sleep_between_retries_seconds
        if retry:
            self.logger.warning("Parameter retry is deprecated, "
                                "use timeout_in_sec instead")
            timeout_in_sec = retry * self.sleep_between_retries_in_seconds
        return self.get_instance_ids(log_group, stream_name, timeout_in_sec, expected_count)

    def _query_log_group(self, log_group, query):
        boto_client = boto3.client('logs', region_name=self.region_name)
        try:
            start_query_response = boto_client.start_query(
                logGroupName=log_group,
                startTime=int((datetime.now() - timedelta(weeks=2)).timestamp()),
                endTime=int(datetime.now().timestamp()),
                queryString=query
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return []
            elif e.response["Error"]["Code"] == "MalformedQueryException":
                # "Query's end date and time is either before the log groups creation time ..."
                logging.warning("Probably, the endpoint log group doesn't exist yet: " + e.response["Error"]["Message"])
                return []
            else:
                raise

        query_id = start_query_response['queryId']
        response = None
        while response is None or response['status'] == 'Running':
            time.sleep(1)
            response = boto_client.get_query_results(
                queryId=query_id
            )
        lines = response['results']
        return lines

    def get_training_cloudwatch_url(self, training_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"cloudwatch/home?region={self.region_name}#" \
               f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTrainingJobs$3F" \
               f"logStreamNameFilter$3D{training_job_name}$252F"

    def get_training_metadata_url(self, training_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/jobs/{training_job_name}"

    def get_endpoint_cloudwatch_url(self, endpoint_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"cloudwatch/home?region={self.region_name}#" \
               f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FEndpoints$252F{endpoint_name}"

    def get_endpoint_metadata_url(self, endpoint_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/endpoints/{endpoint_name}"

    def get_endpoint_config_metadata_url(self, endpoint_config_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/endpointConfig/{endpoint_config_name}"

    def get_model_metadata_url(self, model_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/models/{model_name}"

    def get_processing_cloudwatch_url(self, processing_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"cloudwatch/home?region={self.region_name}#" \
               f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FProcessingJobs$3F" \
               f"logStreamNameFilter$3D{processing_job_name}$252F"

    def get_processing_metadata_url(self, processing_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/processing-jobs/{processing_job_name}"

    def get_transform_cloudwatch_url(self, transform_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"cloudwatch/home?region={self.region_name}#" \
               f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252FTransformJobs$3F" \
               f"logStreamNameFilter$3D{transform_job_name}$252F"

    def get_transform_metadata_url(self, transform_job_name):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/transform-jobs/{transform_job_name}"

    def get_ide_cloudwatch_url(self, domain, user, app_name):
        app_type = 'JupyterServer' if app_name == 'default' else 'KernelGateway'
        if user:
            return f"https://{self.aws_console.get_console_domain()}/" \
                   f"cloudwatch/home?region={self.region_name}#" \
                   f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252Fstudio" \
                   f"$3FlogStreamNameFilter$3D{domain}$252F{user}$252F{app_type}$252F{app_name}"
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"cloudwatch/home?region={self.region_name}#" \
               f"logsV2:log-groups/log-group/$252Faws$252Fsagemaker$252Fstudio" \
               f"$3FlogStreamNameFilter$3D{app_type}$252F{app_name}"

    def get_ide_metadata_url(self, domain, user):
        return f"https://{self.aws_console.get_console_domain()}/" \
               f"sagemaker/home?region={self.region_name}#" \
               f"/studio/{domain}/user/{user}"

    def count_sns_notifications(self, topic_name: str, period: timedelta):
        cloudwatch_resource = boto3.resource('cloudwatch', region_name=self.region_name)
        cloudwatch_metrics = cloudwatch_resource.metrics.filter(
            Namespace='AWS/SNS',
            MetricName='NumberOfNotificationsDelivered',
            Dimensions=[{'Name': 'TopicName', 'Value': topic_name}]
        )

        start_time = datetime.utcnow() - period
        end_time = datetime.utcnow()

        statistics = None
        for metric in cloudwatch_metrics:
            metric.load()
            statistics = metric.get_statistics(
                Dimensions=[{'Name': 'TopicName', 'Value': topic_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=['Sum']
            )
            logging.debug(metric)
            logging.debug(statistics)

        if not statistics:
            return 0
        return len(statistics['Datapoints'])
