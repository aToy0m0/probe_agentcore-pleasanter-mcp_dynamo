"""Per-user API keys, encrypted before entering DynamoDB."""

import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import boto3


def principal_id(issuer, subject):
    return "user#" + hashlib.sha256((issuer + "\n" + subject).encode()).hexdigest()


def encryption_context(principal):
    return {"purpose": "pleasanter-mcp-dynamo-probe", "principal": principal}


def read_item(principal, **options):
    return boto3.client("dynamodb").get_item(
        TableName=os.environ["KEY_TABLE"], Key={"principal": {"S": principal}},
        ConsistentRead=True, **options,
    ).get("Item")


def key_status(principal):
    return read_item(principal, ProjectionExpression="#state, updatedAt, revision",
                     ExpressionAttributeNames={"#state": "state"})


def replace_key(principal, previous, api_key):
    updated_at = datetime.now(timezone.utc).isoformat()
    item = {
        "principal": {"S": principal},
        "revision": {"S": uuid4().hex},
        "updatedAt": {"S": updated_at},
        "state": {"S": "disabled" if api_key is None else "active"},
    }
    if api_key is not None:
        ciphertext = boto3.client("kms").encrypt(
            KeyId=os.environ["ENCRYPTION_KEY"], Plaintext=api_key.encode("ascii"),
            EncryptionContext=encryption_context(principal),
        )["CiphertextBlob"]
        item["ciphertext"] = {"B": ciphertext}
    condition = {"ConditionExpression": "attribute_not_exists(principal)"}
    if previous is not None:
        condition = {
            "ConditionExpression": "revision = :revision",
            "ExpressionAttributeValues": {":revision": previous["revision"]},
        }
    boto3.client("dynamodb").put_item(TableName=os.environ["KEY_TABLE"], Item=item, **condition)
    return updated_at


def load_key(principal):
    item = read_item(principal)
    if item is None or item["state"]["S"] == "disabled":
        return None
    if item["state"]["S"] != "active":
        raise ValueError("Unexpected key state")
    return boto3.client("kms").decrypt(
        KeyId=os.environ["ENCRYPTION_KEY"], CiphertextBlob=item["ciphertext"]["B"],
        EncryptionContext=encryption_context(principal),
    )["Plaintext"].decode("ascii")
