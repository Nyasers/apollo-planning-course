"""DeepSeek adapter using the OpenAI-compatible chat completions API."""
from __future__ import annotations

import copy
import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .config import Settings

SYSTEM_PROMPT = """你是 Apollo Claw 的实验解释助手，只服务 Apollo PnC 仿真实验。
你必须遵守：
1. 只根据输入证据回答，不编造数字、评分或命令输出。
2. 区分事实、推测、建议和需要学生确认的操作。
3. 评分来自脚本，不来自你。
4. 不执行命令，不声称已经执行命令。
5. 输出中文 JSON，字段为 facts、hypotheses、suggestions、need_student_confirm、source_refs。
"""


class DeepSeekUnavailable(RuntimeError):
    pass


def _redact_text(value: str) -> str:
    text = value
    text = re.sub(r"C:\\Users\\[^\\\s]+(?:\\[^\\\s]+)*", "<local-home>", text, flags=re.IGNORECASE)
    text = re.sub(r"/home/[^/\s]+", "~", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "<redacted-api-key>", text)
    text = re.sub(r"(?i)(DEEPSEEK_API_KEY\s*=\s*)\S+", r"\1<redacted>", text)
    return text


def redact_for_model(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Keep model input useful while removing raw commands and local secrets."""
    data = copy.deepcopy(evidence)
    data.pop("commands", None)
    def walk(value):
        if isinstance(value, str):
            return _redact_text(value)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {key: walk(item) for key, item in value.items()}
        return value
    return walk(data)


def _post_json(url: str, payload: Dict[str, Any], api_key: str, timeout: int = 45) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_connection(settings: Settings, timeout: int = 20) -> Dict[str, Any]:
    if not settings.deepseek_api_key:
        raise DeepSeekUnavailable("DEEPSEEK_API_KEY is not configured")
    base = settings.deepseek_base_url.rstrip("/")
    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": "只回复 OK"}],
        "temperature": 0,
        "max_tokens": 4,
    }
    data = _post_json(base + "/chat/completions", payload, settings.deepseek_api_key, timeout=timeout)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"ok": True, "model": settings.deepseek_model, "response": content}


def explain(settings: Settings, evidence: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    if not settings.deepseek_api_key:
        raise DeepSeekUnavailable("DEEPSEEK_API_KEY is not configured")
    base = settings.deepseek_base_url.rstrip("/")
    url = base + "/chat/completions"
    user = "请解释下面的 Apollo 实验证据。\n" + json.dumps(redact_for_model(evidence), ensure_ascii=False, indent=2)
    if question:
        user += "\n学生问题：" + question
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        data = _post_json(url, payload, settings.deepseek_api_key)
    except urllib.error.HTTPError as exc:
        raise DeepSeekUnavailable(f"DeepSeek HTTP {exc.code}: {exc.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DeepSeekUnavailable(f"DeepSeek 请求失败：{exc}")
    except json.JSONDecodeError as exc:
        raise DeepSeekUnavailable(f"DeepSeek 返回无法解析：{exc}")
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "facts": [],
            "hypotheses": [],
            "suggestions": [content],
            "need_student_confirm": True,
            "source_refs": [],
        }


REPORT_QA_SYSTEM_PROMPT = """你是 Apollo Claw 的实验报告问答助手，服务 Apollo Planning 仿真课程。
只依据提供的当前报告和最近对话回答，不编造数字、分数、命令或执行结果。
回答要适合初学者：先给结论，再列报告证据，最后给可执行的下一步。
如果报告没有相关信息，要明确说“报告中没有足够证据”，并指出还需要查看什么。
评分来自脚本，不来自你；不要说已经执行过命令。
输出中文 JSON，字段为 answer、evidence、next_steps、needs_confirmation。answer 是自然语言回答。"""


def report_context(report: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only report fields useful for a grounded Q&A prompt."""
    keys = ("meta", "record", "metrics", "score", "lab", "verification", "ai", "evidence", "errors", "capability")
    return redact_for_model({key: report.get(key) for key in keys if key in report})


def answer_report_question(
    settings: Settings,
    report: Dict[str, Any],
    question: str,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not settings.deepseek_api_key:
        raise DeepSeekUnavailable("DEEPSEEK_API_KEY is not configured")
    messages: List[Dict[str, str]] = [{"role": "system", "content": REPORT_QA_SYSTEM_PROMPT}]
    for item in (history or [])[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:4000]})
    messages.append({
        "role": "user",
        "content": "当前实验报告（只作为证据）：\n"
        + json.dumps(report_context(report), ensure_ascii=False, indent=2)
        + "\n\n学生问题：" + question,
    })
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    try:
        data = _post_json(settings.deepseek_base_url.rstrip("/") + "/chat/completions", payload, settings.deepseek_api_key)
    except urllib.error.HTTPError as exc:
        raise DeepSeekUnavailable(f"DeepSeek HTTP {exc.code}: {exc.reason}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DeepSeekUnavailable(f"DeepSeek 请求失败：{exc}")
    except json.JSONDecodeError as exc:
        raise DeepSeekUnavailable(f"DeepSeek 返回无法解析：{exc}")
    content = data["choices"][0]["message"]["content"]
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        return {"answer": content, "evidence": [], "next_steps": [], "needs_confirmation": []}
    if not isinstance(result, dict):
        return {"answer": str(result), "evidence": [], "next_steps": [], "needs_confirmation": []}
    result.setdefault("answer", "报告中没有足够证据回答这个问题。")
    result.setdefault("evidence", [])
    result.setdefault("next_steps", [])
    result.setdefault("needs_confirmation", [])
    return result


def fallback_report_answer(report: Dict[str, Any], question: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Answer report questions without a model, using only report fields."""
    meta = report.get("meta", {}) or {}
    record = report.get("record", {}) or {}
    score = report.get("score", {}) or {}
    lab = report.get("lab", {}) or {}
    metrics = report.get("metrics", {}) or {}
    text = (question or "").lower()
    failed = [item for item in (score.get("metrics") or []) if isinstance(item, dict) and item.get("pass") is False]
    failed_names = [str(item.get("name")) for item in failed]
    passed = score.get("passed_metrics") or "—"
    evidence: List[str] = []
    next_steps: List[str] = []

    if record.get("channel_count") == 0 or record.get("status") == "empty":
        return {
            "answer": "当前报告的 record 没有有效 channel，不能据此判断车辆行为。先启动 DreamView/SimControl 场景，再重新录制。",
            "evidence": ["record.channel_count = 0 或 status = empty"],
            "next_steps": ["启动场景和 Planning/Control 模块", "确认 channel 有消息后重新 record"],
            "needs_confirmation": [],
        }

    if any(word in text for word in ("ttc", "行人", "碰撞", "礼让", "没通过", "未通过", "没有完全通过", "失败")):
        answer = f"这份报告场景自评通过 {passed} 项，TTC 仍未通过。"
        for item in failed:
            evidence.append(f"{item.get('name')} 未通过：{item.get('fail')}/{item.get('total')} 帧")
        comparison = lab.get("comparison") or []
        for item in comparison:
            if str(item.get("id", "")).lower() == "ttc":
                evidence.append(f"TTC 基线 {item.get('before')} → 本轮 {item.get('after')}（{item.get('before_detail')} → {item.get('after_detail')}）")
        review = lab.get("human_review") or []
        if review:
            evidence.append(str(review[0]))
        answer += " 当前报告只能证明 TTC 低于阈值，不能仅凭报告判断是合理礼让还是减速过晚；需要结合行人和车辆轨迹确认。"
        next_steps = ["回放 TTC 时间窗", "确认目标对象是否为行人", "检查人行横道前是否提前减速"]
    elif any(word in text for word in ("基线", "对比", "改善", "变化", "优化")):
        comparison = lab.get("comparison") or []
        answer = "这轮相对基线有改善，但还没有完全通过。"
        for item in comparison[:8]:
            evidence.append(f"{item.get('label')}: {item.get('before')} → {item.get('after')}（{item.get('status')}）")
        next_steps = [str(item) for item in (lab.get("next_actions") or [])[:3]]
    elif any(word in text for word in ("分数", "得分", "多少", "评分", "8/9", "通过项")):
        answer = f"报告没有总分，score.value 为空；当前可用的结果是场景自评通过 {passed} 项。"
        evidence.append("score.value = null，is_official = false")
        if failed_names:
            evidence.append("未通过项：" + "、".join(failed_names))
        next_steps = ["以九项指标和证据为准，不要把通过项当成官方总分"]
    else:
        answer = f"当前报告是 {meta.get('scenario') or meta.get('task') or 'Apollo 实验'}，场景自评通过 {passed} 项。"
        if failed_names:
            answer += " 未通过项：" + "、".join(failed_names) + "。"
        for item in failed[:3]:
            evidence.append(f"{item.get('name')} 未通过：{item.get('fail')}/{item.get('total')} 帧")
        for key, label in (("max_lon_accel", "最大纵向加速度"), ("max_jerk", "最大 Jerk"), ("hard_brake", "急刹次数")):
            if metrics.get(key) is not None:
                evidence.append(f"{label}：{metrics.get(key)}")
        next_steps = [str(item) for item in (lab.get("next_actions") or [])[:3]]

    if not evidence:
        evidence.append("报告中未找到与问题直接对应的指标")
    return {
        "answer": answer,
        "evidence": evidence,
        "next_steps": next_steps or ["查看报告中的场景指标和证据链"],
        "needs_confirmation": [],
    }


FALLBACK_RULES = {
    "TTC": "TTC 偏低：这一段是否在跟车/礼让？若是，确认礼让充分；若不是，减速起点要提前。",
    "ReachEnd": "未到终点：确认 record 是否覆盖到车停下的时刻，必要时把录制时长拉长。",
    "SpeedLimit": "超速：检查 profiles/default 下的 speed_limit 配置与地图限速。",
    "AccelerationLimit": "纵向加速度越界：调小 max_acceleration / max_deceleration。",
    "HardBrake": "出现急刹：grep stop_reason 确认触发原因。",
    "CentripetalAccelerationLimit": "过弯横向加速度偏大：降低转弯限速。",
    "Collision": "发生碰撞：检查 obstacle_avoid 安全距离。",
    "TimeLimit": "场景超时：提升平均速度或减少绕行。",
    "OnRoad": "越出道路：检查车道宽度与横向控制参数。",
}


def fallback_explain(evidence: Dict[str, Any]) -> Dict[str, Any]:
    metrics = evidence.get("metrics", {}) or {}
    record = evidence.get("record", {}) or {}
    score = evidence.get("score", {}) or {}
    events = evidence.get("events", {}) or {}
    errors = evidence.get("errors", []) or []
    facts = []
    suggestions = []

    # 新证据结构：九项指标 + 事件窗口
    metric_rows = score.get("metrics") or []
    if metric_rows:
        failed = [m for m in metric_rows if not m.get("pass")]
        facts.append(f"场景判定：{'PASS' if score.get('scenario_pass') else 'FAIL'}，"
                     f"通过 {score.get('passed_metrics', '-')} 项")
        for item in failed[:3]:
            facts.append(f"{item.get('name')} 未通过（{item.get('fail')}/{item.get('total')} 帧）")
            tip = FALLBACK_RULES.get(item.get("name"))
            if tip:
                suggestions.append(tip)
    if "TTC" in events:
        ev = events["TTC"]
        facts.append(f"TTC 低于阈值集中在 t={ev.get('first_t')}–{ev.get('last_t')} s（{ev.get('count')} 帧）")
    if metrics.get("remaining_to_end_m") is not None:
        facts.append(f"录制结束时距终点 {metrics['remaining_to_end_m']} m")

    # 旧证据结构兼容
    if metrics.get("min_ttc") is not None:
        facts.append(f"最低 TTC：{metrics['min_ttc']} 秒")
        if metrics["min_ttc"] < 2.0:
            suggestions.append("检查人行道前速度边界和停止线参数，确认是否需要提前减速。")
    for key, label in (("hard_brake", "急刹次数"), ("max_jerk", "最大 Jerk"), ("max_lon_accel", "最大纵向加速度")):
        if metrics.get(key) is not None:
            facts.append(f"{label}：{round(metrics[key], 2)}")
    if record.get("channel_count") is not None:
        facts.append(f"record 核心 channel 数量：{record['channel_count']}")
    if record.get("channel_count") == 0:
        suggestions.append("先启动 SimControl 场景和 Planning/Control/Routing 模块，确认 channel 有消息后重新录制。")

    refs = ["local-rule-fallback"]
    if errors:
        refs.append("experiment.errors")
    if not facts:
        facts.append("没有可用的指标数据，先确认 record 非空且包含 localization/pose。")
    return {
        "facts": facts,
        "hypotheses": [],
        "suggestions": suggestions,
        "need_student_confirm": bool(suggestions),
        "source_refs": refs,
    }
