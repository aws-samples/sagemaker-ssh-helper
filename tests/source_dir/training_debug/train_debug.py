import logging
import os

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()


import subprocess
# Take the command from Python Debug Server dialog in PyCharm
subprocess.check_call("pip install pydevd-pycharm~=222.4459.20".split())

# Next command is the patch for https://youtrack.jetbrains.com/issue/PY-40552
subprocess.check_call("sed -i~ -e s~s.replace~str(s).replace~ "
                      "/opt/conda/lib/python3.8/site-packages/_pydevd_bundle/pydevd_xml.py".split())

logging.info("Connecting to remote debug server")
import pydevd_pycharm
pydevd_pycharm.settrace('127.0.0.1', port=12345, stdoutToServer=True, stderrToServer=True)
logging.info("Connection complete")


model_dir = os.getenv('SM_MODEL_DIR', '/opt/ml/model')
model_path = os.path.join(model_dir, 'model.pth')

# put your training code here
print(f"Training the model {model_path}...")

with open(model_path, 'wb') as f:
    f.write(b"42")  # save your model here
