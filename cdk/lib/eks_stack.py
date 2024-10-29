from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_eks as eks,
)
from constructs import Construct

class EksStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.cluster = eks.Cluster(
            self, "EksCluster",
            vpc=vpc,
            version=eks.KubernetesVersion.V1_31,
            default_capacity=2  # Default node group with 2 instances
        )
