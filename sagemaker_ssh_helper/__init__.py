import sagemaker_ssh_helper.env


def setup_and_start_ssh():
    import subprocess
    import os

    ssh_instance_count = int(os.environ.get("SSH_INSTANCE_COUNT", "1"))
    node_rank = sagemaker_ssh_helper.env.sm_get_node_rank()
    start_ssh = os.environ.get("START_SSH", "false")

    print(f"SSH Helper startup params: start_ssh={start_ssh}, ssh_instance_count={ssh_instance_count},"
          f" node_rank={node_rank}")

    if start_ssh == "true" and node_rank < ssh_instance_count:
        print(f"Starting SSH Helper setup")
        subprocess.check_call(["bash", os.path.join(os.path.dirname(__file__), "sm-setup-ssh")])
    else:
        print(f"Skipping SSH Helper setup")
