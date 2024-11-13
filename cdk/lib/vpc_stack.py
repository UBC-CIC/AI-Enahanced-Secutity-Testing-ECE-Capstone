from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct

class AestVpcStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self, "AestVpc",
            max_azs=2, 
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="AestPublicSubnet",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="AestPrivateSubnet",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
            ]
        )
