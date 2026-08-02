import jsii
from aws_cdk import CfnResource, IAspect
from constructs import IConstruct


@jsii.implements(IAspect)
class PermissionBoundaryAspect:
    """Attach a permissions boundary to every IAM role in the scope.

    A boundary caps what a role can do no matter what its policies grant, so applying one
    across the app closes the gap where a single over-permissive policy slips through review.
    Roles that already carry a boundary are overridden, which is deliberate: the account-wide
    boundary wins.

    Example:
        ```python
        Aspects.of(app).add(PermissionBoundaryAspect(f"arn:aws:iam::{account}:policy/base-permission-boundary"))
        ```

    See:
        https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-iam-role.html#cfn-iam-role-permissionsboundary
    """

    def __init__(self, permissions_boundary_arn: str) -> None:
        """
        Args:
            permissions_boundary_arn: ARN of the managed policy to attach as the boundary.
        """
        self.permissions_boundary_arn = permissions_boundary_arn

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, CfnResource) and node.cfn_resource_type == "AWS::IAM::Role":
            node.add_property_override(
                "PermissionsBoundary", self.permissions_boundary_arn
            )
