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
    d = Diagram(1630, 1430)
    d.register_icons(icons)
    d.text("利用者別の Pleasanter API キーを DynamoDB と KMS で管理", 30, 44, 27, INK, "700")
    d.scope(250, 69, 1350, 1330, "cloud", "AWS Cloud")
    d.service("iam", 1120, 89, "AWS IAM", "各サービスの実行ロールと権限")
    d.scope(274, 178, 1302, 1197, "region", "us-east-1", size=16)
    d.group_box(300, 229, 1250, 298, "キーを登録する", "登録・状態確認・登録解除")
    d.group_box(300, 722, 1250, 366, "本人のキーでツールを呼ぶ", "署名付き本人情報で実行")
    d.group_box(300, 1116, 1250, 230, "デプロイ時の自動検証", "Cognito でログインし、Gateway 経由で 2 ユーザーの分離を確認")

    def node(icon, x, y, label, desc):
        d.service_stacked(icon, x, y, label, [desc])

    def edge(points, label, x, y, *, both=False, accent=False):
        color = ACCENT if accent else "#66788A"
        d.poly(points, color, 3 if accent else 2, both=both)
        d.text(label, x, y, 13, color, "700" if accent else "400", anchor="middle")

    d.card(30, 345, 155, 64, "登録ブラウザ")
    node("cognito", 500, 580, "Amazon Cognito", "共有プール1つ・クライアント2つ")
    node("api", 390, 347, "Amazon API Gateway", "HTTP API／JWT・scope 検証")
    node("lambda", 815, 347, "AWS Lambda", "登録 API")
    node("kms", 1200, 257, "AWS KMS", "対称鍵／本文を暗号化")
    node("ddb", 1150, 580, "Amazon DynamoDB", "共有テーブル1つ／暗号文・状態・版・モック照合値")
    edge([(105, 409), (105, 612), (500, 612)], "認可コード＋PKCE", 399, 601, both=True)
    edge([(185, 375), (390, 375)], "画面・登録 API", 334, 365, both=True)
    edge([(454, 375), (815, 375)], "JWT 検証済みリクエスト", 630, 399)
    edge([(879, 365), (1010, 365), (1010, 289), (1200, 289)], "Encrypt", 1100, 279, both=True)
    edge([(879, 392), (1000, 392), (1000, 596), (1150, 596)], "状態取得・条件付き書込", 1138, 564, accent=True)

    d.card(30, 812, 155, 64, "MCP クライアント")
    node("gateway", 390, 812, "Amazon Bedrock AgentCore", "Gateway／JWT 認可")
    node("lambda", 825, 812, "AWS Lambda", "アダプター／署名検証")
    node("lambda", 1410, 812, "AWS Lambda", "モック／ハッシュ照合")
    node("lambda", 750, 580, "AWS Lambda", "本人照合後に KMS Sign")
    node("kms", 1060, 952, "AWS KMS", "署名鍵と本文の暗号化鍵")
    edge([(185, 836), (390, 836)], "MCP／JWT", 335, 826, both=True)
    edge([(454, 855), (825, 855)], "tools/call／署名済み本人情報", 632, 879)
    edge([(454, 830), (650, 830), (650, 630), (750, 630)], "REQUEST インターセプター", 520, 733)
    edge([(750, 596), (564, 596)], "GetUser", 655, 585, both=True)
    edge([(889, 834), (1410, 834)], "IAM 署名＋X-API-Key／HTTPS", 1150, 822, both=True)
    edge([(889, 863), (985, 863), (985, 973), (1060, 973)], "Verify・Decrypt", 1028, 940, both=True)
    edge([(857, 812), (857, 620), (1150, 620)], "本人分を強い整合性で取得", 1010, 646)
    edge([(1442, 812), (1442, 605), (1214, 605)], "モック照合値を取得", 1342, 592)

    node("cfn", 450, 1200, "AWS CloudFormation", "カスタムリソース")
    node("lambda", 850, 1200, "AWS Lambda", "検証用のユーザー・キーを準備")
    node("logs", 1310, 1200, "Amazon CloudWatch", "5 Lambda のログ／180 日保持")
    edge([(514, 1232), (850, 1232)], "ServiceToken で呼び出す", 680, 1222)
    edge([(914, 1232), (1310, 1232)], "検証結果を記録", 1115, 1222)
    return d.write(ROOT / "architecture.svg")


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
