from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_ec2 as ec2,
    RemovalPolicy
)
from constructs import Construct

class S3Stack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create regular S3 bucket for CSI driver
        self.bucket = s3.Bucket(
            self, "AestBucket",
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True  # Cleanup purpose
        )
