from sagemaker_ssh_helper.sm_ssh import SageMakerSecureShellHelper


def test_fqdn_to_type():
    sm_ssh = SageMakerSecureShellHelper()
    assert sm_ssh.fqdn_to_type("ssh-training-job.training.sagemaker") == "training"
    assert sm_ssh.fqdn_to_type("ssh-processing-job.processing.sagemaker") == "processing"
    assert sm_ssh.fqdn_to_type("ssh-transform-job.transform.sagemaker") == "transform"
    assert sm_ssh.fqdn_to_type("ssh-endpoint.inference.sagemaker") == "inference"
    assert sm_ssh.fqdn_to_type("sagemaker-data-science-ml-m5-large.studio.sagemaker") == "ide"
    assert sm_ssh.fqdn_to_type("ssh-test-ds2-cpu.studio.sagemaker") == "ide"
    assert sm_ssh.fqdn_to_type("ssh-test-ds2-cpu.test-data-science.d-egm0dexample.studio.sagemaker") == "ide"
    assert sm_ssh.fqdn_to_type("ssh-helper-notebook.notebook.sagemaker") == "notebook"


def test_fqdn_to_name():
    sm_ssh = SageMakerSecureShellHelper()
    assert sm_ssh.fqdn_to_name("ssh-training-job.training.sagemaker") == "ssh-training-job"
    assert sm_ssh.fqdn_to_name("ssh-processing-job.processing.sagemaker") == "ssh-processing-job"
    assert sm_ssh.fqdn_to_name("ssh-transform-job.transform.sagemaker") == "ssh-transform-job"
    assert sm_ssh.fqdn_to_name("ssh-endpoint.inference.sagemaker") == "ssh-endpoint"
    assert sm_ssh.fqdn_to_name("sagemaker-data-science-ml-m5-large.studio.sagemaker") == "sagemaker-data-science-ml-m5-large"
    assert sm_ssh.fqdn_to_name("ssh-test-ds2-cpu.studio.sagemaker") == "ssh-test-ds2-cpu"
    assert sm_ssh.fqdn_to_name("ssh-test-ds2-cpu.test-data-science.d-egm0dexample.studio.sagemaker") == "ssh-test-ds2-cpu"
    assert sm_ssh.fqdn_to_name("ssh-helper-notebook.notebook.sagemaker") == "ssh-helper-notebook"
    assert sm_ssh.fqdn_to_name("training.sagemaker") == ""
    assert sm_ssh.fqdn_to_name("sagemaker") == ""


def test_fqdn_to_studio_user_and_domain():
    sm_ssh = SageMakerSecureShellHelper()
    assert sm_ssh.fqdn_to_studio_domain_id("ssh-training-job.training.sagemaker") == ""
    assert sm_ssh.fqdn_to_studio_user_name("ssh-training-job.training.sagemaker") == ""
    assert sm_ssh.fqdn_to_studio_domain_id("ssh-test-ds2-cpu.studio.sagemaker") == ""
    assert sm_ssh.fqdn_to_studio_user_name("ssh-test-ds2-cpu.studio.sagemaker") == ""
    assert sm_ssh.fqdn_to_studio_domain_id(
        "ssh-test-ds2-cpu.test-data-science.d-egm0dexample.studio.sagemaker"
    ) == "d-egm0dexample"
    assert sm_ssh.fqdn_to_studio_user_name(
        "ssh-test-ds2-cpu.test-data-science.d-egm0dexample.studio.sagemaker"
    ) == "test-data-science"
    assert sm_ssh.fqdn_to_studio_domain_id(
        "test-data-science.d-egm0dexample.studio.sagemaker"
    ) == "d-egm0dexample"
    assert sm_ssh.fqdn_to_studio_user_name(
        "test-data-science.d-egm0dexample.studio.sagemaker"
    ) == "test-data-science"
