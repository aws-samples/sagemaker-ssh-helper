#!/bin/bash

# A lifecycle configuration script for SageMaker Studio Jupyter Server.
# Prepares environment to use port forwarding into kernel gateways
# through Jupyter Server Proxy extension and noVNC.
# See https://docs.aws.amazon.com/sagemaker/latest/dg/studio-lcc.html .

set -e

sudo yum install -y hostname
hostname
id
cat /opt/ml/metadata/resource-metadata.json

source /opt/conda/etc/profile.d/conda.sh
conda activate base
pip uninstall -y -q awscli
pip install -q sagemaker-ssh-helper

# Uncomment two lines below to update SageMaker SSH Helper to the latest dev version from the main branch
#git clone https://github.com/aws-samples/sagemaker-ssh-helper.git ./sagemaker-ssh-helper/ || echo 'Already cloned'
#cd ./sagemaker-ssh-helper/ && git pull --no-rebase && git clean -f && pip install . && cd ..

ps xfaeww

which python
which pip

env

sm-local-configure

function start_noVNC_linux() {
  json_value_regexp='s/^[^"]*".*": \"\(.*\)\"[^"]*/\1/'
  latest_noVNC_release=$(curl -s https://api.github.com/repos/novnc/noVNC/releases/latest)

  novnc_tag=$(echo "$latest_noVNC_release" | grep "tag_name" | sed -e "$json_value_regexp")
  echo "Got latest noVNC release tag: $novnc_tag"

  curl -sSL "https://api.github.com/repos/novnc/noVNC/tarball/$novnc_tag" -o "/tmp/noVNC.tgz"
  mkdir -p /tmp/noVNC
  tar xzf /tmp/noVNC.tgz -C /tmp/noVNC --strip-components=1

  cd /tmp/noVNC
  nohup ./utils/novnc_proxy --vnc 127.0.0.1:5901 &
}

# Comment the below line, if don't want to use WebVNC to connect into kernel gateway VNC sessions
start_noVNC_linux


function start_ssh_ide() {
  sudo -E env "PATH=$PATH" sm-ssh-ide configure --ssh-only
  sudo -E env "PATH=$PATH" sm-ssh-ide set-local-user-id "$LOCAL_USER_ID"
  sudo -E env "PATH=$PATH" sm-ssh-ide init-ssm
  sudo -E env "PATH=$PATH" sm-ssh-ide stop
  sudo -E env "PATH=$PATH" sm-ssh-ide start
  sudo -E env "PATH=$PATH" nohup sm-ssh-ide ssm-agent &
}

# Uncomment the below two lines, if you plan to connect to the Jupyter Server with `sm-ssh connect default.studio.sagemaker`
#LOCAL_USER_ID="AIDACKCEVSQ6C2EXAMPLE:terry@SSO"
#start_ssh_ide
