from aws_cdk import (
    aws_iam as iam,
    aws_eks as eks,
    aws_s3 as s3,
    CfnJson,
    Stack,
)
from constructs import Construct

class EksS3AccessStack(Stack):
    def __init__(self, scope: Construct, id: str, cluster: eks.Cluster, s3_bucket: s3.Bucket, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define the IAM policy for accessing the S3 bucket
        s3_policy = iam.PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            resources=[
                s3_bucket.bucket_arn,
                f"{s3_bucket.bucket_arn}/*"
            ]
        )

        # Use CfnJson to create the dynamic StringEquals condition
        string_equals_condition = CfnJson(
            self, "StringEqualsCondition",
            value={
                f"{cluster.cluster_open_id_connect_issuer}:sub": "system:serviceaccount:default:s3-access-sa"
            }
        )

        # Create IAM Role for the Service Account
        role = iam.Role(
            self, "EksS3AccessRole",
            assumed_by=iam.WebIdentityPrincipal(
                cluster.open_id_connect_provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": string_equals_condition
                }
            )
        )
        role.add_to_policy(s3_policy)

        # Define Kubernetes Service Account with the IAM Role
        s3_access_service_account = eks.ServiceAccount(
            self, "S3AccessServiceAccount",
            cluster=cluster,
            name="s3-access-sa",
            namespace="default"
        )

        # Attach the policy to the Service Account
        s3_access_service_account.add_to_principal_policy(s3_policy)

        # Output the S3 bucket name for reference
        self.output_s3_bucket = s3_bucket.bucket_name
