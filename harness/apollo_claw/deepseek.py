"""DeepSeek adapter using the OpenAI-compatible chat completions API."""
from __future__ import annotations

import copy
import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

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
    data = _post_json(url, payload, settings.deepseek_api_key)
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


def fallback_explain(evidence: Dict[str, Any]) -> Dict[str, Any]:
    metrics = evidence.get("metrics", {}) or {}
    record = evidence.get("record", {}) or {}
    errors = evidence.get("errors", []) or []
    facts = []
    suggestions = []
    if metrics.get("min_ttc") is not None:
        facts.append(f"最低 TTC：{metrics['min_ttc']} 秒")
    if metrics.get("hard_brake") is not None:
        facts.append(f"急刹次数：{metrics['hard_brake']}")
    if metrics.get("max_jerk") is not None:
        facts.append(f"最大 Jerk：{metrics['max_jerk']}")
    if record.get("channel_count") is not None:
        facts.append(f"record 核心 channel 数量：{record['channel_count']}")
    if record.get("status"):
        facts.append(f"record 状态：{record['status']}")
    if record.get("channel_count") == 0:
        suggestions.append("先启动 SimControl 场景和 Planning/Control/Routing 模块，确认 channel 有消息后重新录制。")
    if metrics.get("min_ttc") is not None and metrics["min_ttc"] < 2.0:
        suggestions.append("检查人行道前速度边界和停止线参数，确认是否需要提前减速。")
    refs = ["local-rule-fallback"]
    if errors:
        refs.append("experiment.errors")
    return {
        "facts": facts,
        "hypotheses": [],
        "suggestions": suggestions,
        "need_student_confirm": True,
        "source_refs": refs,
    }
