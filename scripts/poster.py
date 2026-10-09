#!/usr/bin/env python3
"""开饭海报生成 v7.1 · 全中文紧凑竖版（朋友圈 / 小红书分享友好）。

设计目标：突出"方便、快捷、新颖、好玩"的体验，而非价格优势；
版面全中文化 + 9:16 竖屏，适合手机直接分享。

结构（从上到下，全中文栏标）：
  1. 顶部   品牌行「麦当劳 · 开饭战报」
  2. 主标题 「点单，只需一句话」（"一句话"品牌红强调）
  3. 你说   用户原话折行 + 「↑ 就这一句」
  4. 揭晓   巨型「3 秒」+「后，这餐已下单」
  5. 代劳   ✓它替你做了 N 件事（两列紧凑）
  6. 听懂   本单明细（人/餐品/定制/数量，不显单价）
  7. 之王   本群麦门之王（大字 + 金皇冠）
  8. 分账   环形饼图 + 图例（金额/占比，王之扇区品牌红）
  9. 收尾   金拱门 + 钩子「动动嘴，3 秒下单，下次你来一句试试？」

【字体】三级兜底，永不崩：
  1) 汉仪雅酷黑（用户自装，视觉最佳）  ~/Library/Fonts/HYYakuHei-{45,65,85,95}W.ttf
  2) 冬青黑体 Hiragino Sans GB（macOS 自带） W3 / W6
  3) 华文黑体 STHeiti（macOS 自带）
  4) Noto Sans CJK（Linux 常见）
  5) PIL 默认字体（最后兜底，中文可能缺字）
可用环境变量覆盖：MCD_FONT_LIGHT / MCD_FONT_REGULAR / MCD_FONT_BOLD / MCD_FONT_NUM

【输入数据】POSTER_JSON 环境变量或 stdin（JSON）：
  必填：items[{speaker,name,spec,qty}], best{code,label,payable,original,savings,points}, share[{speaker,amount}]
  可选：group_name, king, user_quote, ai_did[list[str]]

【输出】POSTER_OUT 指定路径，缺省 ./poster.png。
【依赖】pip install Pillow
"""
from __future__ import annotations

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ─── 麦当劳 APP 配色 ────────────────────────────────
INK = (39, 36, 31)            # 主文字·炭黑 #27241F
INK_SOFT = (140, 140, 140)    # 次级文字·中性灰
INK_FAINT = (190, 190, 190)   # 极淡灰
BRAND_RED = (218, 41, 28)     # 麦当劳红 #DA291C
GOLD = (255, 199, 44)         # 金拱门黄 #FFC72C
HAIRLINE = (235, 235, 235)    # 1px 细线
BG = (255, 255, 255)          # 纯白底

# ─── 字体候选链（每档按优先级，第一个能加载的生效）───
_FONT_CANDIDATES = {
    "l": [  # 细体
        os.getenv("MCD_FONT_LIGHT", ""),
        os.path.expanduser("~/Library/Fonts/HYYakuHei-45W.ttf"),
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Light.ttc",
    ],
    "r": [  # 常规
        os.getenv("MCD_FONT_REGULAR", ""),
        os.path.expanduser("~/Library/Fonts/HYYakuHei-65W.ttf"),
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ],
    "b": [  # 粗体
        os.getenv("MCD_FONT_BOLD", ""),
        os.path.expanduser("~/Library/Fonts/HYYakuHei-85W.ttf"),
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ],
}
# ttc 里的字重下标（Hiragino Sans GB: 0=W3, 2=W6）
_TTC_INDEX = {
    "/System/Library/Fonts/Hiragino Sans GB.ttc": {"l": 0, "r": 0, "b": 2},
}
_FONT_NUM_CANDIDATES = [
    os.getenv("MCD_FONT_NUM", ""),
    os.path.expanduser("~/Library/Fonts/HYYakuHei-95W.ttf"),
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]


def _load_font(candidates: list, size: int, weight: str = "r") -> ImageFont.FreeTypeFont:
    for p in candidates:
        if not p or not os.path.exists(p):
            continue
        idx = _TTC_INDEX.get(p, {}).get(weight, 0)
        try:
            return ImageFont.truetype(p, size, index=idx)
        except (OSError, ValueError):
            continue
    # 极端兜底：PIL 内置（中文可能缺字，但不崩）
    return ImageFont.load_default()


def F(size: int, weight: str = "r"):
    return _load_font(_FONT_CANDIDATES[weight], size, weight)


def FN(size: int, bold: bool = False):
    return _load_font(_FONT_NUM_CANDIDATES, size, "b" if bold else "r")


def tw(d, text, font):
    b = d.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def tb(d, text, font):
    return d.textbbox((0, 0), text, font=font)


def load_data() -> dict:
    raw = os.getenv("POSTER_JSON", "") or sys.stdin.read()
    return json.loads(raw.strip()) if raw.strip() else {}


def draw_golden_arches(dr, cx, cy, scale=1.0, fill=GOLD, line_w=8):
    """金拱门 M：两个修长椭圆拱相交。cx,cy 为底边中点。"""
    h = int(84 * scale)
    w = int(52 * scale)
    off = int(0.55 * h)
    for sgn in (-1, 1):
        ox = cx + sgn * off
        bbox = [ox - w, cy - h, ox + w, cy + h]
        dr.arc(bbox, start=180, end=360, fill=fill, width=line_w)


def draw_check(dr, x, y, size, color, line_w=4):
    """画对勾 ✓。x,y 为左上角,size 为整体尺寸。"""
    p1 = (x, y + size * 0.55)
    p2 = (x + size * 0.30, y + size * 0.85)
    p3 = (x + size, y + size * 0.15)
    dr.line([p1, p2], fill=color, width=line_w, joint="curve")
    dr.line([p2, p3], fill=color, width=line_w, joint="curve")


def section_label(dr, text, y):
    """中文栏标：品牌红小字 + 右侧发丝线。返回画完后的 y。"""
    f = F(22, "b")
    dr.text((84, y), text, font=f, fill=BRAND_RED)
    lw_ = tw(dr, text, f)
    dr.line([84 + lw_ + 24, y + 11, W - 84, y + 11], fill=HAIRLINE, width=1)
    return y + 62


def wrap_text(d, text, font, max_w):
    out = []
    line = ""
    for c in text:
        if tw(d, line + c, font) <= max_w:
            line += c
        else:
            out.append(line)
            line = c
    if line:
        out.append(line)
    return out


# 缺省"它替你做了"——通用流程动作，不含与具体场景可能不符的断言。
# Agent 应优先传入 ai_did 反映本次真实动作。
DEFAULT_AI_DID = [
    "听懂了每人的口味定制",
    "拉取了门店可售菜单",
    "实时算出精确总价",
    "比了券与积分的最优组合",
    "给每人分好 AA 账单",
    "出好这张可转发海报",
]

PAD = 84
SECTION_GAP = 52
W = 1080


def render(d: dict, out_path: str | None = None):
    items = d.get("items", [])
    best = d.get("best") or {}
    share = d.get("share", [])
    king = d.get("king") or (share[0]["speaker"] if share else "")
    group = d.get("group_name", "")

    user_quote = d.get("user_quote", "")
    ai_did = d.get("ai_did") or DEFAULT_AI_DID

    # 原话折行
    tmp = Image.new("RGB", (10, 10))
    td = ImageDraw.Draw(tmp)
    f_quote = F(34, "l")
    quote_lines = wrap_text(td, user_quote, f_quote, W - PAD * 2) if user_quote else []

    img = Image.new("RGB", (W, 3200), BG)
    dr = ImageDraw.Draw(img)
    y = 66

    # ═══ 1. 顶部品牌行 ═══
    dr.ellipse([PAD, y + 6, PAD + 13, y + 19], fill=BRAND_RED)
    dr.text((PAD + 26, y - 2), "麦当劳 · 开饭战报", font=F(22), fill=INK_SOFT)
    if group:
        dr.text((W - PAD - tw(dr, group, F(22)), y - 2), group, font=F(22), fill=INK_SOFT)
    y += 60

    # ═══ 2. 主标题：点单，只需一句话 ═══
    f_hero = F(88, "b")
    pre, emph = "点单，只需", "一句话"
    pw, ew = tw(dr, pre, f_hero), tw(dr, emph, f_hero)
    x0 = (W - (pw + ew)) // 2
    dr.text((x0, y), pre, font=f_hero, fill=INK)
    dr.text((x0 + pw, y), emph, font=f_hero, fill=BRAND_RED)
    y += 120
    f_sub = F(26, "l")
    sub = "—— 一句话，就是点单的全部"
    dr.text(((W - tw(dr, sub, f_sub)) // 2, y + 4), sub, font=f_sub, fill=INK_SOFT)
    y += 56
    dr.line([(W - 90) // 2, y, (W + 90) // 2, y], fill=BRAND_RED, width=2)
    y += SECTION_GAP

    # ═══ 3. 你说：用户原话 ═══
    if quote_lines:
        y = section_label(dr, "你说", y)
        for ln in quote_lines:
            dr.text((PAD, y), ln, font=f_quote, fill=INK)
            y += 50
        y += 4
        dr.text((PAD, y), "↑ 就这一句", font=F(24, "b"), fill=BRAND_RED)
        y += 66 + SECTION_GAP

    # ═══ 4. 揭晓：3 秒 ═══
    y = section_label(dr, "揭晓", y)
    f_num = FN(176, bold=True)
    f_cn = F(80, "b")
    b3, bs = tb(dr, "3", f_num), tb(dr, "秒", f_cn)
    h3, hs = b3[3] - b3[1], bs[3] - bs[1]
    n_w, c_w = b3[2] - b3[0], bs[2] - bs[0]
    gap = 20
    sx = (W - (n_w + gap + c_w)) // 2
    base = y + 36
    dr.text((sx - b3[0], base), "3", font=f_num, fill=BRAND_RED)
    dr.text((sx + n_w + gap - bs[0], base + h3 - hs), "秒", font=f_cn, fill=BRAND_RED)
    y = base + max(h3, hs) + 48
    f_s2 = F(30, "l")
    s2 = "后，这餐已下单"
    dr.text(((W - tw(dr, s2, f_s2)) // 2, y), s2, font=f_s2, fill=INK)
    y += 50 + SECTION_GAP

    # ═══ 5. 代劳：它替你做了 N 件事（两列） ═══
    y = section_label(dr, "它替你做了", y)
    col_w = (W - PAD * 2) // 2
    col_h = 54
    for i, item in enumerate(ai_did):
        col = i % 2
        row = i // 2
        cx0 = PAD + col * col_w
        cy0 = y + row * col_h
        draw_check(dr, cx0, cy0 + 8, 30, BRAND_RED, line_w=4)
        lines = wrap_text(dr, item, F(25), col_w - 62)
        for j, ln in enumerate(lines[:2]):
            dr.text((cx0 + 46, cy0 + j * 30), ln, font=F(25), fill=INK)
    rows_needed = math.ceil(len(ai_did) / 2)
    y += rows_needed * col_h + 16 + SECTION_GAP

    # ═══ 6. 听懂：本单明细 ═══
    y = section_label(dr, "它听懂了", y)
    for it in items:
        sp, name, spec, qty = (it.get("speaker", ""), it.get("name", ""),
                               it.get("spec", ""), int(it.get("qty", 1)))
        dr.text((PAD, y + 6), sp, font=F(22), fill=INK_SOFT)
        nx = PAD + 110
        dr.text((nx, y), name, font=F(28, "b"), fill=INK)
        if spec:
            dr.text((nx + tw(dr, name, F(28, "b")) + 20, y + 6), spec, font=F(20), fill=INK_SOFT)
        if qty > 1:
            qt = f"×{qty}"
            dr.text((W - PAD - tw(dr, qt, FN(24)) - 4, y + 4), qt, font=FN(24), fill=BRAND_RED)
        y += 58
        dr.line([PAD, y - 8, W - PAD, y - 8], fill=HAIRLINE, width=1)
    y += 8 + SECTION_GAP

    # ═══ 7. 之王 ═══
    if king:
        y = section_label(dr, "麦门之王", y)
        dr.text((PAD, y), king, font=F(78, "l"), fill=INK)
        y += 96
        cx, cy = PAD + 4, y + 10
        cw, ch = 48, 34
        pts = [(cx, cy + ch), (cx, cy + 12), (cx + cw * 0.22, cy + ch * 0.5),
               (cx + cw * 0.5, cy - 6), (cx + cw * 0.78, cy + ch * 0.5),
               (cx + cw, cy + 12), (cx + cw, cy + ch)]
        dr.polygon(pts, fill=GOLD)
        dr.rectangle([cx - 3, cy + ch, cx + cw + 3, cy + ch + 4], fill=GOLD)
        dr.text((PAD + 72, y + 2), "这位吃最多，也担最多", font=F(24), fill=INK_SOFT)
        y += 62 + SECTION_GAP

    # ═══ 8. 分账：环形饼图 + 图例 ═══
    if share:
        y = section_label(dr, "它分好了", y)
        total = sum(float(s.get("amount", 0)) for s in share) or 1
        R = 96
        ring_w = 38
        cx = PAD + 40 + R
        cy = y + R + 16
        amts = [float(s.get("amount", 0)) for s in share]
        colors = [INK, INK_SOFT, INK_FAINT, GOLD]
        mx = amts.index(max(amts)) if amts else -1
        if mx >= 0:
            colors[mx] = BRAND_RED
        ir = R - ring_w - 6
        start = -90.0
        for i, s in enumerate(share):
            frac = amts[i] / total
            end = start + 360 * frac
            bbox = [cx - R, cy - R, cx + R, cy + R]
            dr.pieslice(bbox, start, end, fill=colors[i])
            a = math.radians(start)
            x0 = cx + int(math.cos(a) * ir); y0 = cy + int(math.sin(a) * ir)
            x1 = cx + int(math.cos(a) * R); y1 = cy + int(math.sin(a) * R)
            dr.line([x0, y0, x1, y1], fill=BG, width=3)
            start = end
        dr.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], fill=BG)
        c_total = f"¥{total:,.0f}"
        f_ct = FN(38, bold=True)
        dr.text((cx - tw(dr, c_total, f_ct) // 2, cy - 40), c_total, font=f_ct, fill=INK)
        clbl = "合计"
        f_cl = F(20)
        dr.text((cx - tw(dr, clbl, f_cl) // 2, cy + 12), clbl, font=f_cl, fill=INK_SOFT)

        lx = cx + R + 56
        ly = y + 30
        for i, s in enumerate(share):
            amt = amts[i]
            pct = f"{amt / total * 100:.0f}%"
            dr.ellipse([lx, ly + 6, lx + 16, ly + 22], fill=colors[i])
            dr.text((lx + 30, ly), s.get("speaker", ""), font=F(26, "b"), fill=INK)
            dr.text((lx + 30, ly + 36), f"¥{amt:,.2f} · {pct}", font=F(22), fill=INK_SOFT)
            ly += 96
        y += R * 2 + 40 + SECTION_GAP

    # ═══ 9. 收尾：金拱门 + 钩子 ═══
    fy = y + 8
    draw_golden_arches(dr, W // 2, fy + 78, scale=1.0, fill=GOLD, line_w=5)
    f_hook = F(28, "b")
    hook = "动动嘴，3 秒下单，下次你来一句试试？"
    dr.text(((W - tw(dr, hook, f_hook)) // 2, fy + 122), hook, font=f_hook, fill=INK)
    f_tag = F(20, "l")
    tag = "#麦门开饭 · #动嘴下单"
    dr.text(((W - tw(dr, tag, f_tag)) // 2, fy + 168), tag, font=f_tag, fill=INK_SOFT)
    f_gen = F(17, "l")
    gen = "麦麦开饭官 · 实时算价"
    dr.text(((W - tw(dr, gen, f_gen)) // 2, fy + 202), gen, font=f_gen, fill=INK_FAINT)

    out_path = out_path or os.getenv("POSTER_OUT") or "poster.png"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.crop((0, 0, W, min(3200, fy + 240))).save(out_path)
    return out_path


if __name__ == "__main__":
    print(render(load_data()))
