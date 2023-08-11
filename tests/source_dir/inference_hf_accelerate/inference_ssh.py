# We need to add lib into sys.path, see:
# https://github.com/aws/sagemaker-python-sdk/blob/93af78b2120b33859505f8b26976c1fd243c44b7/src/sagemaker/workflow/_repack_model.py#L79
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

# https://github.com/deepjavalibrary/djl-serving/blob/v0.20.0/engines/python/setup/djl_python/huggingface.py#L207
from djl_python.huggingface import handle

if handle is None:
    raise ValueError("Failed to import HF accelerate handler")
