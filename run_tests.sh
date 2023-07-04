#!/bin/bash

set -e

cat /etc/hosts
bash ./compare_release_src.sh
# Creating venv
python -m venv ./venv
source ./venv/bin/activate
# Install the package
pip freeze --all | tee pip_freeze_before.txt
pip install '.'
pip check
pip freeze --all | tee pip_freeze_after.txt
cp -r ./venv/ ./venv-lambda/
pip install '.[cdk,test]'
pip check
pip freeze --all | tee pip_freeze_after_test.txt
( diff pip_freeze_before.txt pip_freeze_after.txt || : ) | tee pip_freeze_diff.txt
( diff pip_freeze_after.txt pip_freeze_after_test.txt || : ) | tee pip_freeze_diff_test.txt
# Scanning sources
bandit -r ./sagemaker_ssh_helper/ ./tests/ *.py --skip B603,B404,B101 2>&1 | tee bandit.txt
flake8 --extend-ignore E501,F401,F541,E402 ./sagemaker_ssh_helper/ ./tests/ *.py | tee flake8.txt
# Configure local env
id
apt-get update
apt-get install -y sudo
sm-local-configure
source tests/generate_sagemaker_config.sh
# Update IAM/SSM policies
curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
export DEBIAN_FRONTEND=noninteractive
apt-get install -y nodejs
npm install -g aws-cdk
cdk --version
USER_ROLE=$GITLAB_ROLE_ARN
REGION=eu-west-1
# See https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html
cdk bootstrap aws://"$ACCOUNT_ID"/"$REGION" \
  --require-approval never
APP="python -m sagemaker_ssh_helper.cdk.tests_app"
AWS_REGION=$REGION cdk -a "$APP" deploy SSH-IAM-SSM-Stack-Tests \
    -c sagemaker_role=$SAGEMAKER_ROLE -c user_role=$USER_ROLE \
    --require-approval never
APP="python -m sagemaker_ssh_helper.cdk.iam_ssm_app"
AWS_REGION=$REGION cdk -a "$APP" deploy SSH-IAM-SSM-Stack \
    -c sagemaker_role=$SAGEMAKER_ROLE -c user_role=$USER_ROLE \
    --require-approval never
APP="python -m sagemaker_ssh_helper.cdk.advanced_tier_app"
AWS_REGION=$REGION cdk -a "$APP" deploy SSM-Advanced-Tier-Stack \
    --require-approval never
APP="python -m sagemaker_ssh_helper.cdk.low_gpu_lambda_app"
AWS_REGION=$REGION cdk -a "$APP" deploy Low-GPU-Lambda-Stack \
    -c sns_notification_topic_arn="$SNS_NOTIFICATION_TOPIC_ARN" \
    --require-approval never
REGION=eu-west-2
cdk bootstrap aws://"$ACCOUNT_ID"/"$REGION" \
  --require-approval never
APP="python -m sagemaker_ssh_helper.cdk.advanced_tier_app"
AWS_REGION=$REGION cdk -a "$APP" deploy SSM-Advanced-Tier-Stack \
    --require-approval never
unset REGION
unset APP
unset USER_ROLE
# Set bucket versioning to detect model repacking / dependencies overrides
aws s3api put-bucket-versioning \
    --bucket "$(AWS_DEFAULT_REGION=eu-west-1 bash tests/get_sagemaker_bucket.sh)" \
    --versioning-configuration Status=Enabled
aws s3api put-bucket-versioning \
    --bucket "$(AWS_DEFAULT_REGION=eu-west-2 bash tests/get_sagemaker_bucket.sh)" \
    --versioning-configuration Status=Enabled
# Set default region for tests - need both to avoid confusion because one can override another
export AWS_REGION=eu-west-1
export AWS_DEFAULT_REGION=eu-west-1
aws configure list
# Assume CI/CD role
# shellcheck disable=SC2207
sts=( $(source tests/assume-sagemaker-role.sh) )
export AWS_ACCESS_KEY_ID=${sts[0]}
export AWS_SECRET_ACCESS_KEY=${sts[1]}
export AWS_SESSION_TOKEN=${sts[2]}
# Run tests
echo "Extra args for pytest - $PYTEST_EXTRA_ARGS"
cd tests
coverage run -m pytest \
    --html=pytest_report.html --self-contained-html --junitxml=pytest_report.xml \
    -m 'not manual' \
    -o sagemaker_studio_domain=$SAGEMAKER_STUDIO_DOMAIN \
    -o sns_notification_topic_arn=$SNS_NOTIFICATION_TOPIC_ARN \
    $PYTEST_EXTRA_ARGS || EXIT_CODE=$?
coverage report
coverage xml
coverage html --show-contexts
cd -
exit $EXIT_CODE