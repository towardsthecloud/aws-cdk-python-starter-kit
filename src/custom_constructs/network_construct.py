from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct

from .base_construct import BaseConstruct


class NetworkConstruct(BaseConstruct):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        # Determine bucket properties based on the environment
        is_production = self.environment == "production"

        # Create a VPC with 9 subnets divided over 3 AZs (3 public, 3 private, 3 isolated)
        cidr = (
            "172.16.0.0/16"
            if self.environment == "dev"
            else "172.17.0.0/16"
            if self.environment == "test"
            else "172.18.0.0/16"
        )
        nat_gateways = 3 if self.environment == "production" else 1

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr(cidr),
            nat_gateways=nat_gateways,
            max_azs=3,
            flow_logs={
                "s3": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_s3(
                        s3.Bucket(
                            self,
                            "VpcFlowLogBucket",
                            encryption=s3.BucketEncryption.S3_MANAGED,
                            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                            auto_delete_objects=None if is_production else True,
                            removal_policy=None
                            if is_production
                            else RemovalPolicy.DESTROY,
                        )
                    ),
                    traffic_type=ec2.FlowLogTrafficType.REJECT,
                )
            },
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=20,
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
                ec2.SubnetConfiguration(
                    cidr_mask=20,
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
                ec2.SubnetConfiguration(
                    cidr_mask=20,
                    name="isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                ),
            ],
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
