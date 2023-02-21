
def pytest_addoption(parser):
    parser.addini('sagemaker_role', '')
    parser.addini('kernel_gateway_name', '')
