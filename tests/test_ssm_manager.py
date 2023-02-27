import logging

from mock.mock import Mock

from sagemaker_ssh_helper.manager import SSMManager

logger = logging.getLogger('sagemaker-ssh-helper')


def test_can_fetch_instance_by_name():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_with_tags = Mock(return_value={
        "mi-01234567890abcd00": {},
        "mi-01234567890abcd01": {
            "SSHResourceName": "ssh-job",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-job",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677072061
        },
        "mi-01234567890abcd02": {
            "SSHResourceName": "ssh-job",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-job",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677072061
        },
        "mi-01234567890abcd03": {
            "SSHResourceName": "ssh-job",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:processing-job/ssh-job",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677071209
        },
        "mi-01234567890abcd04": {
            "SSHResourceName": "ssh-job",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:transform-job/ssh-job",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677069966
        },
        "mi-01234567890abcd05": {
            "SSHResourceName": "",
            "SSHResourceArn": "",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677073892
        },
        "mi-01234567890abcd06": {
            "SSHResourceName": "ssh-training",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-training",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677077641
        },
        "mi-01234567890abcd07": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677077641
        }
    })

    ids = manager.get_training_instance_ids("ssh-job", expected_count=2)
    assert len(ids) == 2
    assert ids[0] == "mi-01234567890abcd01"
    assert ids[1] == "mi-01234567890abcd02"

    ids = manager.get_processing_instance_ids("ssh-job")
    assert len(ids) == 1
    assert ids[0] == "mi-01234567890abcd03"

    ids = manager.get_transformer_instance_ids("ssh-job")
    assert len(ids) == 1
    assert ids[0] == "mi-01234567890abcd04"

    ids = manager.get_studio_kgw_instance_ids("sagemaker-data-science-ml-m5-large-1234567890abcdef0")
    assert len(ids) == 1
    assert ids[0] == "mi-01234567890abcd07"

    ids = manager.get_training_instance_ids("sagemaker-data-science-ml-m5-large-1234567890abcdef0")
    assert len(ids) == 0

    ids = manager.get_studio_kgw_instance_ids("ssh-job")
    assert len(ids) == 0


def test_instances_sorted_by_lru():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_with_tags = Mock(return_value={
        "mi-01234567890abcd07": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 2
        },
        "mi-01234567890abcd08": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 3
        },
        "mi-01234567890abcd09": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1
        },
    })

    ids = manager.get_studio_kgw_instance_ids("sagemaker-data-science-ml-m5-large-1234567890abcdef0")
    assert len(ids) == 3
    assert ids[0] == "mi-01234567890abcd08"
    assert ids[1] == "mi-01234567890abcd07"
    assert ids[2] == "mi-01234567890abcd09"


def test_can_fetch_instances_from_default_region():
    manager = SSMManager(redo_attempts=0)
    _ = manager.list_all_instances_with_tags()


def test_can_fetch_instances_from_another_region():
    manager = SSMManager(region_name="eu-west-2", redo_attempts=0)
    _ = manager.list_all_instances_with_tags()


def test_can_filter_instances_by_timestamp():
    manager = SSMManager(redo_attempts=0, clock_timestamp_override=1677158462)
    manager.list_all_instances_with_tags = Mock(return_value={
        "mi-01234567890abcd00": {},
        "mi-01234567890abcd01": {
            "SSHOwner": "",
            "$__SSMManager__.PingStatus": "ConnectionLost"
        },
        "mi-01234567890abcd02": {
            "SSHOwner": "",
            "$__SSMManager__.PingStatus": "Online"
        },
        "mi-01234567890abcd03": {
            "SSHOwner": "",
            "$__SSMManager__.PingStatus": "ConnectionLost"
        },
        "mi-01234567890abcd04": {
            "SSHResourceName": "ssh-job-1",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-job-1",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677072061,
            "$__SSMManager__.PingStatus": "ConnectionLost"
        },
        "mi-01234567890abcd05": {
            "SSHResourceName": "ssh-job-2",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-job-2",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1677158461,
            "$__SSMManager__.PingStatus": "ConnectionLost"
        },
    })

    ids = manager.list_expired_ssh_instances(expiration_days=1)
    assert len(ids) == 3
    assert "mi-01234567890abcd01" in ids
    assert "mi-01234567890abcd03" in ids
    assert "mi-01234567890abcd04" in ids
