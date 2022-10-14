import os

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

model_dir = os.getenv('SM_MODEL_DIR', '/opt/ml/model')
model_path = os.path.join(model_dir, 'model.pth')

# put your training code here

with open(model_path, 'wb') as f:
    f.write(b"42")  # save your model here
