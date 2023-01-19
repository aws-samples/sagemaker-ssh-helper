import logging
import os
import distutils.dir_util

import test_util

os.environ["SAGEMAKER_BASE_DIR"] = os.path.join(os.path.dirname(__file__), "opt_ml")
from sagemaker_training import environment as training_environment, params as training_parameters

from sagemaker_training.cli.train import main as train_main


def test_local_training():
    logging.info("Starting training")

    f"""
    Compare with https://github.com/aws/amazon-sagemaker-examples/tree/main/advanced_functionality/scikit_bring_your_own/container/local_test .
    """
    assert training_environment.SAGEMAKER_BASE_PATH == "/opt/ml"

    test_util._clean_training_opt_ml_dir()
    distutils.dir_util.copy_tree("./source_dir/training_clean/", "./opt_ml/code/")

    os.environ = {
        training_parameters.USER_PROGRAM_ENV: "train_clean.py",
    }

    try:
        train_main()
    except SystemExit as e:
        assert e.code == 0

    assert os.path.exists("./opt_ml/model/model.pth")
    assert os.path.exists("./opt_ml/output/success")

    logging.info("Finished training")
