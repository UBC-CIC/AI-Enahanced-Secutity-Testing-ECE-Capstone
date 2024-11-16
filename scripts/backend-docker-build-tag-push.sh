#!/bin/bash

# Variables
AWS_ACCOUNT_ID=619071345478
AWS_REGION=us-west-2
ECR_REPOSITORY=aest/backend
LOCAL_IMAGE=aest/backend:latest
ECR_IMAGE=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
DOCKERFILE_PATH=../src/backend/Dockerfile
BUILD_CONTEXT=../src/backend

# Build the Docker image
docker buildx build --platform linux/amd64 -t $LOCAL_IMAGE -f $DOCKERFILE_PATH $BUILD_CONTEXT

# Authenticate Docker to AWS ECR
aws ecr get-login-password --region $AWS_REGION | \
docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag the Docker image
docker tag $LOCAL_IMAGE $ECR_IMAGE

# Push the Docker image to ECR
docker push $ECR_IMAGE
