import logging
import os
import distutils.dir_util
from pathlib import Path

import mock

from sagemaker_training import params as training_parameters

import test_util


@mock.patch.dict(
    os.environ, {
        "SAGEMAKER_BASE_DIR": os.path.join(os.path.dirname(__file__), "opt_ml"),
        training_parameters.USER_PROGRAM_ENV: Path('source_dir/training_clean/train_clean.py').name
    }
)
def test_local_training():
    from sagemaker_training import environment as training_environment
    from sagemaker_training.cli.train import main as train_main

    logging.info("Starting training")

    f"""
    Compare with https://github.com/aws/amazon-sagemaker-examples/tree/main/advanced_functionality/scikit_bring_your_own/container/local_test .
    """
    assert training_environment.SAGEMAKER_BASE_PATH == "/opt/ml", "default path should be /opt/ml"
    assert training_environment.base_dir.endswith("/opt_ml"), "override path should end with /opt_ml"

    test_util._clean_training_opt_ml_dir()
    distutils.dir_util.copy_tree("./source_dir/training_clean/", "./opt_ml/code/")

    try:
        # Note: it will start the subprocess, so we don't have the code coverage
        # TODO: https://coverage.readthedocs.io/en/latest/subprocess.html
        train_main()
    except SystemExit as e:
        assert e.code == 0

    assert os.path.exists("./opt_ml/model/model.pth")
    assert os.path.exists("./opt_ml/output/success")

    logging.info("Finished training")


@mock.patch.dict(os.environ, {"SM_MODEL_DIR": os.path.join(os.path.dirname(__file__), "opt_ml/model")})
def test_local_training_with_coverage():
    # import will start training
    from source_dir.training_clean import train_clean
    assert train_clean
