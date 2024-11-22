#!/usr/bin/env python3
import aws_cdk as cdk
from lib.vpc_stack import AestVpcStack
from lib.eks_stack import EksStack
from lib.s3_stack import S3Stack
from aws_cdk import App, CfnOutput

app = App()

vpc_stack = AestVpcStack(app, "AestVpcStack")
s3_stack = S3Stack(app, "S3Stack", vpc=vpc_stack.vpc)
eks_stack = EksStack(app, "EksStack", 
    vpc=vpc_stack.vpc,
    bucket=s3_stack.bucket
)

# Output the bucket name for use in Helm values
CfnOutput(s3_stack, "BucketName",
    value=s3_stack.bucket.bucket_name,
    description="Name of the S3 bucket for ZAP reports"
)

app.synth()
