# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.

## Adding new features to SageMaker SSH Helper

SageMaker SSH helper uses Test Driven Development (TDD) methodology to implement its features.

Before implementing new features, check existing [issues](https://github.com/aws-samples/sagemaker-ssh-helper/issues). The contributors are either working already on these features or planning to implement them in the future.

To start development, install the library on your local machine. For macOS, you may also add `dev-macos` to the extras, in addition to `dev`:
```shell
pip install '.[cdk,test,dev]'
```

Configure SageMaker execution role through [defaults](https://sagemaker.readthedocs.io/en/stable/overview.html#configuring-and-using-defaults-with-the-sagemaker-python-sdk) config.

Make sure all tests are working. You need to manually create resources that are passed through environment variables:
```shell
export ACCOUNT_ID="..."  # Obviously, you need AWS account
export AWS_ACCESS_KEY_ID="..."  # The IAM user should be powerful enough to assume USER_ROLE and to bootstrap CDK
export AWS_SECRET_ACCESS_KEY="..."

export SAGEMAKER_ROLE="..."  # You can create it automatically by creating SageMaker Domain
export USER_ROLE="..."  # AWS_ACCESS_KEY role should be allowed to assume (be trusted by) this role for at least 10 h.
                        # User role should trust `codebuild.amazonaws.com`, to call sm-docker.
export SAGEMAKER_STUDIO_DOMAIN="d-..."  # You need to create domain manually and create users: test-base-python,  
                                        # test-data-science, test-tensorflow, test-pytorch, test-spark, test-firefox.
                                        # Create Studio Classic lifecycle config for KernelGateway apps named 
                                        # `sagemaker-ssh-helper-dev` from kernel-lc-config.sh. Add it to the domain.
                                        # For `test-firefox` user, open SageMaker Studio Classic and 'Run' the app.
export VPC_ONLY_SUBNET="subnet-..."  # Create in the default VPC. Don't add Internet gateway or NAT to this subnet.
                                     # Configure VPC endpoints for STS, SSM, S3 and SageMaker.
export VPC_ONLY_SECURITY_GROUP="sg-..."  # Can be default VPC security group
export SAGEMAKER_STUDIO_VPC_ONLY_DOMAIN="d-..."  # Create manually, too. Create `internet-free-user` in the domain.
                                                 # Attach `sagemaker-ssh-helper-dev` lifecycle config to 
                                                 # KernelGateway apps.
export SNS_NOTIFICATION_TOPIC_ARN="..."  # Create SNS topic manually, subscribe to it your e-mail
export LOCAL_USER_ID="AROATCKARONAGFEXAMPLE:gitlab-ci"  # AWS_ACCESS_KEY UserId from `aws sts get-caller-identity` 
export JB_LICENSE_SERVER_HOST="jetbrains-license-server.example.com"
export SAGEMAKER_NOTEBOOK_INSTANCE="ssh-helper-notebook"  # Create manually, run SageMaker_SSH_Notebook.ipynb

export SKIP_CDK="false" 
export SKIP_PROFILE_TESTS="false"

export PYTEST_EXTRA_ARGS=" "
export PYTEST_IGNORE_SKIPS="false"
export PYTEST_KEYWORDS=" "

bash run_tests.sh
```

*Note:* You can find example CDK bootstrap policy for the AWS access key role in [tests/iam/CDKBootstrapPolicy.json](tests/iam/CDKBootstrapPolicy.json). This role should be also able to access SageMaker default buckets, see [tests/iam/GitLabCIPolicy.json](tests/iam/GitLabCIPolicy.json).

Now write a failing test, put code to make it pass, and make sure other tests are still working to avoid any regression. See [.gitlab-ci.yml](.gitlab-ci.yml) and [run_tests.sh](run_tests.sh) to learn how to do that.

For the full run of all tests, at the moment of writing, you need ~9 hours. The user role should allow [session duration](https://docs.aws.amazon.com/IAM/latest/UserGuide/roles-managingrole-editing-console.html#roles-modify_max-session-duration) for at least 10 hours. We recommend setting the max duration through AWS Console to 12 hours. 

**TODO** (for developers): Because IAM role chaining doesn't allow to assume the chained role for more than 1 hour, ACCESS_KEY (for now) should be the IAM user. We should reverse the assume role logic so that tests run under USER_ROLE which in turn assumes the CDK bootstrap role. Now the logic in [run_tests.sh](run_tests.sh) is the opposite.

**TODO** (for developers): We should create CDK to set up domains, users and VPCs.

### Code formatting

The project uses [PEP 8 Style Guide for Python Code](https://peps.python.org/pep-0008/).
Please, make sure your IDE is configured to give you hints when your code doesn't follow the guideline.
In PyCharm it's supported through [Code Inspections](https://www.jetbrains.com/help/pycharm/code-inspection.html) 
that are turned on by default. Your pull request may be rejected, if it doesn't follow the project's formatting style.

## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check existing open, or recently closed, issues to make sure somebody else hasn't already
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment


## Contributing via Pull Requests
Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *main* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional document on [forking a repository](https://help.github.com/articles/fork-a-repo/) and
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).


## Finding contributions to work on
Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels (enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any 'help wanted' issues is a great place to start.


## Code of Conduct
This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct).
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications
If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public github issue.


## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.
