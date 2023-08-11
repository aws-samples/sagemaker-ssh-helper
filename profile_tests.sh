#!/bin/bash

set -e
set -o pipefail

python -m venv ./venv
source ./venv/bin/activate
pip install '.[test]'
id
apt-get update
apt-get install -y sudo
sm-local-configure
source tests/generate_sagemaker_config.sh
source tests/generate_accelerate_config.sh
export DEBIAN_FRONTEND=noninteractive
apt-get install -y graphviz
export AWS_REGION=eu-west-1
export AWS_DEFAULT_REGION=eu-west-1
# shellcheck disable=SC2207
sts=( $(source tests/assume-user-role.sh) )
export AWS_ACCESS_KEY_ID=${sts[0]}
export AWS_SECRET_ACCESS_KEY=${sts[1]}
export AWS_SESSION_TOKEN=${sts[2]}
cd tests
apt-get install -y firefox-esr
export MOZ_HEADLESS=1
# shellcheck disable=SC2086
pytest \
  -o sagemaker_studio_domain="$SAGEMAKER_STUDIO_DOMAIN" \
  -o sagemaker_studio_vpc_only_domain="$SAGEMAKER_STUDIO_VPC_ONLY_DOMAIN" \
  -o vpc_only_subnet="$VPC_ONLY_SUBNET" \
  -o vpc_only_security_group="$VPC_ONLY_SECURITY_GROUP" \
  -o sagemaker_role="$SAGEMAKER_ROLE" \
  -o sns_notification_topic_arn="$SNS_NOTIFICATION_TOPIC_ARN" \
  --profile --profile-svg \
  $PYTEST_EXTRA_ARGS
cd -