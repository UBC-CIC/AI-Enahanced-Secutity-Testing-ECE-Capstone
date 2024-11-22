# from aws_cdk import (
#     aws_iam as iam,
#     aws_eks as eks,
#     aws_s3 as s3,
#     CfnJson,
#     Stack,
# )
# from constructs import Construct

# class EksS3AccessStack(Stack):
#     def __init__(
#         self, 
#         scope: Construct, 
#         id: str, 
#         cluster: eks.Cluster, 
#         bucket: s3.Bucket,
#         **kwargs
#     ) -> None:
#         super().__init__(scope, id, **kwargs)

#         # S3 policy for CSI driver
#         self.s3_policy = iam.PolicyStatement(
#             actions=[
#                 "s3:ListBucket",
#                 "s3:GetObject",
#                 "s3:PutObject",
#                 "s3:DeleteObject",
#                 "s3:AbortMultipartUpload"
#             ],
#             resources=[
#                 bucket.bucket_arn,
#                 f"{bucket.bucket_arn}/*"
#             ]
#         )
