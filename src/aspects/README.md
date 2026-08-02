# AWS CDK Aspects

An [aspect](https://docs.aws.amazon.com/cdk/v2/guide/aspects.html) visits every construct in a scope during the prepare phase. That makes it the right place for a rule you want applied everywhere, without every stack having to remember it.

Each aspect here either **corrects** a property or **reports** a problem. The split is deliberate: correct when there's one right answer, report when the author has a real decision to make.

## Available aspects

| Aspect                     | Behaviour       | What it catches                                                                   |
| -------------------------- | --------------- | --------------------------------------------------------------------------------- |
| `PermissionBoundaryAspect` | Corrects        | IAM roles with no permissions boundary, or a weaker one than the account requires |
| `BucketPublicAccessAspect` | Corrects, warns | S3 buckets that don't block public access                                         |
| `BucketEncryptionAspect`   | Errors          | S3 buckets with no server-side encryption                                         |
| `VpcCidrAspect`            | Errors          | VPCs on address space outside the RFC 1918 private ranges                         |

## Usage

Apply an aspect to the whole app, a single stack, or any construct in between. Scope it as widely as the rule applies:

```python
import aws_cdk as cdk
from aspects import BucketEncryptionAspect, BucketPublicAccessAspect, PermissionBoundaryAspect, VpcCidrAspect

app = cdk.App()

cdk.Aspects.of(app).add(BucketEncryptionAspect())
cdk.Aspects.of(app).add(BucketPublicAccessAspect())
cdk.Aspects.of(app).add(VpcCidrAspect())
cdk.Aspects.of(app).add(PermissionBoundaryAspect(f"arn:aws:iam::{account}:policy/base-permission-boundary"))
```

None of them are applied in [`app.py`](../app.py) by default. Pick the ones your account actually needs and add them there.

An aspect that calls `Annotations.add_error` fails `cdk synth`, so it blocks a deployment rather than reporting after the fact.

## Writing your own

Implement `visit`, and decorate the class with `@jsii.implements(IAspect)` so the CDK recognises it:

```python
import jsii
from aws_cdk import Annotations, IAspect
from aws_cdk import aws_sqs as sqs
from constructs import IConstruct


@jsii.implements(IAspect)
class QueueEncryptionAspect:
    def visit(self, node: IConstruct) -> None:
        if isinstance(node, sqs.CfnQueue) and not node.kms_master_key_id:
            Annotations.of(node).add_error("SQS queue is not encrypted with a KMS key.")
```

Two things to know before you read an L1 property in an aspect:

- **Some reads raise.** jsii cannot deserialize a struct that was set from the TypeScript side, so reading it raises `ValueError: Unknown interface`. `BucketPublicAccessAspect` hits this on any bucket built through the `Bucket` L2 construct and catches it. Check your property against both an L1 and an L2 construct before trusting the read.
- **Some values are tokens.** A property resolved at deploy time is not readable at synthesis time. `Tokenization.is_resolvable` tells you, and the right move is usually to leave it alone rather than override a value you can't see.
