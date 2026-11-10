"""Generate one CloudFormation template with inline Lambda code."""

import hashlib
import json
import os
from pathlib import Path


def ref(name):
    return {"Ref": name}


def attr(name, key="Arn"):
    return {"Fn::GetAtt": [name, key]}


def sub(value):
    return {"Fn::Sub": value}


def allow(action, resource, **extra):
    return {"Effect": "Allow", "Action": action, "Resource": resource, **extra}


resources = {}


def resource(name, kind, **props):
    resources[name] = {"Type": "AWS::" + kind, "Properties": props}


def role(name, service, permissions, condition=None):
    trust = {"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"Service": service}}
    if condition:
        trust["Condition"] = condition
    resource(name, "IAM::Role", AssumeRolePolicyDocument={"Version": "2012-10-17", "Statement": [trust]},
             Policies=[{"PolicyName": "probe-only", "PolicyDocument": {
                 "Version": "2012-10-17", "Statement": permissions}}])


resource("Pool", "Cognito::UserPool", UserPoolName=ref("AWS::StackName"),
         AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
         Policies={"PasswordPolicy": {"MinimumLength": 16, "RequireUppercase": True,
                                     "RequireLowercase": True, "RequireNumbers": True,
                                     "RequireSymbols": True}},
         UserPoolTier="LITE")
resource("Client", "Cognito::UserPoolClient", UserPoolId=ref("Pool"), GenerateSecret=False,
         ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
         AllowedOAuthFlowsUserPoolClient=True, AllowedOAuthFlows=["code"],
         AllowedOAuthScopes=["openid", "aws.cognito.signin.user.admin"],
         SupportedIdentityProviders=["COGNITO"],
         CallbackURLs=[os.environ.get("PROBE_CALLBACK_URL", "http://127.0.0.1:38580/callback")],
         PreventUserExistenceErrors="ENABLED", EnableTokenRevocation=True,
         AccessTokenValidity=15, TokenValidityUnits={"AccessToken": "minutes"})
resource("LoginDomain", "Cognito::UserPoolDomain", UserPoolId=ref("Pool"),
         Domain=sub("mcp-dynamo-probe-${AWS::AccountId}"))

for logical, username in (("Owner", "owner"), ("Codex", "codex")):
    resource(logical + "User", "Cognito::UserPoolUser", UserPoolId=ref("Pool"),
             Username=username, MessageAction="SUPPRESS")

resource("SigningKey", "KMS::Key", KeySpec="RSA_2048", KeyUsage="SIGN_VERIFY",
         PendingWindowInDays=7, KeyPolicy={"Version": "2012-10-17", "Statement": [{
             "Effect": "Allow", "Principal": {"AWS": sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:root")},
             "Action": "kms:*", "Resource": "*"}]})
resources["SigningKey"].update(DeletionPolicy="Delete", UpdateReplacePolicy="Delete")

issuer = sub("https://cognito-idp.${AWS::Region}.${AWS::URLSuffix}/${Pool}")
resource("EncryptionKey", "KMS::Key", KeySpec="SYMMETRIC_DEFAULT", KeyUsage="ENCRYPT_DECRYPT",
         EnableKeyRotation=True, PendingWindowInDays=7, KeyPolicy=resources["SigningKey"]["Properties"]["KeyPolicy"])
resources["EncryptionKey"].update(DeletionPolicy="Delete", UpdateReplacePolicy="Delete")
resource("KeyTable", "DynamoDB::Table", BillingMode="PAY_PER_REQUEST",
         AttributeDefinitions=[{"AttributeName": "principal", "AttributeType": "S"}],
         KeySchema=[{"AttributeName": "principal", "KeyType": "HASH"}])
resources["KeyTable"].update(DeletionPolicy="Delete", UpdateReplacePolicy="Delete")

store_env = {"KEY_TABLE": ref("KeyTable"), "ENCRYPTION_KEY": attr("EncryptionKey")}


def table_access(actions, prefix):
    return allow(actions, attr("KeyTable"), Condition={
        "ForAllValues:StringLike": {"dynamodb:LeadingKeys": [prefix]},
        "Null": {"dynamodb:LeadingKeys": "false"},
    })


def key_access(action):
    return allow(action, attr("EncryptionKey"), Condition={
        "StringEquals": {"kms:EncryptionContext:purpose": "pleasanter-mcp-dynamo-probe"},
        "StringLike": {"kms:EncryptionContext:principal": "user#*"},
    })


root = Path(__file__).parent
store_code = (root / "key_store.py").read_text(encoding="utf-8")
code = (root / "handlers.py").read_text(encoding="utf-8") + "\n" + store_code
verifier_code = (root / "verify.py").read_text(encoding="utf-8") + "\n" + store_code
registration_code = (root / "registration.py").read_text(encoding="utf-8") + "\n" + store_code
registration_code += "\nPAGE = " + repr((root / "registration.html").read_text(encoding="utf-8")) + "\n"

registration_endpoint = attr("RegistrationApi", "ApiEndpoint")
registration_callback = sub("${RegistrationApi.ApiEndpoint}/")
login_origin = sub("https://${LoginDomain}.auth.${AWS::Region}.amazoncognito.com")
scopes = {action: {"Fn::Join": ["", [registration_endpoint, f"/keys.{action}"]]}
          for action in ("read", "write", "delete")}
resource("RegistrationApi", "ApiGatewayV2::Api", Name=sub("${AWS::StackName}-registration"), ProtocolType="HTTP")
resource("RegistrationScope", "Cognito::UserPoolResourceServer", UserPoolId=ref("Pool"),
         Identifier=registration_endpoint, Name=sub("${AWS::StackName}-registration"),
         Scopes=[{"ScopeName": f"keys.{action}", "ScopeDescription": f"{action} own API key"}
                 for action in scopes])
resource("RegistrationClient", "Cognito::UserPoolClient", UserPoolId=ref("Pool"),
         GenerateSecret=False, AllowedOAuthFlowsUserPoolClient=True, AllowedOAuthFlows=["code"],
         AllowedOAuthScopes=["openid", *scopes.values()], CallbackURLs=[registration_callback],
         LogoutURLs=[registration_callback], SupportedIdentityProviders=["COGNITO"],
         ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"], PreventUserExistenceErrors="ENABLED",
         EnableTokenRevocation=True, AccessTokenValidity=15, TokenValidityUnits={"AccessToken": "minutes"})
resources["RegistrationClient"]["DependsOn"] = "RegistrationScope"
resource("RegistrationAuth", "ApiGatewayV2::Authorizer", ApiId=ref("RegistrationApi"), Name="Cognito",
         AuthorizerType="JWT", IdentitySource=["$request.header.Authorization"],
         JwtConfiguration={"Audience": [ref("RegistrationClient")], "Issuer": issuer})

for name, handler, environment, permissions in [
    ("Interceptor", "intercept", {"ISSUER": issuer, "CLIENT_ID": ref("Client"),
                                  "ADAPTER_ARN": attr("Adapter"), "SIGNING_KEY": attr("SigningKey")}, [
        allow("kms:Sign", attr("SigningKey")), allow("lambda:InvokeFunction", attr("Adapter"))]),
    ("Adapter", "adapt", {**store_env, "ISSUER": issuer, "SIGNING_KEY": attr("SigningKey"),
                          "MOCK_URL": attr("MockUrl", "FunctionUrl")}, [
        allow("kms:Verify", attr("SigningKey")), table_access("dynamodb:GetItem", "user#*"),
        key_access("kms:Decrypt"),
        allow("lambda:InvokeFunctionUrl", attr("Mock"), Condition={"StringEquals": {"lambda:FunctionUrlAuthType": "AWS_IAM"}}),
        allow("lambda:InvokeFunction", attr("Mock"), Condition={"Bool": {"lambda:InvokedViaFunctionUrl": "true"}}),
    ]),
    ("Mock", "mock", {"KEY_TABLE": ref("KeyTable")}, [table_access("dynamodb:GetItem", "mock#*")]),
    ("Registration", "handler", {**store_env, "ISSUER": issuer, "CLIENT_ID": ref("RegistrationClient"),
                                 "AUDIENCE": ref("RegistrationClient"), "LOGIN_ORIGIN": login_origin,
                                 "IDENTITY_PROVIDER": "COGNITO",
                                 "SCOPES": {"Fn::Join": [" ", ["openid", *scopes.values()]]}}, [
        table_access(["dynamodb:GetItem", "dynamodb:PutItem"], "user#*"), key_access("kms:Encrypt"),
    ]),
    ("Verifier", "handler", {**store_env, "ISSUER": issuer}, [
        allow(["cognito-idp:AdminGetUser", "cognito-idp:AdminSetUserPassword"], attr("Pool")),
        table_access(["dynamodb:GetItem", "dynamodb:PutItem"], "user#*"),
        table_access("dynamodb:PutItem", "mock#*"), key_access("kms:Encrypt"),
    ]),
]:
    log = name + "Log"
    resource(log, "Logs::LogGroup", RetentionInDays=180)
    role(name + "Role", "lambda.amazonaws.com", permissions + [
        allow(["logs:CreateLogStream", "logs:PutLogEvents"],
              sub("arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${" + log + "}:log-stream:*"))
    ])
    function_code = {"Verifier": verifier_code, "Registration": registration_code}.get(name, code)
    resource(name, "Lambda::Function", Handler="index." + handler, Runtime="python3.12",
             Timeout=240 if name == "Verifier" else 25,
             Role=attr(name + "Role"), Code={"ZipFile": function_code}, Environment={"Variables": environment},
             LoggingConfig={"LogGroup": ref(log)})

resource("RegistrationIntegration", "ApiGatewayV2::Integration", ApiId=ref("RegistrationApi"),
         IntegrationType="AWS_PROXY", IntegrationUri=attr("Registration"), PayloadFormatVersion="2.0")
resource("RegistrationPermission", "Lambda::Permission", Action="lambda:InvokeFunction",
         FunctionName=ref("Registration"), Principal="apigateway.amazonaws.com",
         SourceArn=sub("arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${RegistrationApi}/*"))
resource("RegistrationStage", "ApiGatewayV2::Stage", ApiId=ref("RegistrationApi"), StageName="$default",
         AutoDeploy=True, DefaultRouteSettings={"ThrottlingBurstLimit": 10, "ThrottlingRateLimit": 5})
for logical, route, action in [
    ("RegistrationPage", "GET /", None),
    ("KeyStatus", "GET /me/pleasanter-key/status", "read"),
    ("KeyPut", "PUT /me/pleasanter-key", "write"),
    ("KeyDelete", "DELETE /me/pleasanter-key", "delete"),
]:
    auth = {"AuthorizationType": "NONE"} if action is None else {
        "AuthorizationType": "JWT", "AuthorizerId": ref("RegistrationAuth"),
        "AuthorizationScopes": [scopes[action]],
    }
    resource(logical, "ApiGatewayV2::Route", ApiId=ref("RegistrationApi"), RouteKey=route,
             Target=sub("integrations/${RegistrationIntegration}"), **auth)

resource("MockUrl", "Lambda::Url", AuthType="AWS_IAM", TargetFunctionArn=attr("Mock"))
role("GatewayRole", "bedrock-agentcore.amazonaws.com",
     [allow("lambda:InvokeFunction", [attr("Interceptor"), attr("Adapter")])],
     {"StringEquals": {"aws:SourceAccount": ref("AWS::AccountId")},
      "ArnLike": {"aws:SourceArn": sub("arn:${AWS::Partition}:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:gateway/*")}})
resource("Gateway", "BedrockAgentCore::Gateway", Name=ref("AWS::StackName"),
         RoleArn=attr("GatewayRole"), ProtocolType="MCP", AuthorizerType="CUSTOM_JWT",
         AuthorizerConfiguration={"CustomJWTAuthorizer": {
             "DiscoveryUrl": {"Fn::Join": ["", [issuer, "/.well-known/openid-configuration"]]},
             "AllowedClients": [ref("Client")],
             "AllowedScopes": ["aws.cognito.signin.user.admin"],
         }},
         InterceptorConfigurations=[{"InterceptionPoints": ["REQUEST"],
                                     "InputConfiguration": {"PassRequestHeaders": True},
                                     "Interceptor": {"Lambda": {"Arn": attr("Interceptor")}}}])
resource("Target", "BedrockAgentCore::GatewayTarget", Name="mock",
         GatewayIdentifier=attr("Gateway", "GatewayIdentifier"),
         CredentialProviderConfigurations=[{"CredentialProviderType": "GATEWAY_IAM_ROLE"}],
         TargetConfiguration={"Mcp": {"Lambda": {"LambdaArn": attr("Adapter"),
                                                "ToolSchema": {"InlinePayload": [{
             "Name": "whoami", "Description": "Return the mock account selected for the caller",
             "InputSchema": {"Type": "object", "Properties": {
                 "_gatewayAuth": {"Type": "string", "Description": "Reserved by the Gateway"},
             }},
         }]}}}})

outputs = {
    "GatewayUrl": attr("Gateway", "GatewayUrl"), "PoolId": ref("Pool"), "ClientId": ref("Client"),
    "MockUrl": attr("MockUrl", "FunctionUrl"), "RegistrationUrl": registration_callback,
    "KeyTableName": ref("KeyTable"),
}
resource("Verify", "CloudFormation::CustomResource", ServiceToken=attr("Verifier"), ServiceTimeout=260,
         ProbeRevision=hashlib.sha256((code + verifier_code).encode()).hexdigest(),
         **{key: outputs[key] for key in ("GatewayUrl", "PoolId", "ClientId", "MockUrl")})
resources["Verify"]["DependsOn"] = ["Target", "Interceptor", "Adapter", "Mock", "OwnerUser", "CodexUser"]
outputs["Verification"] = attr("Verify", "Result")

if __name__ == "__main__":
    print(json.dumps({"AWSTemplateFormatVersion": "2010-09-09",
                      "Description": "Isolated Cognito and Pleasanter mock MCP with DynamoDB and KMS",
                      "Resources": resources,
                      "Outputs": {key: {"Value": value} for key, value in outputs.items()}}, indent=2))
