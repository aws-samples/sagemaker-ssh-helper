import logging
import os
import sys

from mock import mock

from sagemaker_ssh_helper.deregister_old_instances_from_ssm import main as deregister_instances_main

logger = logging.getLogger('sagemaker-ssh-helper')


@mock.patch.object(sys, 'argv', ['--preapproving-deregistration', '--delete-older-than-n-days', 2])
def test_deregister_instances():
    deregister_instances_main()
    assert True  # nothing to check


@mock.patch.dict(os.environ, {"AWS_REGION": "eu-west-2", "AWS_DEFAULT_REGION": "eu-west-2"})
@mock.patch.object(sys, 'argv', ['--preapproving-deregistration', '--delete-older-than-n-days', 2])
def test_deregister_instances_another_region():
    deregister_instances_main()
    assert True  # nothing to check
