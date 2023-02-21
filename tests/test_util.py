import distutils.dir_util
import os

import boto3
from botocore.exceptions import ClientError


def _cleanup_dir(directory, recreate=False):
    if os.path.exists(directory):
        distutils.dir_util.remove_tree(directory, verbose=True)

    if recreate:
        distutils.dir_util.mkpath(directory)


def _clean_training_opt_ml_dir():
    _cleanup_dir("./opt_ml/code/")
    _cleanup_dir("./opt_ml/model/", recreate=True)
    _cleanup_dir("./opt_ml/output/", recreate=True)


def _create_bucket_if_doesnt_exist(region, bucket_name):
    s3 = boto3.client('s3')

    bucket_exists = False
    try:
        s3.head_bucket(Bucket=bucket_name)
        bucket_exists = True
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            pass
        else:
            raise e

    if not bucket_exists:
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={
            'LocationConstraint': region
        })

    s3_resource = boto3.resource('s3')

    bucket = s3_resource.Bucket(bucket_name)
    return bucket
