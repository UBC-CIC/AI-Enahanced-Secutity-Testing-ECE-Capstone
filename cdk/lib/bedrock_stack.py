from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct

class BedrockStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create a role for Bedrock to access S3
        self.bedrock_role = iam.Role(
            self, "BedrockS3Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock to access all S3 buckets"
        )

        # Add S3 permissions for all buckets
        self.bedrock_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:DeleteObject",
                    "s3:ListAllMyBuckets"  # Added to list all buckets
                ],
                resources=[
                    "arn:aws:s3:::*",  # All buckets
                    "arn:aws:s3:::*/*"  # All objects in all buckets
                ]
            )
        )

        # Output the role ARN
        CfnOutput(
            self, "BedrockRoleArn",
            value=self.bedrock_role.role_arn,
            description="ARN of role for Bedrock to access S3"
        )
