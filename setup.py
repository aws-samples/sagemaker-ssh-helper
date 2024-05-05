"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0
"""

import os
from pathlib import Path

import setuptools

required_packages = [
    "sagemaker>=2.145.0",
    "psutil",
]

extras = {
    "cdk": [
        "aws-cdk-lib==2.64.0",
        "constructs>=10.0.0,<11.0.0",
    ],
    "test": [
        "build",
        "coverage",
        "flake8",
        "mock",
        "pydocstyle",
        "pytest",
        "pytest-cov",
        "pytest-html",
        "pytest-profiling",
        "pytest-monitor",
        "bandit",
        "aws-cdk-lib==2.64.0",
        "constructs>=10.0.0,<11.0.0",
        "sagemaker-studio-image-build",
        "sagemaker-training",
        "selenium",
        "accelerate[sagemaker]<0.29",  # TODO: see https://github.com/huggingface/accelerate/issues/2744
    ],
    "dev": [
        "sagemaker-pytorch-training",
        "sagemaker-pytorch-inference",
        "torch-model-archiver",
        "tox",
        "wheel",
        "build",
        "twine",
        "pydevd-pycharm~=222.4459.20",
        "scikit-learn",
        "transformers",
        "py-cpuinfo",
        "deepspeed",  # If fails, pip install py-cpuinfo and retry
        # "djl_python",  # no such module in pip
        # To set up djl_python, clone https://github.com/deepjavalibrary/djl-serving and
        #   run 'cd djl-serving/engines/python/setup/ && pip install .'
    ],
    "dev-macos": [
        "tensorflow-macos==2.9.2",
        "numpy==1.22.4"
    ]
}


def read_version():
    return open(os.path.join(os.path.dirname(__file__), "sagemaker_ssh_helper", "VERSION")).read()


setuptools.setup(
    name='sagemaker-ssh-helper',
    version=read_version(),
    author="Amazon Web Services",
    description="A helper library to connect into Amazon SageMaker with AWS Systems Manager and SSH (Secure Shell)",
    long_description="SageMaker SSH Helper is a library that allows you to \"SSH into SageMaker\", "
                     "i.e., securely connect to Amazon SageMaker training jobs, processing jobs, "
                     "and realtime inference endpoints as well as SageMaker Studio notebook containers "
                     "for fast interactive experimentation, remote debugging, and advanced troubleshooting."
                     "\n\n"
                     "For the documentation, see the repo [https://github.com/aws-samples/sagemaker-ssh-helper/]"
                     "(https://github.com/aws-samples/sagemaker-ssh-helper/).",
    long_description_content_type='text/markdown',
    url='https://github.com/aws-samples/sagemaker-ssh-helper',
    packages=setuptools.find_packages(),
    data_files=[
        ('notebooks', [str(Path('SageMaker_SSH_IDE.ipynb')), str(Path('SageMaker_SSH_Notebook.ipynb'))]),
        ('js', [str(Path('./sagemaker_ssh_helper/js/drop_studio_file.js'))]),
        ('version', [str(Path('sagemaker_ssh_helper/VERSION'))])
    ],
    include_package_data=True,
    scripts=['sagemaker_ssh_helper/sm-helper-functions',
             'sagemaker_ssh_helper/sm-connect-ssh-proxy',
             'sagemaker_ssh_helper/sm-wait',
             'sagemaker_ssh_helper/sm-local-start-ssh',
             'sagemaker_ssh_helper/sm-local-ssh-ide',
             'sagemaker_ssh_helper/sm-local-ssh-notebook',
             'sagemaker_ssh_helper/sm-local-ssh-training',
             'sagemaker_ssh_helper/sm-local-ssh-transform',
             'sagemaker_ssh_helper/sm-local-ssh-inference',
             'sagemaker_ssh_helper/sm-local-ssh-processing',
             'sagemaker_ssh_helper/sm-local-configure',
             'sagemaker_ssh_helper/sm-ssh-ide',
             'sagemaker_ssh_helper/sm-save-env',
             'sagemaker_ssh_helper/sm-init-ssm',
             'sagemaker_ssh_helper/sm-setup-ssh',
             ],
    entry_points={
        "console_scripts": [
            "sm-ssh=sagemaker_ssh_helper.sm_ssh:main",
            "sm-ssh-deregister-instances=sagemaker_ssh_helper.deregister_old_instances_from_ssm:main"
        ]
    },
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
        "Programming Language :: Python :: 3.11",
        # "Programming Language :: Python :: 3.12",  # TODO: doesn't work on Windows, SageMaker Python SDK supports 3.10
        # "Programming Language :: Python :: 3.13",  # TODO: not tested yet, test with tox
    ]
)
