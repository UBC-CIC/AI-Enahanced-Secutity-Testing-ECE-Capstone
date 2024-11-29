from aws_cdk import (
    Stack,
    aws_sagemaker as sagemaker,
    aws_iam as iam,
    aws_logs as logs
)
from constructs import Construct
from config import HUGGING_FACE_HUB_TOKEN

class LlmStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sagemaker_role = iam.Role(
            self, "SageMakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess")
            ]
        )

        # Create CloudWatch Log Group
        log_group = logs.LogGroup(
            self, "SageMakerEndpointLogs",
            retention=logs.RetentionDays.ONE_WEEK
        )

        model = sagemaker.CfnModel(
            self, "MistralModel",
            execution_role_arn=sagemaker_role.role_arn,
            primary_container={
                "image": f"763104351884.dkr.ecr.{self.region}.amazonaws.com/huggingface-pytorch-tgi-inference:2.1-tgi2.0-gpu-py310-cu121-ubuntu22.04",
                "environment": {
                    "HF_MODEL_ID": "mistralai/Mistral-7B-Instruct-v0.3",
                    "SM_NUM_GPUS": "1",
                    "MAX_INPUT_LENGTH": "8192",
                    "MAX_TOTAL_TOKENS": "12288",
                    "MAX_BATCH_TOTAL_TOKENS": "12288",
                    "MAX_BATCH_PREFILL_TOKENS": "8192",
                    "MESSAGES_API_ENABLED": "true",
                    "SAGEMAKER_CONTAINER_LOG_LEVEL": "INFO",
                    "SAGEMAKER_REGION": self.region,
                    "HF_TOKEN": HUGGING_FACE_HUB_TOKEN,
                    "HF_HUB_TOKEN": HUGGING_FACE_HUB_TOKEN,
                    "HUGGING_FACE_HUB_TOKEN": HUGGING_FACE_HUB_TOKEN,
                    "MAX_CONCURRENT_REQUESTS": "1",
                    "PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:256"
                }
            }
        )

        endpoint_config = sagemaker.CfnEndpointConfig(
            self, "MistralEndpointConfig",
            production_variants=[{
                "initialVariantWeight": 1.0,
                "modelName": model.attr_model_name,
                "variantName": "AllTraffic",
                # "instanceType": "ml.g5.2xlarge",
                "instanceType": "ml.g5.4xlarge",
                "initialInstanceCount": 1
            }]
        )

        self.endpoint = sagemaker.CfnEndpoint(
            self, "MistralEndpoint",
            endpoint_config_name=endpoint_config.attr_endpoint_config_name,
            endpoint_name="mistral-endpoint"
        )

        self.endpoint.node.add_dependency(model)
        self.endpoint.node.add_dependency(endpoint_config)
