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
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        print(f"IAM_ROLE_ARN: {IAM_ROLE_ARN}")

        self.cluster = eks.Cluster(
            self, "AestEks",
            vpc=vpc,
            version=eks.KubernetesVersion.V1_31,
            kubectl_layer=KubectlV31Layer(self, "KubectlLayer"),
            default_capacity=1,
            default_capacity_instance=ec2.InstanceType("t3.small")
        )

        # Map Capstone role for cluster admin access
        capstone_role = iam.Role.from_role_arn(self, "ExternalRole", IAM_ROLE_ARN)
        self.cluster.aws_auth.add_role_mapping(capstone_role, groups=["system:masters"], username="devops")

        # Add a service account for the backend deployment
        backend_service_account = self.cluster.add_service_account(
            "BackendServiceAccount",
            name="backend-sa",
            namespace="default",
        )

        # Attach permissions for backend service account to trigger jobs
        backend_service_account.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "batch:CreateJob",
                    "batch:DeleteJob",
                    "batch:DescribeJob",
                    "batch:ListJobs",
                ],
                resources=["*"],
            )
        )

        # Grant Kubernetes permissions to manage jobs in the default namespace
        job_permissions = eks.KubernetesManifest(
            self, "JobPermissions",
            cluster=self.cluster,
            manifest=[
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "Role",
                    "metadata": {
                        "namespace": "default",
                        "name": "zap-job-role",
                    },
                    "rules": [
                        {
                            "apiGroups": [""],
                            "resources": ["pods", "pods/log", "configmaps", "secrets"],
                            "verbs": ["get", "list", "watch", "create", "delete"],
                        },
                        {
                            "apiGroups": ["batch"],
                            "resources": ["jobs", "jobs/status"],
                            "verbs": ["create", "delete", "get", "list", "watch"],
                        },
                    ],
                },
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "RoleBinding",
                    "metadata": {
                        "namespace": "default",
                        "name": "zap-job-rolebinding",
                    },
                    "subjects": [
                        {
                            "kind": "ServiceAccount",
                            "name": "backend-sa",
                            "namespace": "default",
                        }
                    ],
                    "roleRef": {
                        "kind": "Role",
                        "name": "zap-job-role",
                        "apiGroup": "rbac.authorization.k8s.io",
                    },
                },
            ]
        )

        # Add dependency to ensure RBAC configuration is applied before the backend service account uses it
        backend_service_account.node.add_dependency(job_permissions)
