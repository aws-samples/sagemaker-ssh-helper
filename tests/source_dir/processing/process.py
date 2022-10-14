
# Fix Python path until SageMaker Processing supports source_dir and requirements.txt for all frameworks or
#   package is released into PyPI
import sys
sys.path.append("/opt/ml/processing/input/")

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

print("42")
