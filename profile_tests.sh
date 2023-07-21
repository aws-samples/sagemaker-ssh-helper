#!/bin/bash

set -e

python -m venv ./venv
source ./venv/bin/activate
pip install '.[test]'
id
apt-get update
apt-get install -y sudo
sm-local-configure
source tests/generate_sagemaker_config.sh
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
pytest \
  -m 'not manual' \
  -o sagemaker_studio_domain=$SAGEMAKER_STUDIO_DOMAIN \
  --profile --profile-svg \
  $PYTEST_EXTRA_ARGS
cd -