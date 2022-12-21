import distutils.dir_util
import os


def _cleanup_dir(directory, recreate=False):
    if os.path.exists(directory):
        distutils.dir_util.remove_tree(directory, verbose=True)

    if recreate:
        distutils.dir_util.mkpath(directory)


def _clean_training_opt_ml_dir():
    _cleanup_dir("./opt_ml/code/")
    _cleanup_dir("./opt_ml/model/", recreate=True)
    _cleanup_dir("./opt_ml/output/", recreate=True)
