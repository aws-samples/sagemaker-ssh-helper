import time
from datetime import timedelta

from sagemaker_ssh_helper import setup_and_start_ssh, is_last_session_timeout

setup_and_start_ssh()

while not is_last_session_timeout(timedelta(minutes=30)):
    time.sleep(10)
