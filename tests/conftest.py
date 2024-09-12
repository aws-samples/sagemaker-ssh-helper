
def pytest_addoption(parser):
    parser.addini('sagemaker_studio_domain', '')
    parser.addini('sagemaker_studio_vpc_only_domain', '')
    parser.addini('vpc_only_subnet', '')
    parser.addini('vpc_only_security_group', '')
    parser.addini('sagemaker_role', '')
    parser.addini('sns_notification_topic_arn', '')
    parser.addini('sagemaker_notebook_instance', '')
