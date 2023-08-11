# Compare with:
# https://github.com/deepjavalibrary/djl-serving/blob/v0.22.1/engines/python/setup/djl_python/deepspeed.py
# For SageMaker SSH Helper, we need to add lib into sys.path, see:
# https://github.com/aws/sagemaker-python-sdk/blob/93af78b2120b33859505f8b26976c1fd243c44b7/src/sagemaker/workflow/_repack_model.py#L79
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

import logging
from djl_python import Input, Output
import os
import deepspeed
import torch
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

predictor = None


def get_model(properties):
    model_name = properties["model_id"]
    tensor_parallel = properties["tensor_parallel_degree"]
    local_rank = int(os.getenv("LOCAL_RANK", "0"))
    model = AutoModelForCausalLM.from_pretrained(
        model_name, revision="float32", torch_dtype=torch.float32
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model = deepspeed.init_inference(
        model,
        mp_size=tensor_parallel,
        dtype=model.dtype,
        replace_method="auto",
        replace_with_kernel_inject=True,
    )
    generator = pipeline(
        task="text-generation", model=model, tokenizer=tokenizer, device=local_rank
    )
    return generator


def handle(inputs: Input) -> None:
    logging.info("Got input: %s", str(inputs))
    global predictor
    if not predictor:
        predictor = get_model(inputs.get_properties())

    if inputs.is_empty():
        # Model server makes an empty call to warmup the model on startup
        return None

    data = inputs.get_as_string()
    result = predictor(data, do_sample=True, max_new_tokens=256)
    return Output().add(result)
