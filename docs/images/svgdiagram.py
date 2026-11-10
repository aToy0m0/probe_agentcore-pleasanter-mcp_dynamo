"""AWS構成図SVGを組み立てるための最小プリミティブ。

使い方は assets/example_build.py を参照する。
アイコンは AWS 公式 Architecture Icons の SVG を base64 data URI として埋め込む。
"""
from __future__ import annotations

import base64
from pathlib import Path

# ---------------------------------------------------------------- 既定のトークン

INK = "#16191F"          # 見出しとサービス名
SUB = "#5F6B7A"          # 補足テキスト
LINE = "#8C97A2"         # 通常の接続線
ACCENT = "#ED7100"       # 主題の1本だけに使うAWSオレンジ
GROUP_BG = "#F4F6F8"     # 意味のまとまりの背景
CLOUD = "#232F3E"        # AWS Cloud枠
CARD_BORDER = "#D8DEE5"  # 白カードの枠
WHITE = "#FFFFFF"

FONT = (
    "'Yu Gothic UI','Yu Gothic','Meiryo','Noto Sans JP',"
    "'Hiragino Sans','Segoe UI',sans-serif"
)

ICON_SIZE = 64  # 図内のサービスアイコンは同一サイズに揃える


def data_uri(path: Path) -> str:
    """SVGファイルをbase64のdata URIへ変換する。外部参照を作らないために必ず使う。"""
    return "data:image/svg+xml;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text_width(s: str, size: float, bold: bool = False) -> float:
    """描画幅の概算。ASCIIは約0.58em、日本語などの全角は約1.0emとして見積もる。

    厳密ではないので、隣接要素との間隔を決める用途にだけ使い、
    最終判断は必ず固定PNGの原寸確認で行う。
    """
    em = size * (1.06 if bold else 1.0)
    return sum(em * (0.58 if ord(c) < 0x2E80 else 1.0) for c in s)


class Diagram:
    """SVG要素を順に積み上げる。zオーダーは追加順。"""

    def __init__(self, width: float, height: float, font: str = FONT) -> None:
        self.width = width
        self.height = height
        self.font = font
        self.icons: dict[str, str] = {}
        self._body: list[str] = []

    # ---------------------------------------------------------- アイコン登録

    def register_icons(self, mapping: dict[str, Path]) -> None:
        """名前 -> 公式アイコンSVGのパス。登録した名前を icon() で参照する。"""
        for name, path in mapping.items():
            p = Path(path)
            if not p.is_file():
                raise FileNotFoundError(f"AWS公式アイコンが見つからない: {name} -> {p}")
            self.icons[name] = data_uri(p)

    # ---------------------------------------------------------- 基本図形

    def rrect(self, x: float, y: float, w: float, h: float, r: float, fill: str,
              stroke: str = "none", sw: float = 1.0) -> None:
        self._body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def text(self, s: str, x: float, y: float, size: float, color: str = INK,
             weight: str = "400", anchor: str = "start") -> None:
        self._body.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>'
        )

    def line(self, x1: float, y1: float, x2: float, y2: float,
             color: str = LINE, width: float = 1.6) -> None:
        """矢印のない区切り線。接続線には使わない。"""
        self._body.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none"/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str = "none",
               stroke: str = "none", sw: float = 1.0) -> None:
        self._body.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def arc_shoulders(self, cx: float, cy: float, r: float,
                      stroke: str = LINE, sw: float = 2.4) -> None:
        """人物ピクトグラムの肩。ブラウザカードなどAWS外の要素に使う。"""
        self._body.append(
            f'<path d="M{cx - r} {cy} a{r} {r} 0 0 1 {r * 2} 0" fill="none" '
            f'stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def icon(self, name: str, x: float, y: float, size: float = ICON_SIZE) -> None:
        if name not in self.icons:
            raise KeyError(f"未登録のアイコン: {name}。register_icons()で公式SVGを登録する")
        self._body.append(
            f'<image href="{self.icons[name]}" x="{x}" y="{y}" width="{size}" height="{size}"/>'
        )

    def poly(self, points: list[tuple[float, float]], color: str = LINE,
             width: float = 2.0, arrow: bool = True, both: bool = False) -> None:
        """直交ポリライン。終点に矢印を付ける。24px未満の区間を作らない。

        both=Trueで始点にも矢印を付ける。要求と応答を1本で表す往復経路に使い、
        方向が一意な取得・作成には使わない。
        """
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if 0 < abs(x2 - x1) + abs(y2 - y1) < 24:
                raise ValueError(f"24px未満の区間: ({x1},{y1})->({x2},{y2})")
        pts = " ".join(f"{x},{y}" for x, y in points)
        # markerはorient="auto-start-reverse"なので、同じ定義をmarker-startへ使うと逆向きになる
        name = "arrow-accent" if color == ACCENT else "arrow"
        markers = ""
        if arrow:
            markers = f' marker-end="url(#{name})"'
            if both:
                markers += f' marker-start="url(#{name})"'
        self._body.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round" stroke-linecap="round"{markers}/>'
        )

    # ---------------------------------------------------------- 合成要素

    def scope(self, x: float, y: float, w: float, h: float, marker: str, title: str,
              size: float = 20, stroke: str = CLOUD) -> None:
        """AWS Cloud、Regionなどの地理・スコープ境界。

        公式グループマーカーを境界の左上頂点へ隙間なく置き、タイトルはその右へ分離する。
        角は丸めない。角丸にすると左上マーカーの直角と枠の曲線がずれ、隙間があるように
        見えるため、マーカーを持つ枠は必ず直角の矩形にする。
        背景は透明にし、意味のまとまりを示す薄いグレーのグループと視覚的に区別する。
        ラベルだけの独自枠を作らない。囲むスコープに対応する公式マーカーが無い場合は、
        枠を描かずに配置と見出しテキストで表す。
        """
        self.rrect(x, y, w, h, 0, "none", stroke, 1.6)
        self.icon(marker, x, y, 32)
        self.text(title, x + 44, y + 23, size, INK, "700")

    def group_box(self, x: float, y: float, w: float, h: float, title: str, sub: str = "",
                  fill: str = GROUP_BG, stroke: str = "none", title_color: str = INK,
                  header_icon: str | None = None, header_icon_size: float = 40) -> None:
        """意味のまとまり。見出しはサービス名ではなく仕事で切る。

        header_iconを渡すと見出しの左に公式アイコンを置き、テキストをその分だけ右へ寄せる。
        主題となる実行環境を強調する場合に使う（強調は図に1つまで）。
        """
        self.rrect(x, y, w, h, 16, fill, stroke, 1.8)
        tx = x + 32
        if header_icon:
            self.icon(header_icon, tx, y + 22, header_icon_size)
            tx += header_icon_size + 12
        self.text(title, tx, y + 46, 19, title_color, "700")
        if sub:
            self.text(sub, tx, y + 70, 12.5, SUB)

    def service(self, icon_name: str, ix: float, iy: float, name: str, desc: str,
                size: float = ICON_SIZE, gap: float = 20) -> None:
        """アイコンの右にサービス名と補足を並べる。サービス名は公式表示名をそのまま使う。"""
        self.icon(icon_name, ix, iy, size)
        tx = ix + size + gap
        self.text(name, tx, iy + size * 0.44, 17, INK, "700")
        self.text(desc, tx, iy + size * 0.82, 12.5, SUB)

    def service_stacked(self, icon_name: str, ix: float, iy: float, name: str,
                        descs: list[str], size: float = ICON_SIZE) -> None:
        """アイコンの下にサービス名と補足を中央揃えで積む。"""
        self.icon(icon_name, ix, iy, size)
        cx = ix + size / 2
        self.text(name, cx, iy + size + 26, 17, INK, "700", anchor="middle")
        for i, d in enumerate(descs):
            self.text(d, cx, iy + size + 48 + i * 20, 12.5, SUB, anchor="middle")

    def card(self, x: float, y: float, w: float, h: float, title: str, sub: str = "") -> None:
        """AWS外の製品やSDKなど、公式アイコンが無いものは文字だけのカードで表す。"""
        self.rrect(x, y, w, h, 10, WHITE, CARD_BORDER, 1.4)
        cx, cy = x + w / 2, y + h / 2
        self.text(title, cx, cy + (0 if not sub else -6), 16, INK, "700", anchor="middle")
        if sub:
            self.text(sub, cx, cy + 18, 12.5, SUB, anchor="middle")

    # ---------------------------------------------------------- 出力

    def render(self) -> str:
        defs = (
            "<defs>"
            f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker>'
            f'<marker id="arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{ACCENT}"/></marker>'
            "</defs>"
        )
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" font-family="{self.font}">'
        )
        bg = f'<rect width="{self.width}" height="{self.height}" fill="{WHITE}"/>'
        return "\n".join([head, defs, bg, *self._body, "</svg>"])

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        return path
