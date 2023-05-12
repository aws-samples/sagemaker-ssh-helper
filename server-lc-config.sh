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
#git clone https://github.com/aws-samples/sagemaker-ssh-helper.git
#cd sagemaker-ssh-helper && pip install . && cd ..

ps xfaeww

which python
which pip

env

sm-local-configure

_install_noVNC_linux

cd noVNC
nohup ./utils/novnc_proxy --vnc 127.0.0.1:5901 &
