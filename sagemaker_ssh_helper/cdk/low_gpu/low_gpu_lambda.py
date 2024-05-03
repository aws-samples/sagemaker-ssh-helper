import os
import logging
import boto3

from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper, SSHProcessorWrapper


def handler(event, context):
    if len(logging.getLogger().handlers) > 0:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.DEBUG)

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
    logging.info(f"Triggered by processing job: {processing_job_name}. "
                 f"Metadata: {ssh_processing_wrapper.get_metadata_url()} . "
                 f"Logs: {ssh_processing_wrapper.get_cloudwatch_url()} .")

    image_uri = event['detail']['AppSpecification']['ImageUri']
    job_status = event['detail']['ProcessingJobStatus']
    exit_message = event['detail']['ExitMessage']
    rule_to_invoke = event['detail']['Environment']['rule_to_invoke']

    if '/sagemaker-debugger-rules:latest' not in image_uri:
        logging.info("Not a SageMaker Debugger processing job")
        return {'statusCode': 200, 'body': 'Not a debugger job.'}

    if rule_to_invoke != 'LowGPUUtilization':
        logging.info("Not a LowGPUUtilization profiler rule")
        return {'statusCode': 200, 'body': 'Not a lowGPUUtilization profiler rule.'}

    if job_status != 'Completed':
        logging.info("Profiler job hasn't been completed yet. Skipping check.")
        return {'statusCode': 200, 'body': 'Job is not yet completed.'}

    training_job_arn = event['detail']['TrainingJobArn']
    ssh_training_wrapper: SSHEstimatorWrapper = SSHEstimatorWrapper.attach_arn(training_job_arn)
    logging.info(f"Training job ARN: {training_job_arn}. "
                 f"Metadata: {ssh_training_wrapper.get_metadata_url()} . "
                 f"Logs: {ssh_training_wrapper.get_cloudwatch_url()} .")

    if 'RuleEvaluationConditionMet' not in exit_message:
        logging.info(f"No issues found with GPU utilization of training job "
                     f"{ssh_training_wrapper.training_job_name()}")
        return {'statusCode': 200, 'body': 'No issues.'}

    logging.warning(f"Found issues with GPU utilization of the training job "
                    f"{ssh_training_wrapper.training_job_name()}: {exit_message}")

    logging.info(f"Send notification email and/or SMS through Amazon SNS topic {sns_notification_topic_arn}")
    sns_resource = boto3.resource('sns')
    logging.debug("Boto3 resource created.")
    sns_notification_topic = sns_resource.Topic(sns_notification_topic_arn)
    logging.debug("SNS topic created.")
    response = sns_notification_topic.publish(
        Subject='Training job with low GPU utilization',
        Message=exit_message + "\n\n" +
                "Training job metadata URL:\n" +
                ssh_training_wrapper.get_metadata_url()
    )
    logging.info(f"SNS response: {response}")

    # Optionally, stop the job (not recommended, better to keep notifications only)
    # ssh_training_wrapper.stop_training_job()

    return {'statusCode': 200, 'body': 'Low GPU utilization issues found.'}
