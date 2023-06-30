
def pytest_addoption(parser):
    parser.addini('sagemaker_studio_domain', '')
    parser.addini('sns_notification_topic_arn', '')
