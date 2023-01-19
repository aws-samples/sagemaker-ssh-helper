import torch
from torch import Tensor

# We need to add lib into sys.path, see:
# https://github.com/aws/sagemaker-python-sdk/blob/93af78b2120b33859505f8b26976c1fd243c44b7/src/sagemaker/workflow/_repack_model.py#L79
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()


# noinspection DuplicatedCode
class MyModel:
    number_t: Tensor = torch.tensor(0)

    def __init__(self, number: str):
        self.number_t = torch.tensor(int(number) + 20000)

    def predict(self, input_data: Tensor):
        return [self.number_t + input_data[0]]


def model_fn(model_dir):
    with open(os.path.join(model_dir, 'model.pth'), 'rb') as f:
        return MyModel(f.readline().decode('latin1'))


def predict_fn(input_data, model):
    return model.predict(input_data)
