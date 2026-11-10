"""Check the generated Lambda code and role boundaries without AWS calls."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

import build


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.registration = {}
        exec(build.registration_code, self.registration)
        self.ddb, self.kms = Mock(), Mock()
        self.ddb.get_item.return_value = {}
        self.kms.encrypt.return_value = {"CiphertextBlob": b"ciphertext"}
        env = patch.dict("os.environ", {"KEY_TABLE": "probe", "ENCRYPTION_KEY": "kms",
                                         "ISSUER": "issuer", "CLIENT_ID": "client", "AUDIENCE": "client"})
        clients = patch("boto3.client", side_effect={"dynamodb": self.ddb, "kms": self.kms}.__getitem__)
        self.addCleanup(env.stop)
        self.addCleanup(clients.stop)
        env.start()
        clients.start()

    def request(self, route, body=None, client="client"):
        return self.registration["handler"]({
            "routeKey": route, "body": json.dumps(body),
            "requestContext": {"authorizer": {"jwt": {"claims": {
                "iss": "issuer", "sub": "owner-id", "token_use": "access", "client_id": client,
            }}}},
        }, SimpleNamespace(aws_request_id="test"))

    def test_registration_binds_ciphertext_to_authenticated_principal(self):
        route = "PUT /me/pleasanter-key"
        self.assertEqual(self.request(route, {"apiKey": "dummy", "sub": "other"})["statusCode"], 400)
        self.assertEqual(self.request(route, {"apiKey": "dummy"}, client="mcp-client")["statusCode"], 401)
        self.ddb.get_item.assert_not_called()
        self.assertEqual(self.request(route, {"apiKey": "dummy"})["statusCode"], 200)
        written = self.ddb.put_item.call_args.kwargs
        principal = self.registration["principal_id"]("issuer", "owner-id")
        self.assertEqual(written["Item"]["principal"], {"S": principal})
        self.assertEqual(written["Item"]["ciphertext"], {"B": b"ciphertext"})
        self.assertNotIn("dummy", repr(written))
        self.assertEqual(self.kms.encrypt.call_args.kwargs["EncryptionContext"]["principal"], principal)

    def test_stale_delete_returns_conflict_and_status_does_not_decrypt(self):
        self.ddb.get_item.return_value = {"Item": {
            "revision": {"S": "old"}, "state": {"S": "active"}, "updatedAt": {"S": "date"},
        }}
        status = self.request("GET /me/pleasanter-key/status")
        self.assertEqual(json.loads(status["body"]), {"registered": True, "updatedAt": "date"})
        self.assertTrue(self.ddb.get_item.call_args.kwargs["ConsistentRead"])
        self.ddb.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.assertEqual(self.request("DELETE /me/pleasanter-key")["statusCode"], 409)
        written = self.ddb.put_item.call_args.kwargs
        self.assertEqual(written["ExpressionAttributeValues"], {":revision": {"S": "old"}})
        self.assertEqual(written["Item"]["state"], {"S": "disabled"})
        self.assertNotIn("ciphertext", written["Item"])
        self.kms.decrypt.assert_not_called()
        self.kms.encrypt.assert_not_called()

    def test_adapter_does_not_decrypt_disabled_keys(self):
        adapter = {}
        exec(build.code, adapter)
        self.ddb.get_item.return_value = {"Item": {"state": {"S": "disabled"}}}
        self.assertIsNone(adapter["load_key"]("user#owner"))
        self.kms.decrypt.assert_not_called()
        self.ddb.get_item.return_value = {"Item": {
            "state": {"S": "active"}, "ciphertext": {"B": b"ciphertext"},
        }}
        self.kms.decrypt.return_value = {"Plaintext": b"dummy"}
        self.assertEqual(adapter["load_key"]("user#owner"), "dummy")
        self.assertEqual(self.kms.decrypt.call_args.kwargs["EncryptionContext"]["principal"], "user#owner")
        self.assertTrue(self.ddb.get_item.call_args.kwargs["ConsistentRead"])

    def test_generated_roles_split_key_permissions(self):
        def actions(name):
            role = build.resources[name + "Role"]["Properties"]
            statements = role["Policies"][0]["PolicyDocument"]["Statement"]
            return {action for statement in statements for action in (
                statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
            )}

        self.assertIn("kms:Encrypt", actions("Registration"))
        self.assertNotIn("kms:Decrypt", actions("Registration"))
        self.assertIn("kms:Decrypt", actions("Adapter"))
        self.assertNotIn("dynamodb:PutItem", actions("Adapter"))
        self.assertNotIn("kms:Decrypt", actions("Mock"))
        self.assertFalse(any(resource["Type"] == "AWS::SecretsManager::Secret"
                             for resource in build.resources.values()))
