import sqlite3
import json
import os
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "exam.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            title TEXT,
            grade TEXT,
            semester TEXT,
            topics TEXT,
            questions TEXT,
            total_score INTEGER DEFAULT 100,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER,
            student_id INTEGER,
            answers TEXT,
            graded_results TEXT,
            analysis TEXT,
            kp_stats TEXT,
            score REAL DEFAULT 0,
            total_score REAL DEFAULT 100,
            image_path TEXT,
            submitted_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (exam_id) REFERENCES exams(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS kp_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            knowledge_point TEXT,
            grade TEXT,
            total_attempts INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(student_id, knowledge_point),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            points INTEGER,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS daily_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            date TEXT,
            questions_done INTEGER DEFAULT 0,
            UNIQUE(student_id, date),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            badge_key TEXT,
            earned_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(student_id, badge_key),
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
        """)


# ── 学生 ──────────────────────────────────────

def create_student(name: str, grade: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO students (name, grade) VALUES (?, ?)", (name, grade)
        )
        return cur.lastrowid


def get_all_students() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM students ORDER BY id DESC")]


def get_student(student_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
        return dict(row) if row else None


def update_student(student_id: int, name: str, grade: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET name=?, grade=? WHERE id=?", (name, grade, student_id)
        )


# ── 试卷 ──────────────────────────────────────

def save_exam(student_id: int, title: str, grade: str, semester: str,
              topics: list, questions: list, total_score: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO exams (student_id, title, grade, semester, topics, questions, total_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (student_id, title, grade, semester,
             json.dumps(topics, ensure_ascii=False),
             json.dumps(questions, ensure_ascii=False),
             total_score),
        )
        return cur.lastrowid


def get_exam(exam_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["topics"] = json.loads(d["topics"])
        d["questions"] = json.loads(d["questions"])
        return d


def get_recent_exams(student_id: int, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, grade, semester, total_score, created_at FROM exams "
            "WHERE student_id=? ORDER BY id DESC LIMIT ?",
            (student_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── 提交/批改结果 ────────────────────────────

def save_submission(exam_id: int, student_id: int, answers: dict,
                    graded_results: list, analysis: dict, kp_stats: dict,
                    score: float, total_score: float, image_path: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO submissions
               (exam_id, student_id, answers, graded_results, analysis, kp_stats,
                score, total_score, image_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                exam_id, student_id,
                json.dumps(answers, ensure_ascii=False),
                json.dumps(graded_results, ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                json.dumps(kp_stats, ensure_ascii=False),
                score, total_score, image_path,
            ),
        )
        sub_id = cur.lastrowid
    return sub_id


def get_submission(sub_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (sub_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("answers", "graded_results", "analysis", "kp_stats"):
            if d[key]:
                d[key] = json.loads(d[key])
        return d


def get_submissions_for_exam(exam_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE exam_id=? ORDER BY submitted_at DESC",
            (exam_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("answers", "graded_results", "analysis", "kp_stats"):
                if d[key]:
                    d[key] = json.loads(d[key])
            result.append(d)
        return result


def get_student_submissions(student_id: int, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.score, s.total_score, s.submitted_at,
                      e.title, e.grade, e.semester
               FROM submissions s JOIN exams e ON s.exam_id=e.id
               WHERE s.student_id=? ORDER BY s.submitted_at DESC LIMIT ?""",
            (student_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── 知识点掌握度（累计） ─────────────────────

def update_kp_mastery(student_id: int, grade: str, kp_stats: dict):
    with get_conn() as conn:
        for kp, v in kp_stats.items():
            conn.execute(
                """INSERT INTO kp_mastery (student_id, knowledge_point, grade, total_attempts, correct_count)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, knowledge_point) DO UPDATE SET
                     total_attempts = total_attempts + excluded.total_attempts,
                     correct_count = correct_count + excluded.correct_count,
                     last_updated = datetime('now', 'localtime')""",
                (student_id, kp, grade, v["total"], v["correct"]),
            )


def get_kp_mastery(student_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM kp_mastery WHERE student_id=? ORDER BY "
            "CAST(correct_count AS REAL)/CAST(total_attempts AS REAL) ASC",
            (student_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["rate"] = d["correct_count"] / d["total_attempts"] if d["total_attempts"] > 0 else 0
            result.append(d)
        return result


def get_adaptive_difficulty(student_id: int, selected_topics: list | None = None) -> dict:
    """
    Compute adaptive difficulty distribution based on the student's recent history.

    Blends overall score rate (last 5 exams) with per-knowledge-point mastery
    for the selected topics (60 % KP weight, 40 % overall when both are available).

    Returns a dict with keys: easy, medium, hard (int %), plus diagnostic fields
    avg_score_rate, avg_kp_rate, exam_count, kp_count.
    """
    subs = get_student_submissions(student_id, limit=5)
    kp_data = {m["knowledge_point"]: m["rate"] for m in get_kp_mastery(student_id)}

    avg_score_rate = None
    exam_count = 0
    if subs:
        rates = [s["score"] / s["total_score"] for s in subs if s.get("total_score", 0) > 0]
        if rates:
            avg_score_rate = sum(rates) / len(rates)
            exam_count = len(rates)

    avg_kp_rate = None
    kp_count = 0
    if selected_topics:
        topic_rates = [kp_data[t] for t in selected_topics if t in kp_data]
        if topic_rates:
            avg_kp_rate = sum(topic_rates) / len(topic_rates)
            kp_count = len(topic_rates)

    if avg_kp_rate is not None and avg_score_rate is not None:
        combined = 0.6 * avg_kp_rate + 0.4 * avg_score_rate
    elif avg_kp_rate is not None:
        combined = avg_kp_rate
    elif avg_score_rate is not None:
        combined = avg_score_rate
    else:
        return {"easy": 40, "medium": 40, "hard": 20,
                "avg_score_rate": None, "avg_kp_rate": None,
                "exam_count": 0, "kp_count": 0}

    # 根据综合掌握率映射到难度分布
    if combined >= 0.85:
        easy, medium, hard = 15, 40, 45   # 优秀 → 大幅提高挑战
    elif combined >= 0.70:
        easy, medium, hard = 25, 45, 30   # 良好 → 适当加大难度
    elif combined >= 0.55:
        easy, medium, hard = 40, 40, 20   # 中等 → 均衡默认
    elif combined >= 0.40:
        easy, medium, hard = 50, 38, 12   # 偏弱 → 巩固基础
    else:
        easy, medium, hard = 60, 32, 8    # 薄弱 → 以简单为主建立信心

    return {
        "easy": easy, "medium": medium, "hard": hard,
        "avg_score_rate": avg_score_rate,
        "avg_kp_rate": avg_kp_rate,
        "exam_count": exam_count,
        "kp_count": kp_count,
    }


# ── 积分 ──────────────────────────────────────

def award_points(student_id: int, points: int, reason: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO points_log (student_id, points, reason) VALUES (?, ?, ?)",
            (student_id, points, reason),
        )


def get_total_points(student_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(points), 0) FROM points_log WHERE student_id=?",
            (student_id,),
        ).fetchone()
        return int(row[0])


# ── 每日打卡 / 连续天数 ───────────────────────

def checkin_today(student_id: int, questions_done: int = 0):
    today = date.today().isoformat()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO daily_checkins (student_id, date, questions_done)
               VALUES (?, ?, ?)
               ON CONFLICT(student_id, date) DO UPDATE SET
                 questions_done = questions_done + excluded.questions_done""",
            (student_id, today, questions_done),
        )


def get_streak(student_id: int) -> int:
    """返回截至今天的连续打卡天数。"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT date FROM daily_checkins WHERE student_id=? ORDER BY date DESC",
            (student_id,),
        ).fetchall()
    if not rows:
        return 0
    dates = {r[0] for r in rows}
    streak = 0
    check = date.today()
    while check.isoformat() in dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


def get_daily_questions_done(student_id: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT questions_done FROM daily_checkins WHERE student_id=? AND date=?",
            (student_id, today),
        ).fetchone()
        return row[0] if row else 0


# ── 徽章 ──────────────────────────────────────

BADGE_DEFS = {
    "first_exam":    ("🎉", "初试牛刀",  "完成第一套试卷"),
    "streak_3":      ("🔥", "三日连胜",  "连续3天练习"),
    "streak_7":      ("⚡", "一周不停",  "连续7天练习"),
    "streak_30":     ("🏆", "月度冠军",  "连续30天练习"),
    "perfect_score": ("💯", "满分王",    "获得一次满分"),
    "questions_100": ("📚", "百题斗士",  "累计完成100道题"),
    "questions_500": ("🌟", "数学达人",  "累计完成500道题"),
    "speed_ace":     ("🚀", "口算飞人",  "口算速练20题全对"),
    "kp_master":     ("🎯", "知识点精通","任一知识点掌握度达90%"),
}


def get_badges(student_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT badge_key, earned_at FROM badges WHERE student_id=? ORDER BY earned_at",
            (student_id,),
        ).fetchall()
    result = []
    for r in rows:
        key = r[0]
        if key in BADGE_DEFS:
            icon, name, desc = BADGE_DEFS[key]
            result.append({"key": key, "icon": icon, "name": name,
                            "desc": desc, "earned_at": r[1]})
    return result


def _award_badge(conn, student_id: int, badge_key: str) -> bool:
    """尝试颁发徽章，返回 True 表示是新获得的。"""
    try:
        conn.execute(
            "INSERT INTO badges (student_id, badge_key) VALUES (?, ?)",
            (student_id, badge_key),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def check_and_award_badges(student_id: int) -> list[str]:
    """检查所有徽章条件，返回本次新获得的徽章 key 列表。"""
    newly_earned = []
    with get_conn() as conn:
        # 累计做题数
        row = conn.execute(
            "SELECT COALESCE(SUM(total_attempts), 0) FROM kp_mastery WHERE student_id=?",
            (student_id,),
        ).fetchone()
        total_q = int(row[0])

        # 提交次数（是否完成过试卷）
        sub_count = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE student_id=?", (student_id,)
        ).fetchone()[0]

        # 是否有满分
        perfect = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE student_id=? AND score >= total_score AND total_score > 0",
            (student_id,),
        ).fetchone()[0]

        # kp 最高掌握率
        best_kp = conn.execute(
            "SELECT MAX(CAST(correct_count AS REAL)/CAST(total_attempts AS REAL)) "
            "FROM kp_mastery WHERE student_id=? AND total_attempts > 0",
            (student_id,),
        ).fetchone()[0] or 0

        streak = get_streak(student_id)

        checks = [
            ("first_exam",    sub_count >= 1),
            ("streak_3",      streak >= 3),
            ("streak_7",      streak >= 7),
            ("streak_30",     streak >= 30),
            ("perfect_score", perfect >= 1),
            ("questions_100", total_q >= 100),
            ("questions_500", total_q >= 500),
            ("kp_master",     best_kp >= 0.9),
        ]
        for key, condition in checks:
            if condition and _award_badge(conn, student_id, key):
                newly_earned.append(key)
    return newly_earned


# ── 错题本 ────────────────────────────────────

def get_all_wrong_answers(student_id: int, kp_filter: str | None = None) -> list[dict]:
    """聚合该学生所有提交中答错的题目，按知识点可过滤。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.graded_results, s.submitted_at, e.grade, e.title
               FROM submissions s JOIN exams e ON s.exam_id = e.id
               WHERE s.student_id = ? ORDER BY s.submitted_at DESC""",
            (student_id,),
        ).fetchall()

    wrong: list[dict] = []
    seen: set[str] = set()   # 去重：同一题内容只保留最近一次
    for row in rows:
        try:
            graded = json.loads(row["graded_results"]) if row["graded_results"] else []
        except Exception:
            continue
        for q in graded:
            if q.get("grading", {}).get("is_correct", True):
                continue
            kp = q.get("knowledge_point", "")
            if kp_filter and kp != kp_filter:
                continue
            key = f"{q.get('content','')[:30]}"
            if key in seen:
                continue
            seen.add(key)
            wrong.append({
                **q,
                "submitted_at": row["submitted_at"],
                "exam_title": row["title"],
                "grade": row["grade"],
            })
    return wrong


def get_wrong_kp_list(student_id: int) -> list[str]:
    """返回该学生出现过错误的知识点列表（去重）。"""
    wrong = get_all_wrong_answers(student_id)
    seen, result = set(), []
    for w in wrong:
        kp = w.get("knowledge_point", "")
        if kp and kp not in seen:
            seen.add(kp)
            result.append(kp)
    return result


# ── 周报统计 ──────────────────────────────────

def get_weekly_stats(student_id: int) -> dict:
    """返回过去7天的学习统计数据。"""
    today = date.today()
    week_ago = (today - timedelta(days=6)).isoformat()
    today_str = today.isoformat()

    with get_conn() as conn:
        # 本周提交次数 & 平均分
        subs = conn.execute(
            """SELECT score, total_score, submitted_at FROM submissions
               WHERE student_id=? AND DATE(submitted_at) BETWEEN ? AND ?""",
            (student_id, week_ago, today_str),
        ).fetchall()

        # 本周打卡天数 & 累计做题
        checkins = conn.execute(
            """SELECT date, questions_done FROM daily_checkins
               WHERE student_id=? AND date BETWEEN ? AND ?""",
            (student_id, week_ago, today_str),
        ).fetchall()

        # 本周积分
        pts = conn.execute(
            """SELECT COALESCE(SUM(points), 0) FROM points_log
               WHERE student_id=? AND DATE(created_at) BETWEEN ? AND ?""",
            (student_id, week_ago, today_str),
        ).fetchone()[0]

    sub_count = len(subs)
    avg_score = 0.0
    if subs:
        rates = [s[0] / s[1] * 100 for s in subs if s[1] > 0]
        avg_score = round(sum(rates) / len(rates), 1) if rates else 0.0

    checkin_days = len(checkins)
    questions_done = sum(c[1] for c in checkins)

    # 每日做题明细（用于折线图）
    daily = {c[0]: c[1] for c in checkins}
    daily_list = []
    for i in range(7):
        d = (today - timedelta(days=6 - i)).isoformat()
        daily_list.append({"date": d, "questions": daily.get(d, 0)})

    return {
        "exam_count": sub_count,
        "avg_score": avg_score,
        "checkin_days": checkin_days,
        "questions_done": questions_done,
        "week_points": int(pts),
        "total_points": get_total_points(student_id),
        "streak": get_streak(student_id),
        "daily_list": daily_list,
    }
