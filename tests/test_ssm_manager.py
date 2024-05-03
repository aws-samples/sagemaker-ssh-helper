import logging

from mock.mock import Mock

from sagemaker_ssh_helper.ide import IDEAppStatus
from sagemaker_ssh_helper.interactive_sagemaker import InteractiveSageMaker, SageMaker, SageMakerStudioApp
from sagemaker_ssh_helper.manager import SSMManager

logger = logging.getLogger('sagemaker-ssh-helper')


def test_can_fetch_instance_by_name():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
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
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
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
    _ = manager.list_all_instances_and_fetch_tags()


def test_can_fetch_instances_from_another_region():
    manager = SSMManager(region_name="eu-west-2", redo_attempts=0)
    _ = manager.list_all_instances_and_fetch_tags()


def test_can_filter_instances_by_timestamp():
    manager = SSMManager(redo_attempts=0, clock_timestamp_override=1677158462)
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
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


# noinspection DuplicatedCode
def test_can_filter_by_domain_and_user():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
        "mi-01234567890abcd07": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 2
        },
        "mi-01234567890abcd08": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 3
        },
        "mi-01234567890abcd09": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-5555555555555/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1
        },
    })

    ids = manager.get_studio_user_kgw_instance_ids(
        "d-0123456789bc", "default-1111111111111",
        "sagemaker-data-science-ml-m5-large-1234567890abcdef0"
    )
    assert len(ids) == 1
    assert ids[0] == "mi-01234567890abcd08"


# noinspection DuplicatedCode
def test_can_filter_by_user_with_latest_domain():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
        "mi-01234567890abcd07": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 2
        },
        "mi-01234567890abcd08": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/default-1111111111111/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 3
        },
        "mi-01234567890abcd09": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/default-5555555555555/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": 1
        },
    })

    ids = manager.get_studio_user_kgw_instance_ids(
        "", "default-1111111111111",
        "sagemaker-data-science-ml-m5-large-1234567890abcdef0"
    )
    assert len(ids) == 2
    assert ids[0] == "mi-01234567890abcd08"
    assert ids[1] == "mi-01234567890abcd07"


def test_can_list_ssh_and_non_ssh_instances():
    manager = SSMManager(redo_attempts=0)
    manager.list_all_instances_and_fetch_tags = Mock(return_value={
        "mi-01234567890abcd00": {
            "Cost Center": "78925",
            "Owner": "DbAdmin",
        },
        "mi-01234567890abcd01": {
            "SSHResourceName": "ssh-job",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:training-job/ssh-job",
            "SSHCreator": "",
            "SSHOwner": "",
            "SSHTimestamp": "1677072061",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890000000": {
            "SSHResourceName": "default",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-000000000000/janedoe/JupyterServer/default",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE",
            "SSHTimestamp": "42",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890abcd04": {
            "SSHResourceName": "default",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/janedoe/JupyterServer/default",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE:janedoe@SSO",
            "SSHTimestamp": "0",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890abcd05": {
            "SSHResourceName": "default",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/janedoe/JupyterServer/default",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE:janedoe@SSO",
            "SSHTimestamp": "1",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890abcd07": {
            "SSHResourceName": "ssh-test-kgw",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/janedoe/KernelGateway/ssh-test-kgw",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE:janedoe@SSO",
            "SSHTimestamp": "2",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890abcd08": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789bc/terry/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE:terry@SSO",
            "SSHTimestamp": "1",
            SSMManager.PING_STATUS: "Online"
        },
        "mi-01234567890abcd09": {
            "SSHResourceName": "sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHResourceArn": "arn:aws:sagemaker:eu-west-1:555555555555:app/d-0123456789ab/terry/KernelGateway/sagemaker-data-science-ml-m5-large-1234567890abcdef0",
            "SSHCreator": "",
            "SSHOwner": "AIDACKCEVSQ6C2EXAMPLE:terry@SSO",
            "SSHTimestamp": "3",
            SSMManager.PING_STATUS: "Online"
        },
    })

    sagemaker = SageMaker('eu-west-1')
    sagemaker.list_ide_apps = Mock(return_value=[
        SageMakerStudioApp(
            "d-0123456789bc", "janedoe", "default", "JupyterServer", IDEAppStatus("InService")
        ),
        SageMakerStudioApp(
            "d-0123456789bc", "janedoe", "ssh-test-kgw", "KernelGateway", IDEAppStatus("InService")
        ),
        SageMakerStudioApp(
            "d-0123456789bc", "janedoe", "data-science-m5-no-ssh", "KernelGateway", IDEAppStatus("InService")
        ),
        SageMakerStudioApp(
            "d-0123456789bc", "janedoe", "data-science-g4-no-ssh", "KernelGateway", IDEAppStatus("Offline")
        ),
        SageMakerStudioApp(
            "d-0123456789bc", "terry", "sagemaker-data-science-ml-m5-large-1234567890abcdef0", "KernelGateway", IDEAppStatus("Offline")
        ),
        SageMakerStudioApp(
            "d-0123456789bc", "terry", "data-science-m5-no-ssh", "KernelGateway", IDEAppStatus("Offline")
        ),

        SageMakerStudioApp(
            "d-0123456789ab", "terry", "sagemaker-data-science-ml-m5-large-1234567890abcdef0", "KernelGateway", IDEAppStatus("Offline")
        ),
        SageMakerStudioApp(
            "d-0123456789ab", "terry", "data-science-m5-no-ssh", "KernelGateway", IDEAppStatus("Offline")
        ),
        # LocalApp("janedoe", "AIDACKCEVSQ6C2EXAMPLE:janedoe@SSO", "macOS 13.5.1"),
        # LocalApp("terry", "AIDACKCEVSQ6C2EXAMPLE:terry@SSO", "Windows 10 Pro"),
    ])

    interactive_sagemaker = InteractiveSageMaker(sagemaker, manager)

    apps = interactive_sagemaker.list_studio_ide_apps_for_user_and_domain(
        "d-0123456789bc", "janedoe",
    )
    assert len(apps) == 4
    assert apps[0].app_name == "default"
    assert apps[0].app_type == "JupyterServer"
    assert apps[0].ssm_instance_id == "mi-01234567890abcd05"
    assert apps[0].ssh_owner == "AIDACKCEVSQ6C2EXAMPLE:janedoe@SSO"

    apps = interactive_sagemaker.list_studio_ide_apps_for_user_and_domain(
        "d-0123456789bc", "terry",
    )
    assert len(apps) == 2

    apps = interactive_sagemaker.list_studio_ide_apps_for_user(
        "terry",
    )
    assert len(apps) == 4

    apps = interactive_sagemaker.list_studio_ide_apps()
    assert len(apps) == 8
