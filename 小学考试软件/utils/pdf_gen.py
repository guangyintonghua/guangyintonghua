"""
PDF 生成器（商业级）
- generate_exam_pdf   → 试卷 + 答题区
- generate_report_pdf → 分析报告（含图表）
"""
import io
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image as RLImage,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 字体注册 ──────────────────────────────────
_FONT_REGISTERED = False
_FONT_NAME = "YaHei"
_FONT_BOLD_NAME = "YaHei"

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\msyh.ttc",    "MicrosoftYaHei",     False),
    (r"C:\Windows\Fonts\msyhbd.ttc",  "MicrosoftYaHei-Bold", True),
    (r"C:\Windows\Fonts\simhei.ttf",  "SimHei",             False),
    (r"C:\Windows\Fonts\simsun.ttc",  "SimSun",             False),
]


def _ensure_font():
    global _FONT_REGISTERED, _FONT_NAME, _FONT_BOLD_NAME
    if _FONT_REGISTERED:
        return
    for path, name, is_bold in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                if not is_bold:
                    _FONT_NAME = name
                else:
                    _FONT_BOLD_NAME = name
                _FONT_REGISTERED = True
            except Exception:
                pass
    if not _FONT_REGISTERED:
        _FONT_NAME = "Helvetica"
        _FONT_BOLD_NAME = "Helvetica-Bold"
        _FONT_REGISTERED = True


# ── 颜色定义 ──────────────────────────────────
C_PRIMARY   = colors.HexColor("#4B7BEC")
C_SUCCESS   = colors.HexColor("#52B788")
C_WARNING   = colors.HexColor("#F4A261")
C_DANGER    = colors.HexColor("#E07A7A")
C_TEXT      = colors.HexColor("#2D3436")
C_SUBTEXT   = colors.HexColor("#636E72")
C_BORDER    = colors.HexColor("#DFE6E9")
C_BG_LIGHT  = colors.HexColor("#F8FAFB")
C_BG_BLUE   = colors.HexColor("#EBF0FF")


def _styles() -> dict:
    _ensure_font()
    f, fb = _FONT_NAME, _FONT_BOLD_NAME
    return {
        "title": ParagraphStyle("title", fontName=fb, fontSize=20,
                                textColor=C_TEXT, alignment=TA_CENTER, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", fontName=f, fontSize=11,
                                   textColor=C_SUBTEXT, alignment=TA_CENTER, spaceAfter=16),
        "section": ParagraphStyle("section", fontName=fb, fontSize=13,
                                  textColor=C_PRIMARY, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=f, fontSize=11,
                               textColor=C_TEXT, leading=18, spaceAfter=4),
        "small": ParagraphStyle("small", fontName=f, fontSize=9,
                                textColor=C_SUBTEXT, leading=14),
        "q_num": ParagraphStyle("q_num", fontName=fb, fontSize=11,
                                textColor=C_PRIMARY),
        "q_content": ParagraphStyle("q_content", fontName=f, fontSize=11,
                                    textColor=C_TEXT, leading=18, leftIndent=16),
        "option": ParagraphStyle("option", fontName=f, fontSize=10,
                                 textColor=C_TEXT, leftIndent=32, spaceAfter=2),
        "answer_line": ParagraphStyle("answer_line", fontName=f, fontSize=10,
                                      textColor=C_SUBTEXT, leftIndent=16, spaceAfter=8),
        "header": ParagraphStyle("header", fontName=fb, fontSize=9,
                                 textColor=C_SUBTEXT, alignment=TA_RIGHT),
        "score_big": ParagraphStyle("score_big", fontName=fb, fontSize=32,
                                    textColor=C_PRIMARY, alignment=TA_CENTER),
        "tag": ParagraphStyle("tag", fontName=fb, fontSize=9,
                              textColor=colors.white, alignment=TA_CENTER),
    }


def _page_header_footer(canvas_obj, doc, title: str):
    """每页页眉页脚"""
    _ensure_font()
    canvas_obj.saveState()
    w, h = A4
    # 页眉
    canvas_obj.setFont(_FONT_NAME, 8)
    canvas_obj.setFillColor(C_SUBTEXT)
    canvas_obj.drawString(2 * cm, h - 1.2 * cm, title)
    canvas_obj.drawRightString(w - 2 * cm, h - 1.2 * cm,
                               f"生成时间：{datetime.now().strftime('%Y-%m-%d')}")
    canvas_obj.setStrokeColor(C_BORDER)
    canvas_obj.line(2 * cm, h - 1.4 * cm, w - 2 * cm, h - 1.4 * cm)
    # 页脚
    canvas_obj.line(2 * cm, 1.2 * cm, w - 2 * cm, 1.2 * cm)
    canvas_obj.setFont(_FONT_NAME, 8)
    canvas_obj.drawCentredString(w / 2, 0.8 * cm,
                                 f"第 {canvas_obj.getPageNumber()} 页  ·  小学数学智能练习系统")
    canvas_obj.restoreState()


# ─────────────────────────────────────────────
# 1. 试卷 PDF
# ─────────────────────────────────────────────

def generate_exam_pdf(
    questions: list[dict],
    title: str,
    grade: str,
    semester: str,
    student_name: str = "",
    show_answers: bool = False,
) -> bytes:
    """生成试卷 PDF，返回 bytes"""
    _ensure_font()
    s = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
    )

    story = []
    page_title = f"{grade}{semester} 数学练习卷"

    # ── 封面区 ──────────────────────────────
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(page_title, s["title"]))

    total_score = sum(q.get("score", 0) for q in questions)
    q_count = len(questions)
    meta = f"共 {q_count} 题 · 满分 {total_score} 分 · 人教版"
    story.append(Paragraph(meta, s["subtitle"]))

    # 学生信息栏
    info_data = [
        [
            Paragraph("姓名：_______________", s["body"]),
            Paragraph("班级：_______________", s["body"]),
            Paragraph(f"得分：___________", s["body"]),
        ]
    ]
    info_table = Table(info_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
    info_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("LINEAFTER", (0, 0), (1, -1), 0.5, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 0.3 * cm))

    # ── 按题型分组出题 ──────────────────────
    type_order = ["选择题", "判断题", "填空题", "计算题", "应用题"]
    grouped: dict[str, list] = {}
    for q in questions:
        grouped.setdefault(q.get("type", "其他"), []).append(q)
    type_seq = [t for t in type_order if t in grouped] + \
               [t for t in grouped if t not in type_order]

    roman = ["一", "二", "三", "四", "五", "六"]
    section_idx = 0

    for qtype in type_seq:
        qs = grouped[qtype]
        sec_score = sum(q.get("score", 0) for q in qs)
        r = roman[section_idx] if section_idx < len(roman) else str(section_idx + 1)
        section_idx += 1

        section_title = (
            f"{r}、{qtype}（共 {len(qs)} 题，每题 {qs[0].get('score',0)} 分，"
            f"本题共 {sec_score} 分）"
        )
        story.append(Paragraph(section_title, s["section"]))

        if qtype == "选择题":
            story.append(Paragraph("（将正确答案的字母填入括号）", s["small"]))
        elif qtype == "判断题":
            story.append(Paragraph("（正确的打对号，错误的打错号，填入括号）", s["small"]))

        for q in qs:
            items = []
            content_text = f"{q['id']}. {q['content']}"
            if qtype == "选择题":
                content_text += "（　　）"
            elif qtype == "判断题":
                content_text += "（　　）"

            items.append(Paragraph(content_text, s["q_content"]))

            if q.get("options"):
                for opt in q["options"]:
                    items.append(Paragraph(opt, s["option"]))

            if qtype in ("填空题",):
                pass  # 下划线已在题目中
            elif qtype in ("计算题", "应用题"):
                items.append(Paragraph("解题过程：", s["answer_line"]))
                for _ in range(4 if qtype == "应用题" else 3):
                    items.append(HRFlowable(width="85%", thickness=0.3,
                                            color=C_BORDER, spaceAfter=6))

            if show_answers:
                ans_text = f"【答案：{q.get('answer', '')}】"
                items.append(Paragraph(ans_text,
                                       ParagraphStyle("ans", fontName=_FONT_NAME,
                                                      fontSize=9, textColor=C_SUCCESS,
                                                      leftIndent=16)))

            story.append(KeepTogether(items + [Spacer(1, 0.15 * cm)]))

        story.append(Spacer(1, 0.2 * cm))

    doc.build(
        story,
        onFirstPage=lambda c, d: _page_header_footer(c, d, page_title),
        onLaterPages=lambda c, d: _page_header_footer(c, d, page_title),
    )
    return buf.getvalue()


# ─────────────────────────────────────────────
# 2. 分析报告 PDF
# ─────────────────────────────────────────────

def generate_report_pdf(
    student_name: str,
    grade: str,
    exam_title: str,
    graded_results: list[dict],
    analysis: dict,
    kp_stats: dict,
    score: float,
    total_score: float,
    submitted_at: str = "",
) -> bytes:
    _ensure_font()
    s = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
    )

    report_title = f"{student_name} · 学习分析报告"
    story = []
    pct = round(score / total_score * 100) if total_score else 0
    level = analysis.get("summary", {}).get("level", "")
    comment = analysis.get("summary", {}).get("overall_comment", "")

    # ── 报告头 ──────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("学习分析报告", s["title"]))
    story.append(Paragraph(
        f"{exam_title}  ·  {grade}  ·  {submitted_at[:10] if submitted_at else ''}",
        s["subtitle"]
    ))

    # ── 得分卡 ──────────────────────────────
    score_color = C_SUCCESS if pct >= 80 else C_WARNING if pct >= 60 else C_DANGER
    score_data = [[
        Paragraph(f"{int(score)}", ParagraphStyle("sc", fontName=_FONT_BOLD_NAME,
                  fontSize=40, textColor=score_color, alignment=TA_CENTER)),
        Paragraph(f"/ {int(total_score)}", ParagraphStyle("tc", fontName=_FONT_NAME,
                  fontSize=16, textColor=C_SUBTEXT, alignment=TA_LEFT)),
        Table([
            [Paragraph(f"正确率  {pct}%", ParagraphStyle("rate", fontName=_FONT_BOLD_NAME,
                        fontSize=16, textColor=score_color))],
            [Paragraph(f"综合评级：{level}", s["body"])],
            [Paragraph(comment, s["small"])],
        ], colWidths=[10 * cm]),
    ]]
    score_table = Table(score_data, colWidths=[3 * cm, 2 * cm, 10 * cm])
    score_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("BACKGROUND", (0, 0), (-1, -1), C_BG_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 16),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── 知识点掌握表 ──────────────────────────
    if kp_stats:
        story.append(Paragraph("知识点掌握分析", s["section"]))
        kp_rows = [[
            Paragraph("知识点", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                       fontSize=10, textColor=colors.white)),
            Paragraph("正确题数", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                       fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("正确率", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                       fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("掌握情况", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                       fontSize=10, textColor=colors.white, alignment=TA_CENTER)),
        ]]
        for kp, v in sorted(kp_stats.items(), key=lambda x: x[1]["rate"]):
            r = v["rate"]
            level_txt = "掌握良好" if r >= 0.9 else "基本掌握" if r >= 0.7 else \
                        "需要加强" if r >= 0.5 else "严重薄弱"
            level_color = C_SUCCESS if r >= 0.9 else C_PRIMARY if r >= 0.7 else \
                          C_WARNING if r >= 0.5 else C_DANGER
            kp_rows.append([
                Paragraph(kp, s["body"]),
                Paragraph(f"{v['correct']}/{v['total']}", ParagraphStyle(
                    "kp_num", fontName=_FONT_NAME, fontSize=10, alignment=TA_CENTER)),
                Paragraph(f"{round(r * 100)}%", ParagraphStyle(
                    "kp_rate", fontName=_FONT_BOLD_NAME, fontSize=10,
                    textColor=level_color, alignment=TA_CENTER)),
                Paragraph(level_txt, ParagraphStyle(
                    "kp_lv", fontName=_FONT_NAME, fontSize=10,
                    textColor=level_color, alignment=TA_CENTER)),
            ])

        kp_table = Table(kp_rows, colWidths=[7 * cm, 2.5 * cm, 2.5 * cm, 3 * cm])
        kp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(kp_table)
        story.append(Spacer(1, 0.4 * cm))

    # ── 知识点图表 ──────────────────────────
    if kp_stats:
        chart_img = _render_kp_chart(kp_stats)
        if chart_img:
            story.append(chart_img)
            story.append(Spacer(1, 0.3 * cm))

    # ── 题目详情 ──────────────────────────────
    story.append(Paragraph("答题详情", s["section"]))
    detail_rows = [[
        Paragraph("题号", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("类型", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("知识点", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white)),
        Paragraph("学生答案", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("正确答案", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
        Paragraph("得分", ParagraphStyle("th", fontName=_FONT_BOLD_NAME,
                   fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
    ]]
    for r in graded_results:
        g = r.get("grading", {})
        is_ok = g.get("is_correct", False)
        score_got = g.get("score_got", 0)
        max_s = r.get("score", 0)
        sc = C_SUCCESS if is_ok else C_DANGER
        detail_rows.append([
            Paragraph(f"第{r['id']}题", ParagraphStyle("dc", fontName=_FONT_NAME,
                       fontSize=9, alignment=TA_CENTER)),
            Paragraph(r.get("type", ""), ParagraphStyle("dt", fontName=_FONT_NAME,
                       fontSize=9, alignment=TA_CENTER)),
            Paragraph(r.get("knowledge_point", ""), ParagraphStyle("dk", fontName=_FONT_NAME,
                       fontSize=9)),
            Paragraph(str(r.get("student_answer", "")), ParagraphStyle("da", fontName=_FONT_NAME,
                       fontSize=9, alignment=TA_CENTER)),
            Paragraph(str(r.get("answer", "")), ParagraphStyle("daa", fontName=_FONT_NAME,
                       fontSize=9, textColor=C_SUCCESS, alignment=TA_CENTER)),
            Paragraph(f"{score_got}/{max_s}", ParagraphStyle("ds", fontName=_FONT_BOLD_NAME,
                       fontSize=9, textColor=sc, alignment=TA_CENTER)),
        ])

    det_table = Table(detail_rows, colWidths=[1.8*cm, 1.8*cm, 5*cm, 2.2*cm, 2.2*cm, 2*cm])
    det_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(det_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── 改进建议 ──────────────────────────────
    suggestions = analysis.get("study_suggestions", [])
    if suggestions:
        story.append(Paragraph("改进建议", s["section"]))
        for i, sug in enumerate(suggestions, 1):
            text = f"{i}. <b>{sug.get('title', '')}</b>  {sug.get('detail', '')}"
            story.append(Paragraph(text, s["body"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── 薄弱知识点专练提示 ────────────────────
    weak_points = analysis.get("weak_points_ranked", [])
    if weak_points:
        story.append(Paragraph("建议专项练习", s["section"]))
        wp_data = [[
            Paragraph("知识点", ParagraphStyle("wth", fontName=_FONT_BOLD_NAME,
                       fontSize=9, textColor=colors.white)),
            Paragraph("紧迫程度", ParagraphStyle("wth", fontName=_FONT_BOLD_NAME,
                       fontSize=9, textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("练习建议", ParagraphStyle("wth", fontName=_FONT_BOLD_NAME,
                       fontSize=9, textColor=colors.white)),
        ]]
        for wp in weak_points:
            urgency = wp.get("urgency", "中")
            uc = C_DANGER if urgency == "高" else C_WARNING if urgency == "中" else C_PRIMARY
            wp_data.append([
                Paragraph(wp.get("knowledge_point", ""), s["small"]),
                Paragraph(urgency, ParagraphStyle("wu", fontName=_FONT_BOLD_NAME,
                           fontSize=9, textColor=uc, alignment=TA_CENTER)),
                Paragraph(wp.get("suggested_focus", ""), s["small"]),
            ])
        wp_table = Table(wp_data, colWidths=[5*cm, 2.5*cm, 7.5*cm])
        wp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_SUBTEXT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(wp_table)

    doc.build(
        story,
        onFirstPage=lambda c, d: _page_header_footer(c, d, report_title),
        onLaterPages=lambda c, d: _page_header_footer(c, d, report_title),
    )
    return buf.getvalue()


def _render_kp_chart(kp_stats: dict) -> RLImage | None:
    """渲染知识点柱状图并返回 RLImage"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import numpy as np
        import os as _os

        # 字体
        for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]:
            if _os.path.exists(fp):
                fm.fontManager.addfont(fp)
                prop = fm.FontProperties(fname=fp)
                plt.rcParams["font.family"] = prop.get_name()
                break
        plt.rcParams["axes.unicode_minus"] = False

        names = list(kp_stats.keys())
        rates = [kp_stats[k]["rate"] * 100 for k in names]
        bar_colors = ["#52B788" if r >= 80 else "#4B7BEC" if r >= 60
                      else "#F4A261" if r >= 40 else "#E07A7A"
                      for r in rates]
        short = [n if len(n) <= 7 else n[:6] + "…" for n in names]

        fig, ax = plt.subplots(figsize=(7, max(2.5, len(names) * 0.45)))
        bars = ax.barh(short, rates, color=bar_colors, height=0.55, alpha=0.9)
        ax.set_xlim(0, 105)
        ax.axvline(60, color="#F4A261", linestyle="--", alpha=0.6, linewidth=1, label="基准60%")
        ax.axvline(80, color="#52B788", linestyle="--", alpha=0.6, linewidth=1, label="良好80%")
        for bar, rate in zip(bars, rates):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                    f"{rate:.0f}%", va="center", ha="left", fontsize=8)
        ax.set_xlabel("正确率 %", fontsize=9)
        ax.set_title("知识点掌握情况", fontsize=11, fontweight="bold")
        ax.legend(fontsize=8, loc="lower right")
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout(pad=0.4)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return RLImage(buf, width=15 * cm, height=max(5 * cm, len(names) * 0.9 * cm))
    except Exception:
        return None


# ─────────────────────────────────────────────
# 3. 学习周报 PDF
# ─────────────────────────────────────────────

def generate_weekly_report_pdf(
    student_name: str,
    grade: str,
    stats: dict,
    kp_list: list[dict],
    badges: list[dict],
) -> bytes:
    """生成一份学习周报 PDF，返回 bytes。
    stats keys: exam_count, avg_score, checkin_days, questions_done,
                week_points, total_points, streak, daily_list
    """
    _ensure_font()
    s = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
    )

    from datetime import datetime as _dt, timedelta as _td
    today = _dt.now()
    week_start = (today - _td(days=6)).strftime("%m/%d")
    week_end = today.strftime("%m/%d")
    report_title = f"{student_name} 学习周报"
    story = []

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("学习周报", s["title"]))
    story.append(Paragraph(
        f"{student_name}  ·  {grade}  ·  {week_start} — {week_end}",
        s["subtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 0.4 * cm))

    # ── 本周数据卡 ──
    story.append(Paragraph("本周学习概况", s["section"]))
    avg = stats.get("avg_score", 0)
    score_color = C_SUCCESS if avg >= 80 else C_WARNING if avg >= 60 else C_DANGER

    summary_data = [
        [
            Paragraph("完成试卷", ParagraphStyle("wlbl", fontName=_FONT_NAME, fontSize=10,
                       textColor=C_SUBTEXT, alignment=TA_CENTER)),
            Paragraph("平均分", ParagraphStyle("wlbl", fontName=_FONT_NAME, fontSize=10,
                       textColor=C_SUBTEXT, alignment=TA_CENTER)),
            Paragraph("打卡天数", ParagraphStyle("wlbl", fontName=_FONT_NAME, fontSize=10,
                       textColor=C_SUBTEXT, alignment=TA_CENTER)),
            Paragraph("完成题数", ParagraphStyle("wlbl", fontName=_FONT_NAME, fontSize=10,
                       textColor=C_SUBTEXT, alignment=TA_CENTER)),
            Paragraph("本周积分", ParagraphStyle("wlbl", fontName=_FONT_NAME, fontSize=10,
                       textColor=C_SUBTEXT, alignment=TA_CENTER)),
        ],
        [
            Paragraph(str(stats.get("exam_count", 0)),
                      ParagraphStyle("wval", fontName=_FONT_BOLD_NAME, fontSize=22,
                                     textColor=C_PRIMARY, alignment=TA_CENTER)),
            Paragraph(f"{avg}%",
                      ParagraphStyle("wval2", fontName=_FONT_BOLD_NAME, fontSize=22,
                                     textColor=score_color, alignment=TA_CENTER)),
            Paragraph(f"{stats.get('checkin_days', 0)}/7",
                      ParagraphStyle("wval3", fontName=_FONT_BOLD_NAME, fontSize=22,
                                     textColor=C_SUCCESS, alignment=TA_CENTER)),
            Paragraph(str(stats.get("questions_done", 0)),
                      ParagraphStyle("wval4", fontName=_FONT_BOLD_NAME, fontSize=22,
                                     textColor=C_TEXT, alignment=TA_CENTER)),
            Paragraph(str(stats.get("week_points", 0)),
                      ParagraphStyle("wval5", fontName=_FONT_BOLD_NAME, fontSize=22,
                                     textColor=C_WARNING, alignment=TA_CENTER)),
        ],
    ]
    sum_table = Table(summary_data, colWidths=[3 * cm] * 5)
    sum_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("BACKGROUND", (0, 0), (-1, 0), C_BG_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 0.3 * cm))

    # 连续打卡条幅
    streak = stats.get("streak", 0)
    streak_text = f"🔥 已连续学习 {streak} 天！  ⭐ 累计积分 {stats.get('total_points', 0)} 分"
    story.append(Paragraph(streak_text, ParagraphStyle(
        "streak", fontName=_FONT_BOLD_NAME, fontSize=12,
        textColor=C_WARNING, alignment=TA_CENTER,
        spaceBefore=4, spaceAfter=8,
    )))

    # ── 每日打卡情况 ──
    daily_list = stats.get("daily_list", [])
    if daily_list:
        story.append(Paragraph("每日学习记录", s["section"]))
        daily_rows = [[
            Paragraph("日期", ParagraphStyle("dh", fontName=_FONT_BOLD_NAME, fontSize=9,
                       textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("完成题数", ParagraphStyle("dh", fontName=_FONT_BOLD_NAME, fontSize=9,
                       textColor=colors.white, alignment=TA_CENTER)),
            Paragraph("状态", ParagraphStyle("dh", fontName=_FONT_BOLD_NAME, fontSize=9,
                       textColor=colors.white, alignment=TA_CENTER)),
        ]]
        for d in daily_list:
            done = d.get("questions", d.get("questions_done", 0))
            checked_in = done > 0
            status = "✓ 已打卡" if checked_in else "— 未打卡"
            sc = C_SUCCESS if checked_in else C_SUBTEXT
            daily_rows.append([
                Paragraph(d.get("date", ""), s["small"]),
                Paragraph(str(done), ParagraphStyle("dv", fontName=_FONT_NAME, fontSize=9,
                           alignment=TA_CENTER)),
                Paragraph(status, ParagraphStyle("ds", fontName=_FONT_BOLD_NAME, fontSize=9,
                           textColor=sc, alignment=TA_CENTER)),
            ])
        daily_table = Table(daily_rows, colWidths=[5 * cm, 5 * cm, 5 * cm])
        daily_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(daily_table)
        story.append(Spacer(1, 0.3 * cm))

    # ── 知识点掌握（薄弱top5）──
    weak_kps = [k for k in kp_list if k.get("rate", 1) < 0.7][:5]
    strong_kps = [k for k in kp_list if k.get("rate", 0) >= 0.8][:5]
    if weak_kps:
        story.append(Paragraph("本周需加强知识点", s["section"]))
        for kp in weak_kps:
            r = kp.get("rate", 0)
            bar_w = round(r * 10)
            bar_fill = "■" * bar_w + "□" * (10 - bar_w)
            c_hex = "#E07A7A" if r < 0.5 else "#F4A261"
            text = (
                f"<b>{kp['knowledge_point']}</b>  "
                f"<font color='{c_hex}'>{bar_fill}</font>  "
                f"{round(r * 100)}%"
            )
            story.append(Paragraph(text, s["body"]))
        story.append(Spacer(1, 0.2 * cm))

    if strong_kps:
        story.append(Paragraph("掌握良好知识点", s["section"]))
        kp_names = "、".join(k["knowledge_point"] for k in strong_kps)
        story.append(Paragraph(f"✓  {kp_names}", ParagraphStyle(
            "good_kp", fontName=_FONT_NAME, fontSize=11,
            textColor=C_SUCCESS, spaceAfter=8,
        )))

    # ── 成就徽章 ──
    if badges:
        story.append(Paragraph("获得成就", s["section"]))
        badge_texts = "  ".join(
            f"{b.get('icon','')} {b.get('name','')}" for b in badges
        )
        story.append(Paragraph(badge_texts, s["body"]))
        story.append(Spacer(1, 0.2 * cm))

    # ── 家长留言区 ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("家长留言", s["section"]))
    for _ in range(3):
        story.append(HRFlowable(width="100%", thickness=0.3, color=C_BORDER, spaceAfter=14))

    doc.build(
        story,
        onFirstPage=lambda c, d: _page_header_footer(c, d, report_title),
        onLaterPages=lambda c, d: _page_header_footer(c, d, report_title),
    )
    return buf.getvalue()


def save_pdf(data: bytes, default_name: str) -> str | None:
    """弹出保存对话框，返回保存路径或 None"""
    from PyQt6.QtWidgets import QFileDialog
    path, _ = QFileDialog.getSaveFileName(
        None, "保存 PDF", default_name, "PDF 文件 (*.pdf)"
    )
    if path:
        with open(path, "wb") as f:
            f.write(data)
        return path
    return None
