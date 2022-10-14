import logging
import re
import time
from datetime import datetime, timedelta

import boto3


class SSHLog:
    logger = logging.getLogger('sagemaker-ssh-helper')

    def __init__(self):
        self.boto_client = boto3.client('logs')

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
            assert search is not None
            ip = search.group(1)
            ip_addresses.append(ip)

        while not ip_addresses and retry > 0:
            SSHLog.logger.info(f"SSH Helper not yet started? Retrying. Attempts left: {retry}")
            ip_addresses = self.get_ip_addresses(training_job_name, 0)
            time.sleep(10)
            retry -= 1

        return ip_addresses

    def get_training_ssm_instance_ids(self, training_job_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for training job {training_job_name}")
        return self.get_ssm_instance_ids('/aws/sagemaker/TrainingJobs', training_job_name, retry)

    def get_processing_ssm_instance_ids(self, processing_job_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for processing job {processing_job_name}")
        return self.get_ssm_instance_ids('/aws/sagemaker/ProcessingJobs', processing_job_name, retry)

    def get_endpoint_ssm_instance_ids(self, endpoint_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for endpoint {endpoint_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/Endpoints/{endpoint_name}', "AllTraffic/", retry)

    def get_studio_kgw_ssm_instance_ids(self, kgw_name, retry=0):
        SSHLog.logger.info(f"Querying SSM instance IDs for SageMaker Studio kernel gateway {kgw_name}")
        return self.get_ssm_instance_ids(f'/aws/sagemaker/studio', f"KernelGateway/{kgw_name}", retry)

    def get_ssm_instance_ids(self, log_group, stream_name, retry=0):
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
            assert search is not None
            mid = search.group(1)
            mi_ids.append(mid)

        while not mi_ids and retry > 0:
            SSHLog.logger.info(f"SSH Helper not yet started? Retrying. Attempts left: {retry}")
            mi_ids = self.get_ssm_instance_ids(log_group, stream_name, 0)
            time.sleep(10)
            retry -= 1

        SSHLog.logger.info(f"Got SSM instance IDs: {mi_ids}")

        return mi_ids

    def _query_log_group(self, log_group, query):
        start_query_response = self.boto_client.start_query(
            logGroupName=log_group,
            startTime=int((datetime.now() - timedelta(weeks=2)).timestamp()),
            endTime=int(datetime.now().timestamp()),
            queryString=query
        )
        query_id = start_query_response['queryId']
        response = None
        while response is None or response['status'] == 'Running':
            time.sleep(1)
            response = self.boto_client.get_query_results(
                queryId=query_id
            )
        lines = response['results']
        return lines

