import json
import os


def sm_get_node_rank():
    base_dir = os.environ.get("SAGEMAKER_BASE_DIR", "/opt/ml")

    rc_path = os.path.join(base_dir, "input", "config", "resourceconfig.json")

    if not os.path.exists(rc_path):
        # TODO: make it work for processing and inference, too
        return 0

    with open(rc_path) as json_file:
        rc = json.load(json_file)

    return int(rc["hosts"].index(rc["current_host"]))
