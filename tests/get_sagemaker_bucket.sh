#!/bin/bash

read -r -d '' program << EOF
import logging
import sagemaker
logging.getLogger('sagemaker.config').setLevel(logging.WARNING)
print(sagemaker.Session().default_bucket())
EOF

SAGEMAKER_BUCKET=$(python -c "$program")
echo -n $SAGEMAKER_BUCKET