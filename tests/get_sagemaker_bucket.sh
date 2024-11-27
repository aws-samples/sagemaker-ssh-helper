#!/bin/bash

read -r -d '' program << EOF
import logging
logging.getLogger('sagemaker.config').setLevel(logging.WARNING)
logging.getLogger('botocore.credentials').setLevel(logging.WARNING)
import sagemaker
print(sagemaker.Session().default_bucket())
EOF

SAGEMAKER_BUCKET=$(python -c "$program")
echo -n "$SAGEMAKER_BUCKET"