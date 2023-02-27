# Based on https://github.com/aws/amazon-sagemaker-examples/blob/main/advanced_functionality/scikit_bring_your_own/container/Dockerfile

# Run from SageMaker Studio at the project root (where setup.py is located):
# pip install sagemaker-studio-image-build
# sm-docker build . --file tests/byoc/Dockerfile --repo byoc-ssh:latest

# See https://aws.amazon.com/blogs/machine-learning/using-the-amazon-sagemaker-studio-image-build-cli-to-build-container-images-from-your-studio-notebooks/ .

FROM public.ecr.aws/docker/library/ubuntu:20.04

RUN apt-get -y update && apt-get install -y --no-install-recommends \
         wget \
         python3-pip \
         python3-setuptools \
         nginx \
         ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN pip --no-cache-dir install numpy scipy scikit-learn pandas flask gunicorn

# Test official release (for users):
# RUN pip --no-cache-dir install sagemaker-ssh-helper  # <--- NEW

# Test current release (for developers):
COPY . /tmp/sagemaker-ssh-helper/
RUN pip --no-cache-dir install /tmp/sagemaker-ssh-helper/

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"

COPY tests/byoc/decision_trees /opt/program
WORKDIR /opt/program