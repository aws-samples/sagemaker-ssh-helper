# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary
information to effectively respond to your bug report or contribution.

## Adding new features to the SageMaker SSH Helper

SageMaker SSH helper uses Test Driven Development (TDD) methodology to implement its features.

Before implementing new features, check [TODO](TODO) list and [issues](https://github.com/aws-samples/sagemaker-ssh-helper/issues). The contributors are either working already on these features or planning to implement them in the future.

To start development, install the library on your local machine:
```shell
pip install '.[test,dev,cdk]'
```

Configure SageMaker execution role through [defaults](https://sagemaker.readthedocs.io/en/stable/overview.html#configuring-and-using-defaults-with-the-sagemaker-python-sdk) config.

Make sure all tests are working:
```shell
cd tests
coverage run -m pytest -m 'not manual' \
  -o kernel_gateway_name=<<YOUR_KERNEL_GATEWAY_NAME>>
```
*Tip:* You can pass your parameters either in command line or set it in `tests/pytest.ini`.

Write a failing test, put code to make it pass, and make sure other tests are still working to avoid any regression.

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
