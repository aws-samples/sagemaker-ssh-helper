# Original from:
# https://github.com/aws/amazon-sagemaker-examples/blob/main/advanced_functionality/pytorch_deploy_large_GPT_model/GPT-J-6B-model-parallel-inference-DJL.ipynb
import logging
# We need to add lib into sys.path, see:
# https://github.com/aws/sagemaker-python-sdk/blob/93af78b2120b33859505f8b26976c1fd243c44b7/src/sagemaker/workflow/_repack_model.py#L79
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()

from djl_python import Input, Output
import os
import deepspeed
import torch
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer

predictor = None


def get_model():
    model_name = 'EleutherAI/gpt-j-6B'
    tensor_parallel = int(os.getenv('TENSOR_PARALLEL_DEGREE', '1'))
    local_rank = int(os.getenv('LOCAL_RANK', '0'))
    logging.info(f"Loading model with tensor_parallel={tensor_parallel} and local_rank={local_rank}")
    model = AutoModelForCausalLM.from_pretrained(model_name, revision="float32", torch_dtype=torch.float32)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # #033[33mWARN #033[m #033[92mPyProcess#033[m [1,0]<stderr>:The model 'InferenceEngine' is not supported for text-generation. Supported models are ['BartForCausalLM', 'BertLMHeadModel', 'BertGenerationDecoder', 'BigBirdForCausalLM', 'BigBirdPegasusForCausalLM', 'BioGptForCausalLM', 'BlenderbotForCausalLM', 'BlenderbotSmallForCausalLM', 'BloomForCausalLM', 'CamembertForCausalLM', 'CodeGenForCausalLM', 'CTRLLMHeadModel', 'Data2VecTextForCausalLM', 'ElectraForCausalLM', 'ErnieForCausalLM', 'GitForCausalLM', 'GPT2LMHeadModel', 'GPT2LMHeadModel', 'GPTNeoForCausalLM', 'GPTNeoXForCausalLM', 'GPTNeoXJapaneseForCausalLM', 'GPTJForCausalLM', 'MarianForCausalLM', 'MBartForCausalLM', 'MegatronBertForCausalLM', 'MvpForCausalLM', 'OpenAIGPTLMHeadModel', 'OPTForCausalLM', 'PegasusForCausalLM', 'PLBartForCausalLM', 'ProphetNetForCausalLM', 'QDQBertLMHeadModel', 'ReformerModelWithLMHead', 'RemBertForCausalLM', 'RobertaForCausalLM', 'RobertaPreLayerNormForCausalLM', 'RoCBertForCausalLM', 'RoFormerForCausalLM', 'Speech2Text2ForCausalLM', 'TransfoXLLMHeadModel', 'TrOCRForCausalLM', 'XGLMForCausalLM', 'XLMWithLMHeadModel', 'XLMProphetNetForCausalLM', 'XLMRobertaForCausalLM', 'XLMRobertaXLForCausalLM', 'XLNetLMHeadModel'].

    model = deepspeed.init_inference(model,
                                     mp_size=tensor_parallel,
                                     dtype=model.dtype,
                                     replace_method='auto',
                                     replace_with_kernel_inject=True)
    generator = pipeline(task='text-generation', model=model, tokenizer=tokenizer, device=local_rank)
    return generator


def handle(inputs: Input) -> None:
    global predictor
    if not predictor:
        predictor = get_model()

    if inputs.is_empty():
        # Model server makes an empty call to warmup the model on startup
        return None

    import subprocess
    # Take the command from Python Debug Server dialog in PyCharm
    subprocess.check_call("pip install pydevd-pycharm~=222.4459.20".split())

    # Next command is the patch for https://youtrack.jetbrains.com/issue/PY-40552
    subprocess.check_call("sed -i~ -e s~s.replace~str(s).replace~ "
                          "/usr/local/lib/python3.9/dist-packages/_pydevd_bundle/pydevd_xml.py".split())

    logging.info("Connecting to remote debug server")
    import pydevd_pycharm
    pydevd_pycharm.settrace('127.0.0.1', port=12345, stdoutToServer=True, stderrToServer=True)
    logging.info("Connection complete")

    data = inputs.get_as_string()
    result = predictor(data, do_sample=True, min_tokens=200, max_new_tokens=256)
    return Output().add(result)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout,
                        format="%(message)s",
                        level=logging.INFO)
    predictor = get_model()
    result = predictor("Hello world!", do_sample=True, min_tokens=200, max_new_tokens=256)
    print(result)
    sys.exit(0)
