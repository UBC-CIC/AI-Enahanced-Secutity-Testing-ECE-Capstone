import yaml
import json

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_s3 as s3,
    CfnJson,
)

from aws_cdk.lambda_layer_kubectl_v31 import KubectlV31Layer
from constructs import Construct
from config import IAM_ROLE_ARN, EKS_BACKEND_SERVICE_ACCOUNT_ROLE_ARN


class EksStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, bucket: s3.Bucket, **kwargs) -> None:
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

        # Add S3 permissions to the node role
        self.cluster.default_nodegroup.role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListBucket",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                resources=[
                    bucket.bucket_arn,
                    f"{bucket.bucket_arn}/*"
                ]
            )
        )

        # Map Capstone role for cluster admin access
        capstone_role = iam.Role.from_role_arn(self, "ExternalRole", IAM_ROLE_ARN)
        self.cluster.aws_auth.add_role_mapping(capstone_role, groups=["system:masters"], username="devops")

        # Create backend service account with all necessary permissions
        backend_service_account = self.cluster.add_service_account(
            "BackendServiceAccount",
            name="backend-sa",
            namespace="default",
            annotations={
                "eks.amazonaws.com/role-arn": EKS_BACKEND_SERVICE_ACCOUNT_ROLE_ARN
            }
        )

        # Create CfnJson for the conditions
        string_like = CfnJson(self, "ConditionJson", 
            value={
                f"{self.cluster.open_id_connect_provider.open_id_connect_provider_issuer}:sub": [
                    "system:serviceaccount:default:backend-sa",
                    "system:serviceaccount:kube-system:s3-csi-*"
                ],
                f"{self.cluster.open_id_connect_provider.open_id_connect_provider_issuer}:aud": "sts.amazonaws.com"
            }
        )

        # Add trust policy conditions
        backend_service_account.role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                actions=["sts:AssumeRoleWithWebIdentity"],
                conditions={
                    "StringLike": string_like
                },
                principals=[iam.OpenIdConnectPrincipal(self.cluster.open_id_connect_provider)]
            )
        )

        # Create our own S3 CSI Driver policy
        csi_policy = iam.PolicyStatement(
            sid="MountpointFullBucketAccess",
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:ListBucket"
            ],
            resources=[bucket.bucket_arn]
        )

        object_policy = iam.PolicyStatement(
            sid="MountpointFullObjectAccess",
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:AbortMultipartUpload",
                "s3:DeleteObject"
            ],
            resources=[f"{bucket.bucket_arn}/*"]
        )

        # Add SageMaker endpoint invocation permissions
        sagemaker_policy = iam.PolicyStatement(
            sid="SageMakerEndpointInvoke",
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:InvokeEndpoint"
            ],
            resources=[
                f"arn:aws:sagemaker:{self.region}:{self.account}:endpoint/*"
            ]
        )

        backend_service_account.add_to_principal_policy(csi_policy)
        backend_service_account.add_to_principal_policy(object_policy)
        backend_service_account.add_to_principal_policy(sagemaker_policy)

        # Grant Kubernetes permissions for CSI driver and jobs
        job_permissions = eks.KubernetesManifest(
            self, "JobPermissions",
            cluster=self.cluster,
            manifest=[
                # CSI Driver RBAC
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "ClusterRole",
                    "metadata": {
                        "name": "s3-csi-driver-role"
                    },
                    "rules": [
                        {
                            "apiGroups": [""],
                            "resources": ["serviceaccounts"],
                            "verbs": ["get", "list", "watch"]
                        },
                        {
                            "apiGroups": [""],
                            "resources": ["persistentvolumes"],
                            "verbs": ["get", "list", "watch", "create", "delete"]
                        },
                        {
                            "apiGroups": [""],
                            "resources": ["persistentvolumeclaims"],
                            "verbs": ["get", "list", "watch"]
                        },
                        {
                            "apiGroups": [""],
                            "resources": ["events"],
                            "verbs": ["get", "list", "watch", "create", "update", "patch"]
                        },
                        {
                            "apiGroups": [""],
                            "resources": ["pods"],
                            "verbs": ["get", "list", "watch"]
                        },
                        {
                            "apiGroups": ["storage.k8s.io"],
                            "resources": ["volumeattachments"],
                            "verbs": ["get", "list", "watch", "create", "delete"]
                        }
                    ]
                },
                {
                    "apiVersion": "rbac.authorization.k8s.io/v1",
                    "kind": "ClusterRoleBinding",
                    "metadata": {
                        "name": "s3-csi-driver-binding"
                    },
                    "subjects": [
                        {
                            "kind": "ServiceAccount",
                            "name": "backend-sa",
                            "namespace": "default"
                        }
                    ],
                    "roleRef": {
                        "kind": "ClusterRole",
                        "name": "s3-csi-driver-role",
                        "apiGroup": "rbac.authorization.k8s.io"
                    }
                },
                # Job Role
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
                        {
                            "apiGroups": ["storage.k8s.io"],
                            "resources": ["storageclasses"],
                            "verbs": ["get", "list", "watch", "delete"], 
                        }
                    ],
                },
                # RoleBinding
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

        backend_service_account.node.add_dependency(job_permissions)

        # Add S3 CSI Driver addon with tolerations
        csi_addon = eks.CfnAddon(
            self, "S3CsiDriverAddon",
            addon_name="aws-mountpoint-s3-csi-driver",
            cluster_name=self.cluster.cluster_name,
            service_account_role_arn=backend_service_account.role.role_arn,
            resolve_conflicts="OVERWRITE",
            addon_version="v1.9.0-eksbuild.1",
            configuration_values=json.dumps({
                "node": {
                    "tolerations": [{
                        "key": "CriticalAddonsOnly",
                        "operator": "Exists",
                        "effect": "NoSchedule"
                    }]
                }
            })
        )

        csi_addon.node.add_dependency(backend_service_account)
