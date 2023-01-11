import logging
import re
import time
from datetime import datetime, timedelta

import boto3


class SSHLog:
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self, region_name=None) -> None:
        super().__init__()
        self.region_name = region_name

    def get_ip_addresses(self, training_job_name, retry=0):
        SSHLog.logger.info(f"Querying SSH IP addresses for job {training_job_name}")
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
            SSHLog.logger.info(f"SSH Helper not yet started? Retrying. Attempts left: {retry}")
            ip_addresses = self.get_ip_addresses(training_job_name, 0)
            time.sleep(10)
            retry -= 1

        return ip_addresses

    def get_training_ssm_instance_ids(self, training_job_name, retry=0, expected_count=1):
        SSHLog.logger.info(f"Querying SSM instance IDs for training job {training_job_name}, "
                           f"expected instance count = {expected_count}")
        return self.get_ssm_instance_ids('/aws/sagemaker/TrainingJobs', training_job_name, retry,
                                         expected_count=expected_count)

    def get_processing_ssm_instance_ids(self, processing_job_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for processing job {processing_job_name}")
        return self.get_ssm_instance_ids('/aws/sagemaker/ProcessingJobs', processing_job_name, retry)

    def get_endpoint_ssm_instance_ids(self, endpoint_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for endpoint {endpoint_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/Endpoints/{endpoint_name}', "AllTraffic/", retry)

    def get_transformer_ssm_instance_ids(self, transform_job_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for transform job {transform_job_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/TransformJobs', transform_job_name, retry)

    def get_studio_kgw_ssm_instance_ids(self, kgw_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for SageMaker Studio kernel gateway {kgw_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/studio', f"KernelGateway/{kgw_name}", retry)

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

    def get_ssm_instance_ids(self, log_group, stream_name, retry=0, sleep_between_retries_seconds=10,
                             expected_count=1):
        mi_ids = self.get_ssm_instance_ids_once(log_group, stream_name)

        while not mi_ids and retry > 0:
            SSHLog.logger.info(f"SSH Helper not yet started? Retrying. Attempts left: {retry}")
            time.sleep(sleep_between_retries_seconds)
            mi_ids = self.get_ssm_instance_ids_once(log_group, stream_name)
            retry -= 1

        SSHLog.logger.info(f"Got preliminary SSM instance IDs: {mi_ids}")

        redo_attempts = 5
        while len(mi_ids) < expected_count and redo_attempts > 0:
            SSHLog.logger.info(f"Re-fetch results for other instances to catchup. Attempts left: {redo_attempts}")
            time.sleep(30)
            mi_ids = self.get_ssm_instance_ids_once(log_group, stream_name)
            redo_attempts -= 1

        SSHLog.logger.info(f"Got final SSM instance IDs: {mi_ids}")
        return mi_ids

    def _query_log_group(self, log_group, query):
        boto_client = boto3.client('logs', region_name=self.region_name)
        start_query_response = boto_client.start_query(
            logGroupName=log_group,
            startTime=int((datetime.now() - timedelta(weeks=2)).timestamp()),
            endTime=int(datetime.now().timestamp()),
            queryString=query
        )
        query_id = start_query_response['queryId']
        response = None
        while response is None or response['status'] == 'Running':
            time.sleep(1)
            response = boto_client.get_query_results(
                queryId=query_id
            )
        lines = response['results']
        return lines

