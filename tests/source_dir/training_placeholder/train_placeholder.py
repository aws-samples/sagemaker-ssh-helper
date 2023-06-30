import time
from datetime import timedelta

from sagemaker_ssh_helper import setup_and_start_ssh, is_last_session_timeout, is_profiler_issues_found

setup_and_start_ssh()

while True:
    time.sleep(10)
    if is_last_session_timeout(timedelta(minutes=5)) and is_profiler_issues_found():
        break
