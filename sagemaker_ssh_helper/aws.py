class AWS:
    def __init__(self, region: str) -> None:
        super().__init__()
        self.region = region

    def get_console_domain(self):
        """
        See https://docs.aws.amazon.com/general/latest/gr/mgmt-console.html .
        See https://docs.amazonaws.cn/en_us/aws/latest/userguide/endpoints-arns.html .
        See https://github.com/boto/botocore/blob/develop/botocore/data/endpoints.json .
        """
        if self.region.startswith("cn-"):
            return f"{self.region}.console.amazonaws.cn"
        if self.region.startswith("us-gov-"):
            return f"{self.region}.console.amazonaws-us-gov.com"
        return f"{self.region}.console.aws.amazon.com"

    @staticmethod
    def is_arn(arn: str):
        """
        See https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/using-govcloud-arns.html .
        See https://docs.amazonaws.cn/en_us/aws/latest/userguide/ARNs.html .
        """
        import re
        return re.match(r'^arn:(aws|aws-cn|aws-us-gov):iam::([0-9]+):role/(\S+)$', arn)
