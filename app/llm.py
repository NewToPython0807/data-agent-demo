"""云端大模型调用（T15 / V3-T10）。

调用 DeepSeek（OpenAI 兼容接口）把中文问题转换为 SQL；
V3 增加“先计划、后 SQL”的生成入口（原文返回，解析见 app.plan）。
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.prompt import build_correction_prompt, build_plan_prompt, build_prompt


class LLMError(Exception):
    """大模型调用异常（可读提示）。"""


def _extract_sql(text: str) -> str:
    """从模型输出中提取 SQL：去掉 ```sql ... ``` 代码围栏与首尾空白。"""
    text = (text or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _chat(prompt: str) -> str:
    """调用模型，返回文本内容（失败抛 LLMError）。"""
    if not settings.deepseek_api_key:
        raise LLMError("未配置 DEEPSEEK_API_KEY，请在 .env 中设置")

    payload = {
        "model": settings.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "stream": False,
    }
    url = settings.deepseek_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    last_err = "调用模型失败"
    for _ in range(2):  # 共 2 次尝试（首次 + 重试 1 次）
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.llm_timeout_seconds)
        except httpx.HTTPError as exc:
            last_err = f"网络请求失败：{exc}"
            continue
        if resp.status_code != 200:
            last_err = f"模型接口返回 {resp.status_code}：{resp.text[:200]}"
            continue
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError) as exc:
            last_err = f"解析模型返回失败：{exc}"
            continue
        if not (content or "").strip():
            last_err = "模型返回内容为空"
            continue
        return content

    raise LLMError(last_err)


def generate_sql(question: str, context: list[dict] | None = None) -> str:
    """调用 LLM 生成 SQL，返回 SQL 文本（失败抛 LLMError）。"""
    content = _chat(build_prompt(question, context))
    sql = _extract_sql(content)
    if not sql:
        raise LLMError("模型未返回 SQL 内容")
    return sql


def generate_plan_text(question: str, context: list[dict] | None = None) -> str:
    """调用 LLM 生成“查询计划 + SQL”原文（解析见 app.plan）。"""
    return _chat(build_plan_prompt(question, context))


def generate_correction(question: str, sql: str, error: str) -> str:
    """调用 LLM 修正执行失败的 SQL（返回 SQL 文本）。"""
    content = _chat(build_correction_prompt(question, sql, error))
    corrected = _extract_sql(content)
    if not corrected:
        raise LLMError("模型未返回修正后的 SQL")
    return corrected
