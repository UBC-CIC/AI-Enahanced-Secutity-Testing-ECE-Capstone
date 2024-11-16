#!/usr/bin/env python3
import aws_cdk as cdk
from lib.vpc_stack import AestVpcStack
from lib.eks_stack import EksStack
from lib.s3_stack import S3Stack
from lib.eks_s3_access_stack import EksS3AccessStack

app = cdk.App()

vpc_stack = AestVpcStack(app, "AestVpcStack")

eks_stack = EksStack(app, "EksStack", vpc=vpc_stack.vpc)
s3_stack = S3Stack(app, "S3Stack")
EksS3AccessStack(
    app, 
    "EksS3AccessStack",
    cluster=eks_stack.cluster,
    s3_bucket=s3_stack.bucket
)

app.synth()
