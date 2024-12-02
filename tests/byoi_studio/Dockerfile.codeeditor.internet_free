FROM public.ecr.aws/sagemaker/sagemaker-distribution:1.6-cpu@sha256:d5148872a9e35b62054fbd82991541592b0ea5edb7b343e579a2daf3b50c2f6b

USER root
# Install SageMaker SSH Helper for the Internet-free setup
ARG SAGEMAKER_SSH_HELPER_DIR="/opt/sagemaker-ssh-helper"
RUN mkdir -p $SAGEMAKER_SSH_HELPER_DIR

# See tests/test_ide.py::test_studio_internet_free_mode

# Log the kernel specs
# The kernel name needs to match SageMaker Image config
# RUN jupyter-kernelspec list

RUN pip3 uninstall -y -q awscli

# Install official release (for users):
#RUN \
#    pip3 install --no-cache-dir sagemaker-ssh-helper

# Install dev release from source (for developers):
COPY ./ $SAGEMAKER_SSH_HELPER_DIR/src/
RUN \
    pip3 --no-cache-dir install wheel && \
    pip3 --no-cache-dir install $SAGEMAKER_SSH_HELPER_DIR/src/

# Pre-configure the container with packages, which should be installed from Internet
# Consider adding `--ssh-only` flag and commenting the first RUN command, if you don't plan to connect
# to the VNC server or to the Jupyter notebook
# RUN apt-get update -y && apt-get upgrade -y

RUN sm-ssh-ide configure --ssh-only

USER $MAMBA_USER
WORKDIR "/home/${NB_USER}"
ENTRYPOINT ["entrypoint-code-editor"]  