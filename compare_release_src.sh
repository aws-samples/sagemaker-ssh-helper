#!/bin/bash

set -e
set -o pipefail

mkdir -p src_diff/

cat > /tmp/diff_exclude.txt << EOF
.git
.DS_Store
src_diff
EOF

json_value_regexp='s/^[^"]*".*": \"\(.*\)\"[^"]*/\1/'
latest_release_json=$(curl -sS 'https://api.github.com/repos/aws-samples/sagemaker-ssh-helper/releases/latest')
latest=$(echo "$latest_release_json" | grep "tag_name" | sed -e "$json_value_regexp")

for branch in "main" "$latest"; do
  rm -rf "/tmp/sagemaker-ssh-helper-$latest/" || :

  git clone -c advice.detachedHead=false --depth 1 --branch "$branch" \
    https://github.com/aws-samples/sagemaker-ssh-helper.git \
    "/tmp/sagemaker-ssh-helper-$branch/"
  diff -r -X /tmp/diff_exclude.txt "/tmp/sagemaker-ssh-helper-$branch/" ./ >"src_diff/$branch.txt" || :
done

echo "compare_release_src.sh: Begin differences with main branch:"
cat src_diff/main.txt
echo "compare_release_src.sh: End differences with main branch."
