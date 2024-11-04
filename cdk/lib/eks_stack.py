import yaml

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_eks as eks,
)

from aws_cdk.lambda_layer_kubectl_v31 import KubectlV31Layer
from constructs import Construct
from config import IAM_ROLE_ARN



class EksStack(Stack):
    dast_deployment_path = "eks_manifests/dast_deployment.yaml"
    dast_service_path = "eks_manifests/dast_service.yaml"
    backend_deployment_path = "eks_manifests/backend_deployment.yaml"
    backend_service_path = "eks_manifests/backend_service.yaml"

    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        print(f"IAM_ROLE_ARN: {IAM_ROLE_ARN}")

        self.cluster = eks.Cluster(
            self, "AestEks",
            vpc=vpc,
            version=eks.KubernetesVersion.V1_31,
            kubectl_layer = KubectlV31Layer(self, "KubectlLayer"),
            default_capacity=2 
        )

        self.cluster.add_manifest(
            "DastDeployment",
            self.load_eks_manifest(self.dast_deployment_path)
        )
        self.cluster.add_manifest(
            "DastService",
            self.load_eks_manifest(self.dast_service_path)
        )
        
        self.cluster.add_manifest(
            "BackendDeployment", self.load_eks_manifest(self.backend_deployment_path)
        )
        self.cluster.add_manifest(
            "BackendService", self.load_eks_manifest(self.backend_service_path)
        )

        capstone_role = iam.Role.from_role_arn(self, "ExternalRole", IAM_ROLE_ARN)
        self.cluster.aws_auth.add_role_mapping(capstone_role, groups=["system:masters"], username="devops")

    def load_eks_manifest(self, path):
        with open(path, 'r') as file:
            return yaml.safe_load(file)
