import os

from keras import Model
import tensorflow as tf
import numpy as np

model_dir = os.getenv('SM_MODEL_DIR', '/opt/ml/model')

# put your training code here
print(f"Training the model in {model_dir}...")


# Adopted from the TF example:
# https://github.com/aws/amazon-sagemaker-examples/blob/e63a03fbafa779a1e81043958b389a76fa15ec70/frameworks/tensorflow/code/train.py
class MyModel(Model):
    def __init__(self):
        super(MyModel, self).__init__()
        self.number_t = tf.constant(42, dtype=np.int64)

    def call(self, x, **kwargs):
        return tf.math.add(x, self.number_t)


model = MyModel()
model.compile()

print(model.predict([0]))

# save your model here
version = "00000000"
ckpt_dir = os.path.join(model_dir, version)
if not os.path.exists(ckpt_dir):
    os.makedirs(ckpt_dir)
model.save(ckpt_dir)

print("Training complete.")
