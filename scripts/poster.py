#!/usr/bin/env python3
"""开饭海报生成（独立脚本，供 Skill 调用）。

输入：POSTER_JSON 环境变量 或 stdin 传一段 JSON，字段：
{
  "group_name": "本群开饭战报",
  "items":  [ {"speaker","name","spec","qty"}, ... ],
  "best":   { "code","label","payable","original","savings","points" },
  "share":  [ {"speaker","amount"}, ... ],
  "king":   "花得最多的人名（可选，缺省取 share[0]）"
}
输出：POSTER_OUT 指定路径，缺省写 ./poster.png。

字体：自动探测；可用 MCD_FONT_REGULAR / MCD_FONT_BOLD 覆盖。
依赖：pip install Pillow
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# 麦当劳红黄配色
RED = (218, 41, 28)
YELLOW = (255, 199, 44)
DARK = (34, 34, 34)
GREY = (120, 120, 120)
BG = (255, 248, 231)
WHITE = (255, 255, 255)

_FONT_CANDIDATES = {
    False: [
        os.getenv("MCD_FONT_REGULAR", ""),
        "/usr/local/share/fonts/custom/NotoSansSC-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "assets/fonts/NotoSansSC-Regular.ttf",
    ],
    True: [
        os.getenv("MCD_FONT_BOLD", ""),
        "/usr/local/share/fonts/custom/NotoSansSC-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "assets/fonts/NotoSansSC-Bold.ttf",
    ],
}


def _font(size: int, bold: bool = False):
    for p in _FONT_CANDIDATES[bold]:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_w(draw, text, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def load_data() -> dict:
    raw = os.getenv("POSTER_JSON", "")
    if not raw:
        raw = sys.stdin.read()
    raw = (raw or "").strip()
    if not raw:
        return {}
    return json.loads(raw)


def render(d: dict, out_path: str | None = None):
    W, H = 1080, 1480
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    f_title = _font(64, True)
    f_h2 = _font(40, True)
    f_body = _font(34)
    f_small = _font(26)
    f_big = _font(96, True)

    pad = 64
    items = d.get("items", [])
    best = d.get("best") or {}
    share = d.get("share", [])
    king = d.get("king") or (share[0]["speaker"] if share else "")

    # 顶部红色标题条
    dr.rounded_rectangle([pad, 56, W - pad, 208], radius=32, fill=RED)
    dr.text((pad + 44, 86), "麦麦开饭海报", font=f_title, fill=WHITE)
    dr.text((pad + 46, 160), d.get("group_name", "本群开饭战报"), font=f_small, fill=(255, 220, 200))

    y = 264
    # 一、订单一览
    dr.text((pad, y), "本单已点", font=f_h2, fill=DARK)
    y += 64
    for it in items:
        line = f"{it.get('speaker') or '匿名'}  {it.get('name','')}"
        if it.get("spec"):
            line += f"（{it['spec']}）"
        if int(it.get("qty", 1)) > 1:
            line += f" ×{it['qty']}"
        dr.text((pad + 16, y), line, font=f_body, fill=DARK)
        y += 52
    y += 16

    # 二、最优方案
    if best:
        box_h = 260
        dr.rounded_rectangle([pad, y, W - pad, y + box_h], radius=28, fill=YELLOW)
        dr.text((pad + 40, y + 30), f"最优方案 {best.get('code','')}｜{best.get('label','')}",
                font=f_h2, fill=DARK)
        dr.text((pad + 40, y + 96), f"实付  ¥{float(best.get('payable',0)):.2f}", font=f_big, fill=RED)
        save_txt = f"相比原价省  ¥{float(best.get('savings',0)):.2f}"
        if best.get("points"):
            save_txt += f"   ·   积分 {best['points']}"
        dr.text((pad + 44, y + 208), save_txt, font=f_body, fill=DARK)
        y += box_h + 40

    # 三、分账
    dr.text((pad, y), "AA 分账", font=f_h2, fill=DARK)
    y += 62
    for s in share:
        dr.text((pad + 16, y), s.get("speaker", "?"), font=f_body, fill=DARK)
        amt = f"¥{float(s.get('amount',0)):.2f}"
        dr.text((W - pad - 16 - _text_w(dr, amt, f_body), y), amt, font=f_body, fill=RED)
        y += 52
    dr.text((pad + 16, y), "按各人餐品金额占比分摊优惠", font=f_small, fill=GREY)
    y += 64

    # 四、趣味战报
    if king:
        dr.rounded_rectangle([pad, y, W - pad, y + 96], radius=20, fill=(255, 236, 200))
        dr.text((pad + 32, y + 28), f"本群麦当劳之王：{king}", font=f_h2, fill=RED)
        y += 120

    # 底栏
    dr.line([pad, H - 120, W - pad, H - 120], fill=(230, 220, 200), width=2)
    dr.text((pad, H - 96), "由「麦麦开饭官」自动生成 · 基于麦当劳 MCP", font=f_small, fill=GREY)
    dr.text((pad, H - 60), "#麦门开饭  #麦当劳程序员创意开发大赛", font=f_small, fill=GREY)

    out_path = out_path or os.getenv("POSTER_OUT") or "poster.png"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path)
    return out_path


if __name__ == "__main__":
    path = render(load_data())
    print(path)
