import sagemaker_ssh_helper.env


def setup_and_start_ssh():
    import subprocess
    import os

    if "START_SSH" not in os.environ:
        print("WARNING: SageMaker SSH Helper is not correctly initialized. "
              "Did you forget to call wrapper.create() _before_ fit() / run() / transform() / deploy()?")

    ssh_instance_count = int(os.environ.get("SSH_INSTANCE_COUNT", "1"))
    node_rank = sagemaker_ssh_helper.env.sm_get_node_rank()
    start_ssh = os.environ.get("START_SSH", "false")

    print(f"SSH Helper startup params: start_ssh={start_ssh}, ssh_instance_count={ssh_instance_count},"
          f" node_rank={node_rank}")

    if start_ssh == "true" and node_rank < ssh_instance_count:
        print(f"Starting SSH Helper setup")
        absolute_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sm-setup-ssh")
        subprocess.check_call(["bash", absolute_path])  # nosec B607  # absolute path is calculated
    else:
        print(f"Skipping SSH Helper setup")
