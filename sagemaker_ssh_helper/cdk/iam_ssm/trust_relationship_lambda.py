import boto3


def handler(event, context):
    iam_client = boto3.client('iam')
    iam_client.update_assume_role_policy(
        RoleName="<<SAGEMAKER_ROLE_ARN>>",
        PolicyDocument='{"Version":"2012-10-17","Statement":['
                       '{"Effect":"Allow","Principal":{"Service":["sagemaker.amazonaws.com"]},"Action":["sts:AssumeRole"]},'
                       '{"Effect":"Allow","Principal":{"Service":["codebuild.amazonaws.com"]},"Action":["sts:AssumeRole"]},'
                       '{"Effect":"Allow","Principal":{"Service":["ssm.amazonaws.com"]},"Action":["sts:AssumeRole"]}'
                       ']}')
    return {'statusCode': 200, 'body': 'Success.'}
