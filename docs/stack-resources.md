# デプロイされるスタックのリソース

アプリのテンプレートは39件のリソースを定義する。環境によって CDK が CDKMetadata を追加する。共有の CDK bootstrap リソースは別スタックが管理する。

| AWS サービス | CloudFormation 型 | 論理 ID |
| --- | --- | --- |
| Cognito | `AWS::Cognito::UserPool` | `Pool` |
| Cognito | `AWS::Cognito::UserPoolClient` | `Client` |
| Cognito | `AWS::Cognito::UserPoolDomain` | `LoginDomain` |
| Cognito | `AWS::Cognito::UserPoolUser` | `OwnerUser` |
| Cognito | `AWS::Cognito::UserPoolUser` | `CodexUser` |
| Cognito | `AWS::Cognito::UserPoolResourceServer` | `RegistrationScope` |
| Cognito | `AWS::Cognito::UserPoolClient` | `RegistrationClient` |
| API Gateway | `AWS::ApiGatewayV2::Api` | `RegistrationApi` |
| API Gateway | `AWS::ApiGatewayV2::Authorizer` | `RegistrationAuth` |
| API Gateway | `AWS::ApiGatewayV2::Integration` | `RegistrationIntegration` |
| API Gateway | `AWS::ApiGatewayV2::Stage` | `RegistrationStage` |
| API Gateway | `AWS::ApiGatewayV2::Route` | `RegistrationPage` |
| API Gateway | `AWS::ApiGatewayV2::Route` | `KeyStatus` |
| API Gateway | `AWS::ApiGatewayV2::Route` | `KeyPut` |
| API Gateway | `AWS::ApiGatewayV2::Route` | `KeyDelete` |
| AgentCore | `AWS::BedrockAgentCore::Gateway` | `Gateway` |
| AgentCore | `AWS::BedrockAgentCore::GatewayTarget` | `Target` |
| Lambda | `AWS::Lambda::Function` | `Interceptor` |
| Lambda | `AWS::Lambda::Function` | `Adapter` |
| Lambda | `AWS::Lambda::Function` | `Mock` |
| Lambda | `AWS::Lambda::Function` | `Registration` |
| Lambda | `AWS::Lambda::Function` | `Verifier` |
| Lambda | `AWS::Lambda::Url` | `MockUrl` |
| Lambda | `AWS::Lambda::Permission` | `RegistrationPermission` |
| DynamoDB | `AWS::DynamoDB::Table` | `KeyTable` |
| KMS | `AWS::KMS::Key` | `SigningKey` |
| KMS | `AWS::KMS::Key` | `EncryptionKey` |
| IAM | `AWS::IAM::Role` | `InterceptorRole` |
| IAM | `AWS::IAM::Role` | `AdapterRole` |
| IAM | `AWS::IAM::Role` | `MockRole` |
| IAM | `AWS::IAM::Role` | `RegistrationRole` |
| IAM | `AWS::IAM::Role` | `VerifierRole` |
| IAM | `AWS::IAM::Role` | `GatewayRole` |
| CloudWatch Logs | `AWS::Logs::LogGroup` | `InterceptorLog` |
| CloudWatch Logs | `AWS::Logs::LogGroup` | `AdapterLog` |
| CloudWatch Logs | `AWS::Logs::LogGroup` | `MockLog` |
| CloudWatch Logs | `AWS::Logs::LogGroup` | `RegistrationLog` |
| CloudWatch Logs | `AWS::Logs::LogGroup` | `VerifierLog` |
| CloudFormation | `AWS::CloudFormation::CustomResource` | `Verify` |

構成図では IAM ロール、ロググループ、KMS 鍵、各サービスの設定リソースをまとめて表示している。

[AWS 構成図と設計](architecture.md)
