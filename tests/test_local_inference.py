import os
import distutils.dir_util

os.environ["SAGEMAKER_BASE_DIR"] = os.path.join(os.path.dirname(__file__), "opt_ml")
from sagemaker_training import environment as training_environment, params as training_parameters

from sagemaker_training.cli.train import main as train_main


def test_local_training():
    assert training_environment.SAGEMAKER_BASE_PATH == "/opt/ml"

    _clean_training_opt_ml_dir()
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


def _cleanup_dir(directory, recreate=False):
    if os.path.exists(directory):
        distutils.dir_util.remove_tree(directory, verbose=True)

    if recreate:
        distutils.dir_util.mkpath(directory)


def _clean_training_opt_ml_dir():
    _cleanup_dir("./opt_ml/code/")
    _cleanup_dir("./opt_ml/model/", recreate=True)
    _cleanup_dir("./opt_ml/output/", recreate=True)
