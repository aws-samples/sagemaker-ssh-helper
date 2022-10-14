

def setup_and_start_ssh():
    import subprocess
    import os

    if os.environ.get("START_SSH", "false") == "true":
        subprocess.check_call(["bash", os.path.join(os.path.dirname(__file__), "sm-setup-ssh")])
