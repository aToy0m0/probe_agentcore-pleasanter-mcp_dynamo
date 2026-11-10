"""Generate the AgentCore MCP probe diagram from AWS Architecture Icons (07312026)."""
import sys
from pathlib import Path

from svgdiagram import ACCENT, INK, SUB, Diagram

VERSION = "07312026"
ROOT = Path(__file__).parent


def build(root):
    service = root / f"Architecture-Service-Icons_{VERSION}"
    group = root / f"Architecture-Group-Icons_{VERSION}"
    names = {
        "cognito": ("Security-Identity", "Amazon-Cognito"),
        "kms": ("Security-Identity", "AWS-Key-Management-Service"),
        "iam": ("Security-Identity", "AWS-Identity-and-Access-Management"),
        "ddb": ("Databases", "Amazon-DynamoDB"),
        "gateway": ("Artificial-Intelligence", "Amazon-Bedrock-AgentCore"),
        "api": ("Networking-Content-Delivery", "Amazon-API-Gateway"),
        "lambda": ("Compute", "AWS-Lambda"),
        "cfn": ("Management-Tools", "AWS-CloudFormation"),
        "logs": ("Management-Tools", "Amazon-CloudWatch"),
    }
    icons = {key: service / f"Arch_{category}/64/Arch_{name}_64.svg"
             for key, (category, name) in names.items()}
    icons.update(cloud=group / "AWS-Cloud-logo_32.svg", region=group / "Region_32.svg")
    d = Diagram(1630, 1260)
    d.register_icons(icons)
    d.text("利用者別の Pleasanter API キーを DynamoDB と KMS で管理", 30, 44, 27, INK, "700")
    d.scope(250, 69, 1350, 1160, "cloud", "AWS Cloud")
    d.service("iam", 1120, 89, "AWS IAM", "各サービスの実行ロールと権限")
    d.scope(274, 178, 1302, 1027, "region", "us-east-1", size=16)
    d.group_box(300, 229, 1250, 298, "キーを登録する", "登録・状態確認・登録解除")
    d.group_box(300, 552, 1250, 366, "本人のキーでツールを呼ぶ", "Gateway と Lambda が本人情報を引き継ぐ")
    d.group_box(300, 946, 1250, 230, "デプロイ時の自動検証", "Cognito でログインし、Gateway 経由で 2 ユーザーの分離を確認")

    def node(icon, x, y, label, desc):
        d.service_stacked(icon, x, y, label, [desc])

    def edge(points, label, x, y, *, both=False, accent=False):
        color = ACCENT if accent else "#66788A"
        d.poly(points, color, 3 if accent else 2, both=both)
        d.text(label, x, y, 13, color, "700" if accent else "400", anchor="middle")

    d.card(30, 345, 155, 64, "登録ブラウザ")
    node("cognito", 590, 251, "Amazon Cognito", "登録用 OAuth クライアント")
    node("api", 390, 347, "Amazon API Gateway", "HTTP API／JWT・scope 検証")
    node("lambda", 815, 347, "AWS Lambda", "登録 API")
    node("kms", 1200, 257, "AWS KMS", "対称鍵／本文を暗号化")
    node("ddb", 1410, 384, "Amazon DynamoDB", "利用者別の暗号文・状態・版")
    edge([(105, 345), (105, 283), (590, 283)], "認可コード＋PKCE", 516, 272, both=True)
    edge([(185, 375), (390, 375)], "画面・登録 API", 334, 365, both=True)
    edge([(454, 375), (815, 375)], "JWT 検証済みリクエスト", 630, 399)
    edge([(879, 365), (1010, 365), (1010, 289), (1200, 289)], "Encrypt", 1100, 279, both=True)
    edge([(879, 392), (1095, 392), (1095, 416), (1410, 416)], "状態取得・条件付き書込", 1256, 406, accent=True)

    d.card(30, 642, 155, 64, "MCP クライアント")
    node("gateway", 390, 642, "Amazon Bedrock AgentCore", "Gateway／JWT 認可")
    node("lambda", 825, 642, "AWS Lambda", "アダプター／署名検証")
    node("lambda", 1410, 642, "AWS Lambda", "モック／ハッシュ照合")
    node("lambda", 605, 782, "AWS Lambda", "REQUEST／本人照合後に KMS Sign")
    node("cognito", 810, 782, "Amazon Cognito", "GetUser で本人照合")
    node("kms", 1060, 782, "AWS KMS", "署名鍵と本文の暗号化鍵")
    node("ddb", 1345, 782, "Amazon DynamoDB", "暗号文・モック照合用ハッシュ")
    edge([(185, 666), (390, 666)], "MCP／JWT", 335, 656, both=True)
    edge([(454, 664), (825, 664)], "tools/call／署名済み本人情報", 632, 653)
    edge([(454, 691), (552, 691), (552, 811), (605, 811)], "REQUEST", 590, 763)
    edge([(669, 807), (810, 807)], "GetUser", 740, 797, both=True)
    edge([(889, 664), (1410, 664)], "IAM 署名＋X-API-Key／HTTPS", 1150, 652, both=True)
    edge([(889, 693), (985, 693), (985, 803), (1060, 803)], "Verify・Decrypt", 1028, 770, both=True)
    edge([(889, 681), (1377, 681), (1377, 782)], "本人分を強い整合性で取得", 1173, 703)
    edge([(1474, 691), (1530, 691), (1530, 818), (1409, 818)], "照合値を取得", 1460, 807)

    node("cfn", 450, 1030, "AWS CloudFormation", "カスタムリソース")
    node("lambda", 850, 1030, "AWS Lambda", "検証用のユーザー・キーを準備")
    node("logs", 1310, 1030, "Amazon CloudWatch", "5 Lambda のログ／180 日保持")
    edge([(514, 1062), (850, 1062)], "ServiceToken で呼び出す", 680, 1052)
    edge([(914, 1062), (1310, 1062)], "検証結果を記録", 1115, 1052)
    return d.write(ROOT / "architecture.svg")


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
