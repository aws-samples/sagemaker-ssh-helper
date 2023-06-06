#!/bin/bash

# A lifecycle configuration script for SageMaker Studio Jupyter Server.
# Prepares environment to use port forwarding into kernel gateways
# through Jupyter Server Proxy extension and noVNC.
# See https://docs.aws.amazon.com/sagemaker/latest/dg/studio-lcc.html .

set -e

sudo yum install -y hostname
hostname
cat /opt/ml/metadata/resource-metadata.json

source /opt/conda/etc/profile.d/conda.sh
conda activate base
pip uninstall -y -q awscli
pip install -q sagemaker-ssh-helper

# Uncomment two lines below to update SageMaker SSH Helper to the latest dev version from main branch
#git clone https://github.com/aws-samples/sagemaker-ssh-helper.git ./sagemaker-ssh-helper/ || echo 'Already cloned'
#cd ./sagemaker-ssh-helper/ && git pull --no-rebase && pip install . && cd ..

ps xfaeww

which python
which pip

env

sm-local-configure

function _install_noVNC_linux() {
  json_value_regexp='s/^[^"]*".*": \"\(.*\)\"[^"]*/\1/'
  latest_noVNC_release=$(curl -s https://api.github.com/repos/novnc/noVNC/releases/latest)

  novnc_tag=$(echo "$latest_noVNC_release" | grep "tag_name" | sed -e "$json_value_regexp")
  echo "Got latest noVNC release tag: $novnc_tag"

  curl -sSL "https://api.github.com/repos/novnc/noVNC/tarball/$novnc_tag" -o "/tmp/noVNC.tgz"
  mkdir -p /tmp/noVNC
  tar xzf /tmp/noVNC.tgz -C /tmp/noVNC --strip-components=1
}
_install_noVNC_linux

cd /tmp/noVNC
nohup ./utils/novnc_proxy --vnc 127.0.0.1:5901 &
