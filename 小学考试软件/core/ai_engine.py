import json
import re
import base64
import logging
from pathlib import Path
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError
import config

log = logging.getLogger("app.ai")

# 友好错误提示
_ERR_MAP = {
    AuthenticationError: "API Key 无效或已过期，请在【设置】中重新配置",
    RateLimitError: "API 调用超出频率限制，请稍后再试",
    APIConnectionError: "网络连接失败，请检查网络后重试",
}


def _client(timeout: float = 30.0, max_retries: int = 1) -> OpenAI:
    key = config.get("api_key")
    if not key:
        raise ValueError("API Key 未配置，请先在【设置】中填写 DeepSeek API Key")
    return OpenAI(
        api_key=key,
        base_url=config.get("api_base_url") or "https://api.deepseek.com",
        timeout=timeout,
        max_retries=max_retries,
    )


def _chat(messages: list, temperature: float = 0.7, model: str = None,
          use_cache: bool = False, timeout: float = 30.0, max_retries: int = 1) -> str:
    cache_key = None
    if use_cache:
        from utils import cache as _cache
        import json as _json
        cache_key = _json.dumps({"m": messages, "t": temperature}, ensure_ascii=False)
        cached = _cache.get(cache_key)
        if cached:
            log.debug("Cache hit")
            return cached

    try:
        client = _client(timeout=timeout, max_retries=max_retries)
        m = model or config.get("model_chat") or "deepseek-chat"
        log.debug(f"API call model={m} timeout={timeout}s messages={len(messages)}")
        resp = client.chat.completions.create(
            model=m,
            messages=messages,
            temperature=temperature,
        )
        result = resp.choices[0].message.content.strip()
        log.debug(f"API response length={len(result)}")

        if use_cache and cache_key:
            from utils import cache as _cache
            _cache.set(cache_key, result)

        return result

    except tuple(_ERR_MAP.keys()) as e:
        friendly = _ERR_MAP.get(type(e), str(e))
        log.error(f"API error: {type(e).__name__}: {e}", exc_info=True)
        raise RuntimeError(friendly) from e
    except Exception as e:
        log.error(f"Unexpected API error: {type(e).__name__}: {e}", exc_info=True)
        raise


def _parse_json(text: str) -> dict | list:
    """从模型回复中提取JSON，容忍markdown代码块包裹"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


# ──────────────────────────────────────────────
# 1. 出题
# ──────────────────────────────────────────────

GENERATE_SYSTEM = """你是一位经验丰富的小学数学教研专家，专注人教版教材，精通各年级知识点体系。
你生成的题目必须：符合年级认知水平、表述严谨清晰、答案唯一确定、覆盖指定知识点。
只输出JSON，不输出任何解释。"""

GENERATE_USER = """请为{grade}{semester}生成一套数学练习题。
{region_context}
要求：
- 知识点范围：{topics}
- 难度分布：简单{easy}% / 中等{medium}% / 困难{hard}%
- 题型数量：
{type_lines}

严格按JSON格式输出，每题包含以下字段（不要输出其他内容）：
{{
  "questions": [
    {{
      "id": 1,
      "type": "选择题",
      "content": "题目正文",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "标准答案",
      "knowledge_point": "所属知识点",
      "difficulty": "简单|中等|困难",
      "score": 3
    }}
  ],
  "total_score": 100
}}

注意：
1. 选择题必须有4个选项，非选择题options为空列表[]
2. 判断题answer填"正确"或"错误"
3. 应用题情境真实，数字合理
4. 同类型题目知识点尽量不重复
"""


def generate_exam(
    grade: str,
    semester: str,
    topics: list[str],
    type_counts: dict,  # {题型: (数量, 每题分值)}
    difficulty: tuple = (40, 40, 20),  # easy/medium/hard %
) -> dict:
    from data.regions import get_exam_context
    region = config.get("region") or "全国通用"
    textbook = config.get("textbook_version") or "人教版（PEP）"
    ctx = get_exam_context(region, textbook)
    region_context = f"\n{ctx}\n" if ctx else ""

    type_lines = "\n".join(
        f"  - {t}：{v[0]}道，每题{v[1]}分" for t, v in type_counts.items() if v[0] > 0
    )
    user_msg = GENERATE_USER.format(
        grade=grade,
        semester=semester,
        topics="、".join(topics),
        easy=difficulty[0],
        medium=difficulty[1],
        hard=difficulty[2],
        type_lines=type_lines,
        region_context=region_context,
    )
    raw = _chat(
        [
            {"role": "system", "content": GENERATE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.8,
        timeout=120.0,
        max_retries=0,
    )
    return _parse_json(raw)


# ──────────────────────────────────────────────
# 2. 批改
# ──────────────────────────────────────────────

GRADE_SYSTEM = """你是专业数学阅卷教师。批改时注意：
- 数学等价答案均算正确（如1/2=0.5=50%）
- 填空题允许书写差异，关键数值和单位正确即可
- 应用题过程对、结果因计算错误可酌情给分
- 只输出JSON，不输出其他内容"""

GRADE_USER = """批改以下题目：

题目：{content}
题目类型：{qtype}
标准答案：{answer}
学生答案：{student_answer}
满分：{score}分

输出JSON：
{{
  "is_correct": true/false,
  "score_got": 实际得分（数字）,
  "error_type": null或"粗心错误"|"概念错误"|"计算错误"|"审题错误"|"单位错误",
  "error_desc": "具体错在哪里（15字内，答对则填null）"
}}"""


def grade_question(question: dict, student_answer: str) -> dict:
    if not student_answer or student_answer.strip() in ("", "未作答"):
        return {
            "is_correct": False,
            "score_got": 0,
            "error_type": "未作答",
            "error_desc": "学生未填写答案",
        }
    user_msg = GRADE_USER.format(
        content=question["content"],
        qtype=question["type"],
        answer=question["answer"],
        student_answer=student_answer,
        score=question["score"],
    )
    raw = _chat(
        [
            {"role": "system", "content": GRADE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
    )
    return _parse_json(raw)


def grade_all(questions: list[dict], student_answers: dict) -> list[dict]:
    """批改所有题目，返回带批改结果的列表"""
    results = []
    for q in questions:
        ans = student_answers.get(str(q["id"]), "未作答")
        grading = grade_question(q, ans)
        results.append({**q, "student_answer": ans, "grading": grading})
    return results


# ──────────────────────────────────────────────
# 3. 深度分析报告
# ──────────────────────────────────────────────

ANALYSIS_SYSTEM = """你是资深小学数学教研员，擅长从答题数据中分析学生知识掌握情况。
分析要专业、具体、可操作，避免空话套话。只输出JSON。"""

ANALYSIS_USER = """请对以下答题数据进行深度分析：

学生：{student_name}，{grade}{semester}
本次得分：{score}/{total_score}（正确率{accuracy}%）

各题详情：
{question_detail}

知识点得分率：
{kp_stats}

错误类型分布：
{error_dist}

请输出专业分析报告（JSON格式）：
{{
  "summary": {{
    "level": "优秀|良好|中等|待提高",
    "overall_comment": "总体评价（30字内，指出最突出的优势和最需改进的方向）",
    "score_interpretation": "得分区间解读"
  }},
  "kp_analysis": [
    {{
      "knowledge_point": "知识点名称",
      "mastery_rate": 0.0,
      "status": "掌握良好|基本掌握|需要加强|严重薄弱",
      "wrong_count": 0,
      "total_count": 0,
      "diagnosis": "诊断（15字内）",
      "priority": 1
    }}
  ],
  "error_patterns": [
    {{
      "pattern": "错误规律描述",
      "affected_questions": [1, 3],
      "root_cause": "根本原因分析"
    }}
  ],
  "strengths": ["优势点1", "优势点2"],
  "weak_points_ranked": [
    {{
      "knowledge_point": "知识点",
      "urgency": "高|中|低",
      "suggested_focus": "建议专项练习内容（20字内）"
    }}
  ],
  "study_suggestions": [
    {{
      "title": "建议标题",
      "detail": "具体做法（30字内）",
      "priority": 1
    }}
  ]
}}"""


def analyze_results(
    student_name: str,
    grade: str,
    semester: str,
    graded_results: list[dict],
    kp_stats: dict,
) -> dict:
    total = sum(q["score"] for q in graded_results)
    got = sum(q["grading"]["score_got"] for q in graded_results)
    accuracy = round(got / total * 100, 1) if total > 0 else 0

    q_lines = []
    for r in graded_results:
        g = r["grading"]
        status = "✓" if g["is_correct"] else "✗"
        q_lines.append(
            f"第{r['id']}题[{r['type']}] {status} "
            f"得{g['score_got']}/{r['score']}分 "
            f"知识点:{r.get('knowledge_point','未知')} "
            f"错误类型:{g.get('error_type','无')}"
        )

    kp_lines = [
        f"  {kp}: {v['correct']}/{v['total']}题正确 ({round(v['correct']/v['total']*100) if v['total'] else 0}%)"
        for kp, v in kp_stats.items()
    ]

    error_counts: dict[str, int] = {}
    for r in graded_results:
        et = r["grading"].get("error_type")
        if et and et != "未作答":
            error_counts[et] = error_counts.get(et, 0) + 1

    user_msg = ANALYSIS_USER.format(
        student_name=student_name,
        grade=grade,
        semester=semester,
        score=got,
        total_score=total,
        accuracy=accuracy,
        question_detail="\n".join(q_lines),
        kp_stats="\n".join(kp_lines) or "暂无",
        error_dist=str(error_counts) if error_counts else "无错误",
    )

    raw = _chat(
        [
            {"role": "system", "content": ANALYSIS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        timeout=90.0,
        max_retries=0,
    )
    return _parse_json(raw)


# ──────────────────────────────────────────────
# 4. 专项练习出题
# ──────────────────────────────────────────────

PRACTICE_USER = """请针对"{knowledge_point}"这一知识点，为{grade}学生生成{count}道专项练习题。
{region_context}
要求：
1. 题目由浅入深，覆盖该知识点的各个角度
2. 混合题型（选择/填空/计算/应用各占一部分）
3. 每道题附上详细解析，帮助学生理解原理

严格按JSON输出（格式同生成试卷），不输出其他内容。"""


def generate_practice(knowledge_point: str, grade: str, count: int = 6) -> dict:
    from data.regions import get_exam_context
    region = config.get("region") or "全国通用"
    textbook = config.get("textbook_version") or "人教版（PEP）"
    ctx = get_exam_context(region, textbook)
    region_context = f"\n{ctx}\n" if ctx else ""

    raw = _chat(
        [
            {"role": "system", "content": GENERATE_SYSTEM},
            {
                "role": "user",
                "content": PRACTICE_USER.format(
                    knowledge_point=knowledge_point,
                    grade=grade,
                    count=count,
                    region_context=region_context,
                ),
            },
        ],
        temperature=0.75,
    )
    return _parse_json(raw)


# ──────────────────────────────────────────────
# 5. 解析手写答案（OCR后结构化）
# ──────────────────────────────────────────────

PARSE_ANSWERS_SYSTEM = """你擅长解析学生手写答案的OCR识别结果。
任务：从给定文本中提取题号与对应答案，输出结构化JSON。
规则：
- 识别格式如"1.A"、"2.25"、"3、正确"、"(4)B"等各种写法
- 如果某题号没有答案，填"未作答"
- 只输出JSON，格式：{{"answers": {{"1": "答案", "2": "答案", ...}}}}"""


def parse_handwritten_answers(ocr_text: str, question_count: int) -> dict:
    user_msg = (
        f"共{question_count}道题。\n"
        f"以下是OCR识别的学生答题内容，请提取每题答案：\n\n{ocr_text}"
    )
    raw = _chat(
        [
            {"role": "system", "content": PARSE_ANSWERS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
    )
    return _parse_json(raw)


def parse_handwritten_answers_vision(image_path: str, question_count: int) -> dict:
    """使用视觉模型直接识别图片中的手写答案"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

    client = _client()
    model = config.get("model_vision") or "deepseek-vl"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"这是一张学生手写的答题纸，共{question_count}道题。"
                            "请识别每道题的答案，以JSON格式输出：\n"
                            '{"answers": {"1": "答案", "2": "答案", ...}}\n'
                            "如某题未作答则填'未作答'，只输出JSON。"
                        ),
                    },
                ],
            }
        ],
        temperature=0.1,
    )
    return _parse_json(resp.choices[0].message.content.strip())


# ──────────────────────────────────────────────
# 6. 语音讲解文本生成
# ──────────────────────────────────────────────

VOICE_EXPLAIN_SYSTEM = """你是一位亲切耐心的小学数学老师，正在用语音给学生讲解题目。
要求：
- 用口语说话，自然流畅，像真人朗读一样
- 不要使用任何标点符号（句号除外），不要使用括号、冒号、顿号
- 不要出现数学公式符号，改用文字描述（比如"乘以"代替"×"，"等于"代替"="）
- 语言简单易懂，适合小学生
- 先点出知识点，再讲解题思路，最后说答案
- 控制在200字以内
只输出讲解内容，不输出任何其他东西。"""

VOICE_EXPLAIN_KNOWLEDGE_SYSTEM = """你是一位亲切的小学数学老师，正在为学生讲解一个知识点。
要求：
- 用口语说话，像讲故事一样生动
- 不使用任何标点符号（句号除外），不使用括号冒号等特殊符号
- 数学符号改用文字（"乘以""除以""等于""加上""减去"）
- 先说这个知识点是什么，再举一个简单例子，最后说学好它有什么用
- 语言简单亲切，适合小学生
- 控制在250字以内
只输出讲解内容。"""


def generate_voice_explanation(question: dict, grade: str = "") -> str:
    """
    为单道题目生成口语化讲解文本（用于TTS朗读）
    """
    options_text = ""
    if question.get("options"):
        options_text = "选项是 " + " ".join(
            opt.replace(".", "点").replace("A", "A选项").replace("B", "B选项")
            .replace("C", "C选项").replace("D", "D选项")
            for opt in question["options"]
        )

    user_msg = (
        f"年级：{grade}\n"
        f"题目类型：{question.get('type','')}\n"
        f"知识点：{question.get('knowledge_point','')}\n"
        f"题目内容：{question.get('content','')}\n"
        f"{options_text}\n"
        f"正确答案：{question.get('answer','')}\n"
        f"解题过程：{question.get('answer_detail','')}\n"
        f"易错点：{question.get('error_traps','')}"
    )
    return _chat(
        [
            {"role": "system", "content": VOICE_EXPLAIN_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.6,
        use_cache=True,
    )


def generate_voice_kp_explanation(knowledge_point: str, grade: str = "") -> str:
    """
    为某个知识点生成口语化概念讲解（用于TTS朗读）
    """
    user_msg = f"年级：{grade}\n请讲解知识点：{knowledge_point}"
    return _chat(
        [
            {"role": "system", "content": VOICE_EXPLAIN_KNOWLEDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.65,
        use_cache=True,
    )


# ──────────────────────────────────────────────
# 7. AI 辅导对话（引导式，不直接给答案）
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# 8. 动图讲解步骤分解
# ──────────────────────────────────────────────

GET_STEPS_SYSTEM = """你是数学解题步骤分解专家。将解题过程拆解为4-6个清晰步骤，每步简洁明确。只输出JSON。"""

GET_STEPS_USER = """题目：{content}
年级：{grade}
题型：{qtype}
知识点：{knowledge_point}
正确答案：{answer}

请将完整解题过程分解为4~6个步骤，严格按JSON输出：
{{
  "steps": [
    {{
      "step": 1,
      "title": "步骤标题（4-6字）",
      "content": "本步骤解题内容（20-50字，可包含算式）",
      "key_point": "核心要点或公式（10字内，若无则填空字符串）"
    }}
  ]
}}"""


def get_solution_steps(question: dict, grade: str) -> dict:
    """获取题目的逐步解题过程，用于动图讲解。"""
    user_msg = GET_STEPS_USER.format(
        content=question.get("content", ""),
        grade=grade,
        qtype=question.get("type", ""),
        knowledge_point=question.get("knowledge_point", ""),
        answer=question.get("answer", ""),
    )
    raw = _chat(
        [
            {"role": "system", "content": GET_STEPS_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        timeout=30.0,
    )
    return _parse_json(raw)


# ──────────────────────────────────────────────
# 7. AI 辅导对话（引导式，不直接给答案）
# ──────────────────────────────────────────────

GUIDE_SYSTEM = """你是一位耐心的小学数学辅导老师，正在用苏格拉底式引导法帮助学生解题。
规则：
- 绝对不直接说出答案
- 用提问和提示，一步一步引导学生自己想出答案
- 语言亲切简单，鼓励学生，适合小学生
- 每次回复控制在100字以内
- 如果学生说出了正确答案，夸奖并确认，但不再进一步讲解"""


def guide_student(question: dict, grade: str, history: list[dict]) -> str:
    """AI引导对话，history 格式: [{"role":"user"/"assistant","content":"..."}]"""
    system_ctx = (
        f"{GUIDE_SYSTEM}\n\n"
        f"当前题目（年级:{grade}）：\n"
        f"类型：{question.get('type','')}\n"
        f"知识点：{question.get('knowledge_point','')}\n"
        f"内容：{question.get('content','')}\n"
        f"（仅你知道的正确答案：{question.get('answer','')}，不要说出）"
    )
    messages = [{"role": "system", "content": system_ctx}] + history
    return _chat(messages, temperature=0.7, timeout=30.0)
