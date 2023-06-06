aws sts assume-role \
  --role-arn "$GITLAB_ROLE_ARN" \
  --role-session-name "gitlab-ci" \
  --duration-seconds 28800 \
  --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
  --output text
