import setuptools

required_packages = [
    "sagemaker>=2.110.0"
]

extras = {
    "test": [
        "black",
        "coverage",
        "flake8",
        "mock",
        "pydocstyle",
        "pytest",
        "pytest-cov",
        "sagemaker-pytorch-training",
        "sagemaker-pytorch-inference",
        "torch-model-archiver",
        "tox",
        "wheel",
        "build",
        "twine",
        "pydevd-pycharm~=213.6777.50"
    ]
}
setuptools.setup(
    name='sagemaker-ssh-helper',
    version='1.8.0.dev1',
    author="Amazon Web Services",
    description="A helper library to connect into Amazon SageMaker with AWS Systems Manager and SSH",
    long_description="For the detailed description see [README.md](https://github.com/aws-samples/sagemaker-ssh-helper/blob/main/README.md).",
    long_description_content_type='text/markdown',
    url='https://github.com/aws-samples/sagemaker-ssh-helper',
    packages=setuptools.find_packages(),
    include_package_data=True,
    scripts=['sagemaker_ssh_helper/sm-helper-functions',
             'sagemaker_ssh_helper/sm-connect-ssh-proxy',
             'sagemaker_ssh_helper/sm-wait',
             'sagemaker_ssh_helper/sm-local-start-ssh',
             'sagemaker_ssh_helper/sm-local-install-force',
             'sagemaker_ssh_helper/sm-local-ssh-ide',
             'sagemaker_ssh_helper/sm-local-ssh-training',
             'sagemaker_ssh_helper/sm-start-ssh',
             'sagemaker_ssh_helper/sm-ssh-ide',
             'sagemaker_ssh_helper/sm-save-env',
             'sagemaker_ssh_helper/sm-init-ssm',
             'sagemaker_ssh_helper/sm-setup-ssh'],
    python_requires=">=3.7",
    install_requires=required_packages,
    extras_require=extras,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT No Attribution License (MIT-0)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ]
)
