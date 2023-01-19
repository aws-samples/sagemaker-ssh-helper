import os

from keras import Model
import tensorflow as tf
import numpy as np
from keras.layers import Lambda

model_dir = os.getenv('SM_MODEL_DIR', '/opt/ml/model')

# put your training code here
print(f"Training the model in {model_dir}...")


# FIXME: lambda trick doesn't work for TF serving (seems to be silently ignored)
def start_ssh_lambda(x):
    import os
    import subprocess
    print("Starting SSH from Lambda")
    if os.environ.get('START_SSH', 'false') == 'true':
        # MME for TF ignores inference.py, so wee start SSH helper from the model itself
        subprocess.check_call('pip install sagemaker-ssh-helper'.split(' '))
        import sagemaker_ssh_helper
        sagemaker_ssh_helper.setup_and_start_ssh()
    return x


class MyModel(Model):
    def __init__(self):
        super(MyModel, self).__init__()
        self.number_t = tf.constant(42, dtype=np.int64)
        self.start_ssh_lambda = Lambda(lambda x: start_ssh_lambda(x))

    def call(self, x, **kwargs):
        x = self.start_ssh_lambda(x)
        return tf.math.add(x, self.number_t)


model = MyModel()
model.compile(run_eagerly=True)

print(model.predict([0]))

model.summary()

# save your model here
version = "00000000"
ckpt_dir = os.path.join(model_dir, version)
if not os.path.exists(ckpt_dir):
    os.makedirs(ckpt_dir)
model.save(ckpt_dir)

print("Training complete.")
