import ipaddress

import jsii
from aws_cdk import Annotations, IAspect
from aws_cdk import aws_ec2 as ec2
from constructs import IConstruct

# The three private address blocks from RFC 1918.
PRIVATE_BLOCKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)

RFC1918_RANGES = """
          10.0.0.0        -   10.255.255.255  (10/8 prefix)
          172.16.0.0      -   172.31.255.255  (172.16/12 prefix)
          192.168.0.0     -   192.168.255.255 (192.168/16 prefix)"""


@jsii.implements(IAspect)
class VpcCidrAspect:
    """Fail synthesis when a VPC CIDR falls outside the RFC 1918 private ranges.

    A VPC on public address space routes badly against peered networks and on-premises
    ranges, and the mistake is cheap to make and expensive to undo: a VPC CIDR cannot be
    changed after creation.

    A VPC whose CIDR is still an unresolved token is skipped, since its value is not known
    at synthesis time.

    Example:
        ```python
        Aspects.of(app).add(VpcCidrAspect())
        ```

    See:
        http://www.faqs.org/rfcs/rfc1918.html
    """

    def visit(self, node: IConstruct) -> None:
        if not isinstance(node, ec2.CfnVPC):
            return

        cidr_block = node.cidr_block
        if cidr_block is None:
            # A VPC built from an IPAM pool has no literal CIDR to check.
            return

        try:
            cidr = ipaddress.ip_network(cidr_block, strict=False)
        except ValueError:
            # Either an unresolved token or a malformed value; CloudFormation rejects the
            # latter with a clearer message than this aspect could give.
            return

        if any(
            cidr.subnet_of(block)
            for block in PRIVATE_BLOCKS
            if cidr.version == block.version
        ):
            return

        Annotations.of(node).add_error(
            f"\nYour current VPC Cidr range {node.cidr_block} does not comply with "
            f"the standard CIDR range in block: \n{RFC1918_RANGES}"
        )
