import logging
import sys

from sagemaker_ssh_helper.deregister_old_instances_from_ssm import main as deregister_instances_main

logger = logging.getLogger('sagemaker-ssh-helper')


def test_deregister_instances():
    sys.argv.append('--preapproving-deregistration')
    try:
        deregister_instances_main()
    finally:
        sys.argv.remove('--preapproving-deregistration')

    assert True  # nothing to check
