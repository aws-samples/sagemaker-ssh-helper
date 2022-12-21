import os

import torch
from torch import Tensor


# noinspection DuplicatedCode
class MyModel:
    number_t: Tensor = torch.tensor(0)

    def __init__(self, number: str):
        self.number_t = torch.tensor(int(number))

    def predict(self, input_data: Tensor):
        return [self.number_t + input_data[0]]


def model_fn(model_dir):
    with open(os.path.join(model_dir, 'model.pth'), 'rb') as f:
        return MyModel(f.readline().decode('latin1'))


def predict_fn(input_data, model):
    return model.predict(input_data)
