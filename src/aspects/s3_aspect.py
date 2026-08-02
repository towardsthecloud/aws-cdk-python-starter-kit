import jsii
from aws_cdk import Annotations, IAspect, Tokenization
from aws_cdk import aws_s3 as s3
from constructs import IConstruct


@jsii.implements(IAspect)
class BucketEncryptionAspect:
    """Fail synthesis when a bucket has no server-side encryption configured.

    This one reports rather than corrects: the encryption choice decides who can read the
    objects (SSE-S3 versus SSE-KMS with a specific key), so silently picking one would hide a
    decision the author should make.

    Example:
        ```python
        Aspects.of(app).add(BucketEncryptionAspect())
        ```
    """

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, s3.CfnBucket) and not node.bucket_encryption:
            Annotations.of(node).add_error("S3 bucket encryption is not enabled.")


@jsii.implements(IAspect)
class BucketPublicAccessAspect:
    """Block public access on every bucket that does not already block it.

    Unlike encryption there is one right answer here, so this aspect corrects the property and
    warns instead of failing.

    Two cases are deliberately left alone, because in both the property is set to something
    this aspect cannot read and overriding it would discard a deliberate configuration:

    - An unresolved token, whose value is not known at synthesis time.
    - A configuration set through the `Bucket` L2 construct. jsii cannot deserialize that
      struct back into Python and raises `ValueError: Unknown interface` on the read, so a
      bucket built with `block_public_access=BlockPublicAccess.BLOCK_ALL` is skipped. The
      case this aspect exists to catch, a bucket with no configuration at all, reads cleanly
      as `None` and is still corrected.

    Example:
        ```python
        Aspects.of(app).add(BucketPublicAccessAspect())
        ```

    See:
        https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-publicaccessblockconfiguration.html
    """

    def visit(self, node: IConstruct) -> None:
        if not isinstance(node, s3.CfnBucket):
            return

        try:
            configuration = node.public_access_block_configuration
        except ValueError:
            return

        # Only a bucket with no configuration at all falls through to the correction below.
        if configuration is not None:
            if Tokenization.is_resolvable(configuration):
                return
            if not isinstance(
                configuration, s3.CfnBucket.PublicAccessBlockConfigurationProperty
            ):
                return
            if configuration.block_public_acls is True:
                return

        Annotations.of(node).add_warning(
            f"S3 bucket: {node.bucket_name} has public access! "
            "This is not recommended. "
            "Therefore correcting the publicAccessBlockConfiguration property using Aspects"
        )
        node.add_property_override(
            "PublicAccessBlockConfiguration",
            {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        )
