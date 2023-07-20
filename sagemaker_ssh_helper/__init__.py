import subprocess
import os
from datetime import datetime, timedelta

import sagemaker_ssh_helper.env

sagemaker_ssh_helper.last_session_time = datetime.now()


def setup_and_start_ssh():
    if "START_SSH" not in os.environ:
        print("[sagemaker-ssh-helper] WARNING: SageMaker SSH Helper is not correctly initialized. "
              "Did you forget to call wrapper.create() _before_ fit() / run() / transform() / deploy()?")

    ssh_instance_count = int(os.environ.get("SSH_INSTANCE_COUNT", "1"))
    node_rank = sagemaker_ssh_helper.env.sm_get_node_rank()
    start_ssh = os.environ.get("START_SSH", "false")

    print(f"[sagemaker-ssh-helper] SageMaker SSH Helper startup params: start_ssh={start_ssh}, "
          f"ssh_instance_count={ssh_instance_count}, node_rank={node_rank}")

    script = sagemaker_ssh_helper.env.get_caller_script_name(2)
    if start_ssh == "true" and node_rank < ssh_instance_count:
        print(f"[sagemaker-ssh-helper] Starting SSH Helper setup from {script}")
        sm_setup_ssh_absolute_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sm-setup-ssh")
        subprocess.check_call(["bash", sm_setup_ssh_absolute_path])  # nosec B607  # absolute path is calculated
    else:
        print(f"[sagemaker-ssh-helper] Skipping SageMaker SSH Helper setup from {script}")


def is_last_session_timeout(time_delta: timedelta):
    args = ["pgrep", "-f", "ssm-session-worker"]
    try:
        out = subprocess.check_output(args)
        worker_pids = list(map(int, out.splitlines()))
    except subprocess.CalledProcessError:
        worker_pids = []
    print(f"[sagemaker-ssh-helper] Number of open sessions: {len(worker_pids)}")
    if worker_pids:
        sagemaker_ssh_helper.last_session_time = datetime.now()
        timeout = False
    else:
        time_left = time_delta - (datetime.now() - sagemaker_ssh_helper.last_session_time)
        time_str = str(time_left).split(".")[0]
        timeout = (time_left <= timedelta(seconds=0))
        if not timeout:
            print(f"[sagemaker-ssh-helper] Time left before timeout: {time_str}")
        else:
            print(f"[sagemaker-ssh-helper] Sessions timeout!")

    return timeout


def is_profiler_issues_found():
    from sagemaker_ssh_helper.wrapper import SSHEstimatorWrapper
    training_job_arn = os.environ.get("TRAINING_JOB_ARN")
    if not training_job_arn:
        raise ValueError("Not running inside a training job")
    wrapper = SSHEstimatorWrapper.attach_arn(training_job_arn)
    rule_configs_summary = wrapper.rule_job_summary()
    for rule_config in rule_configs_summary:
        if rule_config['RuleEvaluationStatus'] == 'IssuesFound':
            return True
    return False
