#!/bin/bash

set -e

rm -rf /tmp/sagemaker-ssh-helper-main || :

git clone --depth 1 --branch main \
  https://github.com/aws-samples/sagemaker-ssh-helper.git \
  /tmp/sagemaker-ssh-helper-main/
diff -r -x .git -x .DS_Store /tmp/sagemaker-ssh-helper-main ./ >src_diff_main.txt || :

json_value_regexp='s/^[^"]*".*": \"\(.*\)\"[^"]*/\1/'
latest_release_json=$(curl -sS 'https://api.github.com/repos/aws-samples/sagemaker-ssh-helper/releases/latest')
latest=$(echo "$latest_release_json" | grep "tag_name" | sed -e "$json_value_regexp")

rm -rf "/tmp/sagemaker-ssh-helper-$latest/" || :

git clone -c advice.detachedHead=false --depth 1 --branch "$latest" \
  https://github.com/aws-samples/sagemaker-ssh-helper.git \
  "/tmp/sagemaker-ssh-helper-$latest/"
diff -r -x .git -x .DS_Store "/tmp/sagemaker-ssh-helper-$latest/" ./ >src_diff_latest.txt || :
