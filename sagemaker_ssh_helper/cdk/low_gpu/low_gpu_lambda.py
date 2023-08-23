import os
import logging
import boto3

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHProcessorWrapper


def handler(event, context):
    if len(logging.getLogger().handlers) > 0:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)

    # See: https://docs.aws.amazon.com/sagemaker/latest/dg/automating-sagemaker-with-eventbridge.html
    logging.info(f"Got event: {event}")
    # See: https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
    logging.info(f"Event context: {context}")

    sns_notification_topic_arn = os.environ.get("SNS_NOTIFICATION_TOPIC_ARN", None)
    if not sns_notification_topic_arn:
        raise ValueError("SNS_NOTIFICATION_TOPIC_ARN is not set in Lambda environment")

    event_detail_type = 'SageMaker Processing Job State Change'
    if event['detail-type'] != event_detail_type:
        raise ValueError(f"This lambda should be triggered by an EventBridge event '{event_detail_type}'")

    processing_job_name = event['detail']['ProcessingJobName']
    ssh_processing_wrapper = SSHProcessorWrapper.attach(processing_job_name)
    logging.info(f"Triggered by processing job {processing_job_name}. "
                 f"Metadata: {ssh_processing_wrapper.get_metadata_url()} . "
                 f"Logs: {ssh_processing_wrapper.get_cloudwatch_url()} .")

    training_job_arn = event['detail']['TrainingJobArn']
    ssh_training_wrapper: SSHEstimatorWrapper = SSHEstimatorWrapper.attach_arn(training_job_arn)
    logging.info(f"Inspecting training job {training_job_arn}. "
                 f"Metadata: {ssh_training_wrapper.get_metadata_url()} . "
                 f"Logs: {ssh_training_wrapper.get_cloudwatch_url()} .")

    status_details = ''
    rule_configs_summary = ssh_training_wrapper.rule_job_summary()
    for rule_config in rule_configs_summary:
        if rule_config['RuleConfigurationName'] == 'LowGPUUtilization':
            if rule_config['RuleEvaluationStatus'] == 'IssuesFound':
                status_details = rule_config['StatusDetails']
                logging.warning(f"Found issues with GPU utilization of the training job "
                                f"{ssh_training_wrapper.training_job_name()}: {status_details}")

                logging.info(f"Send notification email and/or SMS through Amazon SNS topic {sns_notification_topic_arn}")
                sns_resource = boto3.resource('sns')
                sns_notification_topic = sns_resource.Topic(sns_notification_topic_arn)
                response = sns_notification_topic.publish(
                    Subject='Training job with low GPU utilization',
                    Message=status_details + "\n\n" +
                            "Training job metadata URL:\n" +
                            ssh_training_wrapper.get_metadata_url()
                )
                logging.info(f"SNS response: {response}")

                # Optionally, stop the job (not recommended, better to keep notifications only)
                # ssh_training_wrapper.stop_training_job()

    if status_details == '':
        logging.info(f"No issues found with GPU utilization of training job "
                     f"{ssh_training_wrapper.training_job_name()}")

    return {'statusCode': 200, 'body': 'Success.'}
