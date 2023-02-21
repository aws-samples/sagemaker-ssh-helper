import boto3


def handler(event, context):
    ssm_client = boto3.client('ssm')
    ssm_client.update_service_setting(SettingId='/ssm/managed-instance/activation-tier',
                                      SettingValue='advanced')
    return {'statusCode': 200, 'body': 'Success.'}
