"""Build editable UML sequence diagrams for Claude and AgentCore."""
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).parent
FONT = "Yu Gothic"

def cell(root, id, value, x, y, w, h, style):
    c = ET.SubElement(root, "mxCell", id=id, value=value, vertex="1", parent="1",
        style=f"fontFamily={FONT};fontSize=16;html=0;whiteSpace=wrap;{style}")
    ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as":"geometry"})
    return c

def line(root, id, x1,y1,x2,y2, dashed=False, arrow=True):
    c=ET.SubElement(root,"mxCell",id=id,edge="1",parent="1",
        style="html=0;strokeColor=#25384A;endArrow="+("open" if arrow else "none")+";endFill=0;"+("dashed=1;" if dashed else ""))
    g=ET.SubElement(c,"mxGeometry",relative="1",**{"as":"geometry"})
    ET.SubElement(g,"mxPoint",x=str(x1),y=str(y1),**{"as":"sourcePoint"})
    ET.SubElement(g,"mxPoint",x=str(x2),y=str(y2),**{"as":"targetPoint"})

def page(file, name, title, actors, messages, notes, width, height):
    diagram=ET.SubElement(file,"diagram",name=name,id=name)
    model=ET.SubElement(diagram,"mxGraphModel",dx="1400",dy="900",grid="1",gridSize="10",page="1",pageScale="1",
        pageWidth=str(width),pageHeight=str(height), math="0",shadow="0")
    root=ET.SubElement(model,"root"); ET.SubElement(root,"mxCell",id="0"); ET.SubElement(root,"mxCell",id="1",parent="0")
    cell(root,"title",title,30,18,width-60,42,"strokeColor=none;fillColor=none;align=left;fontStyle=1;fontSize=25;")
    bottom=max(m[2] for m in messages)+70
    for i,(x,label) in enumerate(actors):
        cell(root,f"actor{i}",label,x-92,85,184,60,"rounded=0;strokeColor=#4C6981;fillColor=#EDF3F8;fontStyle=1;align=center;")
        line(root,f"life{i}",x,145,x,bottom,True,False)
    for i,(a,b,y,text,response) in enumerate(messages):
        xa,xb=actors[a][0],actors[b][0]
        if a==b:
            cell(root,f"self{i}",text,xa+16,y-22,260,50,"rounded=0;strokeColor=#A5B5C3;fillColor=#F7F9FB;align=left;spacing=8;")
        else:
            line(root,f"msg{i}",xa,y,xb,y,response)
            rows=text.count("\n")+1
            cell(root,f"msglabel{i}",text,min(xa,xb)+10,y-rows*22-5,abs(xa-xb)-20,rows*22,
                "strokeColor=none;fillColor=#FFFFFF;align=center;verticalAlign=bottom;")
    y=bottom+30
    for i,(title,body) in enumerate(notes):
        cell(root,f"note{i}",title+"\n"+body,40,y,width-80,body.count("\n")*25+95,
             "strokeColor=#CCD7E0;fillColor=#F5F7FA;align=left;verticalAlign=top;spacing=14;")
        y+=body.count("\n")*25+115

doc=ET.Element("mxfile",host="app.diagrams.net",version="32.6.10",type="device")
page(doc,"login","Claude から Gateway を利用する認証シーケンス",
[(120,"利用者"),(430,"Claude\nリモートコネクター"),(760,"ブラウザ"),(1140,"Amazon Cognito\n共有ユーザープール"),(1510,"AgentCore Gateway")],
[
(0,1,215,"① MCP 接続を開始",False),
(1,2,330,"② 認可 URL を開く\nclient_id・redirect_uri・scope・state\nresponse_type=code・code_challenge・S256",False),
(2,3,440,"GET /oauth2/authorize\n②のパラメータを送信",False),
(0,2,535,"Cognito のログイン画面で認証情報を入力",False),
(2,3,620,"ログイン情報を Cognito に送信",False),
(3,2,710,"302 redirect_uri?code=...&state=...",True),
(2,1,800,"Claude の callback に code と state を渡す",True),
(1,1,865,"state を照合し、開始時の処理に紐付ける",False),
(1,3,1010,"POST /oauth2/token\ncode・client_id・redirect_uri・code_verifier\ngrant_type=authorization_code",False),
(3,1,1120,"アクセストークン等\nCognito が認証成功後に発行",True),
(1,4,1230,"MCP tools/call\nAuthorization: Bearer <access_token>",False)
],
[
("②で使う情報の取得元",
"管理者が取得・設定するもの\n"
"client_id — CDK 出力 ClientId（MCP 用クライアント。登録画面用と区別）\n"
"authorize/token URL — Cognito のドメインと OIDC メタデータから取得\n"
"redirect_uri — Claude が指定する callback。Cognito の許可リストへ同じ URL を登録\n"
"scope — 現行 Gateway が要求する aws.cognito.signin.user.admin と openid\n"
"Claude が接続ごとに生成するもの\n"
"state — コールバックを開始時の処理に結び付けるランダム値\n"
"code_verifier — ランダム値を生成して保持。code_challenge = BASE64URL(SHA256(verifier))"),
("適用範囲",
"Claude リモートコネクターの OAuth 接続を想定。実環境での Claude 接続は未検証。\n"
"現行スタックの既定 callback はローカル用。PROBE_CALLBACK_URL を Claude 用に設定してデプロイする。\n"
"Claude.ai の callback の例は https://claude.ai/api/mcp/auth_callback。\n"
"このアプリクライアントは GenerateSecret=False。ログイン情報はブラウザから Cognito に入力する。")
], 1660,2150)

page(doc,"runtime","Gateway の本人確認から下流 MCP 呼び出しまで",
[(130,"Claude"),(350,"AgentCore\nGateway"),(590,"インターセプター\nLambda"),(830,"Cognito\n同じプール"),(1070,"アダプター\nLambda"),(1310,"AWS KMS\n署名鍵・暗号化鍵"),(1550,"DynamoDB\n同じテーブル"),(1790,"下流 MCP\n検証ではモック")],
[
(0,1,220,"tools/call\nBearer token",False),
(1,1,300,"JWT 署名・期限・client・scope を検証",False),
(1,2,415,"REQUEST＋Authorization",False),
(2,3,505,"GetUser(access token)",False),
(3,2,595,"ユーザー属性・sub",True),
(2,2,675,"iss・client_id・sub・許可ユーザーを照合",False),
(2,5,805,"Sign（iss・sub・user・method・exp）\n有効期限30秒の内部コンテキスト",False),
(5,2,900,"署名",True),
(2,1,995,"予約引数 _gatewayAuth を上書き",True),
(1,4,1090,"IAM 権限で Lambda Target を実行",False),
(4,5,1185,"Verify（内部署名）",False),
(5,4,1280,"検証結果",True),
(4,4,1360,"iss・期限・method・user を確認",False),
(4,6,1480,"iss＋sub から主キーを算出して GetItem\nConsistentRead=True",False),
(6,4,1580,"暗号文と登録状態",True),
(4,5,1680,"Decrypt（暗号文＋主キーのコンテキスト）",False),
(5,4,1780,"本人用 API キー",True),
(4,7,1900,"IAM 署名＋X-API-Key で HTTPS\ninitialize → initialized → tools/call",False),
(7,4,2000,"MCP 実行結果",True),
(4,1,2090,"MCP 実行結果",True),
(1,0,2180,"MCP 実行結果",True)
],
[
("認証情報の役割と検証範囲",
"Cognito の access token — Claude から Gateway と GetUser に送る。\n"
"署名付き内部コンテキスト — 本人確認後に生成し、アダプターで検証する。\n"
"Pleasanter API キー — DynamoDB の暗号文から復号し、下流 MCP への通信に使用する。\n"
"署名不正・期限切れは拒否。未登録・disabled は復号せずエラー。モックの誤キーは拒否。\n"
"tools/list はインターセプターがアダプターを直接呼ぶ別経路。キー取得・復号・下流呼び出しは行わない。\n"
"このページの Gateway 以降は検証 Lambda からの SDK ログインで実環境試験済み。")
], 1930,2540)
ET.indent(doc)
ET.ElementTree(doc).write(HERE/"gateway-auth-sequence.drawio",encoding="utf-8",xml_declaration=True)
print("written", HERE/"gateway-auth-sequence.drawio")
