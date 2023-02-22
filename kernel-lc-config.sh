#!/bin/bash

# A lifecycle configuration script for SageMaker Studio.
# See SageMaker_SSH_IDE.ipynb for manual configuration and for explanation of commands.
# See https://docs.aws.amazon.com/sagemaker/latest/dg/studio-lcc.html .

# Replace with your JetBrains License Server host name
# OR keep it as is and put the value into ~/.sm-jb-license-server to override
JB_LICENSE_SERVER_HOST="jetbrains-license-server.example.com"

# Replace with your password
# OR keep it as is and populate ~/.vnc/passwd to override (see https://linux.die.net/man/1/vncpasswd ).
VNC_PASSWORD="123456"

# Replace with a local UserId
# OR keep it as is and put the value into ~/.sm-ssh-owner to override
LOCAL_USER_ID="AIDACKCEVSQ6C2EXAMPLE"


hostname
cat /opt/ml/metadata/resource-metadata.json

pip install -U pip
pip uninstall --root-user-action ignore -y awscli
pip install --root-user-action ignore -q sagemaker-ssh-helper

# Uncomment two lines below to update SageMaker SSH Helper to the latest dev version from main branch
#git clone https://github.com/aws-samples/sagemaker-ssh-helper.git
#cd sagemaker-ssh-helper && pip install . && cd ..

apt-get -y update
apt-get -y install procps
ps xfaeww

which python
which pip

SYSTEM_PYTHON_PREFIX=$(python -c "from __future__ import print_function;import sys; print(sys.prefix)")
export JUPYTER_PATH="$SYSTEM_PYTHON_PREFIX/share/jupyter/"

env

sm-ssh-ide configure

sm-ssh-ide set-jb-license-server "$JB_LICENSE_SERVER_HOST"
sm-ssh-ide set-vnc-password "$VNC_PASSWORD"

sm-ssh-ide init-ssm "$LOCAL_USER_ID"

sm-ssh-ide stop
sm-ssh-ide start

nohup sm-ssh-ide ssm-agent &