import json
import os
from typing import List


def sm_get_node_rank():
    base_dir = os.environ.get("SAGEMAKER_BASE_DIR", "/opt/ml")

    rc_path = os.path.join(base_dir, "input", "config", "resourceconfig.json")

    if not os.path.exists(rc_path):
        # TODO: make it work for processing and inference, too
        return 0

    with open(rc_path) as json_file:
        rc = json.load(json_file)

    return int(rc["hosts"].index(rc["current_host"]))


def get_caller_script_name(trace_back=1):
    import inspect
    from inspect import FrameInfo
    from pathlib import Path

    stack: List[FrameInfo] = inspect.stack()
    if len(stack) < 2:
        raise AssertionError("Cannot fetch stack trace")

    return Path(stack[trace_back].filename).name
