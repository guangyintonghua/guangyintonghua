"""
本地统计分析：计算知识点掌握度、历史趋势等
（不依赖AI，纯数据计算）
"""
from collections import defaultdict


def compute_kp_stats(graded_results: list[dict]) -> dict:
    """
    按知识点统计正确率
    返回: {knowledge_point: {correct, total, rate, wrong_questions}}
    """
    stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0, "wrong_questions": []})
    for r in graded_results:
        kp = r.get("knowledge_point", "未分类")
        g = r["grading"]
        stats[kp]["total"] += 1
        if g["is_correct"]:
            stats[kp]["correct"] += 1
        else:
            stats[kp]["wrong_questions"].append(r["id"])
    for kp, v in stats.items():
        v["rate"] = round(v["correct"] / v["total"], 2) if v["total"] > 0 else 0.0
    return dict(stats)


def compute_error_distribution(graded_results: list[dict]) -> dict:
    """统计错误类型分布"""
    dist: dict[str, int] = defaultdict(int)
    for r in graded_results:
        et = r["grading"].get("error_type")
        if et:
            dist[et] += 1
    return dict(dist)


def compute_score(graded_results: list[dict]) -> tuple[int, int]:
    """返回 (得分, 总分)"""
    got = sum(r["grading"]["score_got"] for r in graded_results)
    total = sum(r["score"] for r in graded_results)
    return got, total


def get_weak_points(kp_stats: dict, threshold: float = 0.6) -> list[dict]:
    """
    返回薄弱知识点列表（正确率低于threshold），按正确率升序排列
    """
    weak = [
        {"knowledge_point": kp, "rate": v["rate"], "total": v["total"], "correct": v["correct"]}
        for kp, v in kp_stats.items()
        if v["rate"] < threshold and v["total"] > 0
    ]
    return sorted(weak, key=lambda x: x["rate"])


def compute_history_trend(submissions: list[dict]) -> dict:
    """
    从历史提交记录计算趋势数据
    submissions: 数据库查出的历史记录列表，按时间升序
    返回: {dates, scores, accuracy_rates}
    """
    dates, scores, rates = [], [], []
    for s in submissions[-10:]:  # 最近10次
        dates.append(s["submitted_at"][:10])
        score_got = s.get("score", 0)
        total = s.get("total_score", 100)
        scores.append(score_got)
        rates.append(round(score_got / total * 100, 1) if total > 0 else 0)
    return {"dates": dates, "scores": scores, "rates": rates}


def mastery_level(rate: float) -> str:
    if rate >= 0.9:
        return "掌握良好"
    elif rate >= 0.7:
        return "基本掌握"
    elif rate >= 0.5:
        return "需要加强"
    else:
        return "严重薄弱"


def mastery_color(rate: float) -> str:
    """返回对应掌握度的颜色"""
    if rate >= 0.9:
        return "#52B788"   # 绿
    elif rate >= 0.7:
        return "#4B7BEC"   # 蓝
    elif rate >= 0.5:
        return "#F4A261"   # 橙
    else:
        return "#E07A7A"   # 红
