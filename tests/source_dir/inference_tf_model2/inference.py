import json
import requests
import logging

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))

import sagemaker_ssh_helper
sagemaker_ssh_helper.setup_and_start_ssh()


# Adopted from https://sagemaker.readthedocs.io/en/stable/frameworks/tensorflow/using_tf.html#how-to-implement-the-pre-and-or-post-processing-handler-s
def handler(data, context):
    """Handle request.
    Args:
        data (obj): the request data
        context (Context): an object containing request and configuration details
    Returns:
        (bytes, string): data to return to client, (optional) response content type
    """
    processed_input = _process_input(data, context)
    response = requests.post(context.rest_uri, data=processed_input, timeout=5)
    return _process_output(response, context)


def _process_input(data, context):
    if context.request_content_type == 'application/json':
        # pass through json (assumes it's correctly formed)
        d = data.read().decode('utf-8')
        d = f"{{\"instances\": {d}}}"
        logging.info(f"Processing prediction request (model 2): {d}")
        return d

    if context.request_content_type == 'text/csv':
        # very simple csv handler
        return json.dumps({
            'instances': [float(x) for x in data.read().decode('utf-8').split(',')]
        })

    raise ValueError('{{"error": "unsupported content type {}"}}'.format(
        context.request_content_type or "unknown"))


def _process_output(data, context):
    if data.status_code != 200:
        raise ValueError(data.content.decode('utf-8'))

    logging.info(f"Accept content type header: {context.accept_header}")
    response_content_type = context.accept_header
    if response_content_type == '*/*':
        response_content_type = 'application/json'  # fix for SageMaker Studio that always (?) sends 'Accept: */*'

    d = data.content

    if response_content_type == 'application/json':
        d_json = json.loads(d)
        d[0] = d[0] + 20000  # alter prediction for model 2
        d = json.dumps(d_json['predictions'])

    prediction = d
    logging.info(f"Got prediction result (model 2): {prediction}")
    return prediction, response_content_type
