#!/usr/bin/env python3
import aws_cdk as cdk
from lib.vpc_stack import VpcStack
from lib.eks_stack import EksStack
from lib.s3_stack import S3Stack

app = cdk.App()

vpc_stack = VpcStack(app, "VpcStack")

EksStack(app, "EksStack", vpc=vpc_stack.vpc)
S3Stack(app, "S3Stack")

app.synth()
