import time
import os
from datetime import timedelta

from sagemaker_ssh_helper import setup_and_start_ssh, is_last_session_timeout, is_profiler_issues_found

setup_and_start_ssh()

os.environ["AWS_DEFAULT_REGION"] = os.environ.get("AWS_REGION", "")  # for boto3

while True:
    time.sleep(10)
    if is_last_session_timeout(timedelta(minutes=30)) and is_profiler_issues_found():
        # stop if the container is left unattended and profiler found issues like low GPU utilization
        break
