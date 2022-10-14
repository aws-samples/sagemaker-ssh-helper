import time

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

while True:
    time.sleep(10)
