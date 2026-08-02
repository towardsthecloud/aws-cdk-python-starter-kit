from aws_cdk import Stack
from constructs import Construct

# from custom_constructs.network_construct import NetworkConstruct


class StarterStack(Stack):
    """The starting point for your own infrastructure.

    Add your constructs and resources in the constructor. For anything that grows past a
    handful of related resources, add another stack next to this one rather than letting this
    one sprawl.

    Args:
        scope: The scope in which to define this stack.
        id: The scoped construct ID.
        environment: The deployment stage, for example `test` or `production`.

    Example:
        Adding an S3 bucket:

        ```python
        from aws_cdk import aws_s3 as s3

        # In the constructor:
        s3.Bucket(
            self,
            "MyBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )
        ```
    """

    def __init__(
        self, scope: Construct, id: str, environment: str | None = None, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.environment_name = environment

        # ↓↓ Add your constructs and resources below ↓↓

        # Sample construct that creates a secure VPC
        # NetworkConstruct(self, "NetworkConstruct")
