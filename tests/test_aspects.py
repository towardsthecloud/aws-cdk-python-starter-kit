import aws_cdk as cdk
import pytest
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk.assertions import Annotations, Match, Template

from aspects import (
    BucketEncryptionAspect,
    BucketPublicAccessAspect,
    PermissionBoundaryAspect,
    VpcCidrAspect,
)

BOUNDARY_ARN = "arn:aws:iam::123456789012:policy/base-permission-boundary"


def new_stack() -> cdk.Stack:
    return cdk.Stack(
        cdk.App(),
        "aspect-test",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )


def lambda_role(stack: cdk.Stack, id: str, **kwargs) -> iam.Role:
    """Build a role for the boundary tests.

    ty reads IPrincipal structurally and every jsii-generated PrincipalBase subclass names its
    parameter `_statement` where the protocol says `statement`, so no CDK principal satisfies
    the check. The runtime type is correct, and keeping the suppression here means the tests
    below do not each carry one.
    """
    principal = iam.ServicePrincipal("lambda.amazonaws.com")
    return iam.Role(stack, id, assumed_by=principal, **kwargs)  # ty: ignore[invalid-argument-type]


def test_permission_boundary_is_attached_to_every_role():
    stack = new_stack()
    lambda_role(stack, "Role")
    cdk.Aspects.of(stack).add(PermissionBoundaryAspect(BOUNDARY_ARN))

    Template.from_stack(stack).has_resource_properties(
        "AWS::IAM::Role", {"PermissionsBoundary": BOUNDARY_ARN}
    )


def test_permission_boundary_overrides_an_existing_one():
    """The account-wide boundary wins, so a role-level one cannot widen what the role may do."""
    stack = new_stack()
    lambda_role(
        stack,
        "Role",
        permissions_boundary=iam.ManagedPolicy.from_managed_policy_arn(
            stack, "Weaker", "arn:aws:iam::123456789012:policy/weaker"
        ),
    )
    cdk.Aspects.of(stack).add(PermissionBoundaryAspect(BOUNDARY_ARN))

    Template.from_stack(stack).has_resource_properties(
        "AWS::IAM::Role", {"PermissionsBoundary": BOUNDARY_ARN}
    )


def test_bucket_encryption_aspect_errors_on_an_unencrypted_bucket():
    stack = new_stack()
    s3.CfnBucket(stack, "Bucket")
    cdk.Aspects.of(stack).add(BucketEncryptionAspect())

    Annotations.from_stack(stack).has_error(
        "*", Match.string_like_regexp("encryption is not enabled")
    )


def test_bucket_encryption_aspect_accepts_an_encrypted_bucket():
    stack = new_stack()
    s3.Bucket(stack, "Bucket", encryption=s3.BucketEncryption.S3_MANAGED)
    cdk.Aspects.of(stack).add(BucketEncryptionAspect())

    Annotations.from_stack(stack).has_no_error(
        "*", Match.string_like_regexp("encryption is not enabled")
    )


def test_public_access_aspect_blocks_a_bucket_with_no_configuration():
    stack = new_stack()
    s3.CfnBucket(stack, "Bucket")
    cdk.Aspects.of(stack).add(BucketPublicAccessAspect())

    Template.from_stack(stack).has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )


def test_public_access_aspect_leaves_a_compliant_l1_bucket_alone():
    stack = new_stack()
    s3.CfnBucket(
        stack,
        "Bucket",
        public_access_block_configuration=s3.CfnBucket.PublicAccessBlockConfigurationProperty(
            block_public_acls=True, block_public_policy=True
        ),
    )
    cdk.Aspects.of(stack).add(BucketPublicAccessAspect())

    Annotations.from_stack(stack).has_no_warning(
        "*", Match.string_like_regexp("has public access")
    )


def test_public_access_aspect_survives_a_bucket_built_through_the_l2_construct():
    """jsii cannot read back a struct set from TypeScript, and the aspect must not crash on it.

    `s3.Bucket(..., block_public_access=...)` sets the property from the TypeScript side, which
    raises `ValueError: Unknown interface` on read. Synthesis has to succeed regardless.
    """
    stack = new_stack()
    s3.Bucket(stack, "Bucket", block_public_access=s3.BlockPublicAccess.BLOCK_ALL)
    cdk.Aspects.of(stack).add(BucketPublicAccessAspect())

    Template.from_stack(stack).has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": Match.object_like(
                {"BlockPublicAcls": True}
            )
        },
    )


@pytest.mark.parametrize("cidr", ["10.0.0.0/16", "172.16.0.0/16", "192.168.0.0/24"])
def test_vpc_cidr_aspect_accepts_rfc1918_ranges(cidr):
    stack = new_stack()
    ec2.CfnVPC(stack, "Vpc", cidr_block=cidr)
    cdk.Aspects.of(stack).add(VpcCidrAspect())

    Annotations.from_stack(stack).has_no_error(
        "*", Match.string_like_regexp("does not comply")
    )


@pytest.mark.parametrize("cidr", ["11.0.0.0/16", "172.32.0.0/16", "8.8.8.0/24"])
def test_vpc_cidr_aspect_errors_on_public_ranges(cidr):
    stack = new_stack()
    ec2.CfnVPC(stack, "Vpc", cidr_block=cidr)
    cdk.Aspects.of(stack).add(VpcCidrAspect())

    Annotations.from_stack(stack).has_error(
        "*", Match.string_like_regexp("does not comply")
    )


def test_vpc_cidr_aspect_skips_a_vpc_without_a_literal_cidr():
    """A VPC from an IPAM pool has no CIDR to check at synthesis time."""
    stack = new_stack()
    ec2.CfnVPC(stack, "Vpc", ipv4_ipam_pool_id="ipam-pool-1234", ipv4_netmask_length=16)
    cdk.Aspects.of(stack).add(VpcCidrAspect())

    Annotations.from_stack(stack).has_no_error(
        "*", Match.string_like_regexp("does not comply")
    )
