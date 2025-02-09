# AWS Infrastructure Deployment Guide

## Overview

This guide explains how to deploy the AWS infrastructure for our AI-Enhanced Security Testing platform using AWS CDK. The infrastructure consists of VPC, EKS cluster, S3 storage, and optional LLM (SageMaker) components.

## Prerequisites

```bash
# Install AWS CDK
npm install -g aws-cdk

# Install Python dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure
```

> Python virtual environment is recommended 

## Deployment Steps

1. Bootstrap CDK (first-time only): `cdk bootstrap`
2. Review changes: `cdk diff`
3. Deploy infrastructure
    - Deploy all stacks: `cdk deploy`
    - Deploy individual stacks: `cdk deploy <stack-name>`
4. (Optional) Get deployment outputs

## Cleanup

> This cleanup is highly not recommended unless you are sure about the consequences.

`cdk destroy --all`

## Best Practices
1. Always review cdk diff before deployment
2. Use version control for infrastructure code
3. Monitor CloudWatch logs during deployment
4. Keep infrastructure stacks modular and independent
