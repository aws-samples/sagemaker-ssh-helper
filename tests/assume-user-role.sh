aws sts assume-role \
  --role-arn "$USER_ROLE" \
  --role-session-name "gitlab-ci" \
  --duration-seconds 28800 \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text
