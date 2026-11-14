"""OpenAI-compatible chat adapter. Credentials stay in the backend."""
from __future__ import annotations

import asyncio
import math
import os
from pathlib import Path
from threading import BoundedSemaphore, Lock

import httpx
from dotenv import load_dotenv

from .errors import AgentCallFailed
from .sandbox import GOAL_NAMES, LOCATIONS, ROLE_NAMES

_env_lock = Lock()
_slots: BoundedSemaphore | None = None
NPC_PERSONA = (Path(__file__).resolve().parents[1] / "prompts" / "npc_persona.txt").read_text(encoding="utf-8")


def _configuration():
    global _slots
    with _env_lock:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        url = os.getenv("LLM_BASE_URL", "").rstrip("/")
        key = os.getenv("LLM_API_KEY", "")
        model = os.getenv("LLM_MODEL", "")
        try:
            address = httpx.URL(url)
            timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "8"))
            concurrency = int(os.getenv("LLM_MAX_CONCURRENCY", "2"))
            if address.scheme != "https" or not address.host or address.userinfo or address.query or address.fragment:
                raise ValueError
            if not math.isfinite(timeout) or timeout <= 0 or concurrency < 1:
                raise ValueError
        except (ValueError, httpx.InvalidURL):
            raise AgentCallFailed("模型配置无效，请检查 HTTPS 地址、超时与并发设置") from None
        if not key or not model:
            raise AgentCallFailed("请在本地 .env 配置 LLM_API_KEY 和 LLM_MODEL")
        if _slots is None:
            _slots = BoundedSemaphore(concurrency)
        return url, key, model, timeout, _slots


async def complete(messages: list[dict[str, str]], *, max_tokens: int = 1800) -> tuple[str, str]:
    url, key, model, timeout, slots = _configuration()
    if not slots.acquire(blocking=False):
        raise AgentCallFailed("模型并发已满，请稍后重试")
    try:
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if any("JSON Schema:" in message.get("content", "") for message in messages if message.get("role") == "system"):
            payload["response_format"] = {"type": "json_object"}
        if httpx.URL(url).host == "api.deepseek.com":
            payload["thinking"] = {"type": "disabled"}
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                reported_model = data.get("model") or model
                if not isinstance(content, str) or not content.strip() or not isinstance(reported_model, str):
                    raise ValueError
                if key in content or key in reported_model:
                    raise AgentCallFailed("模型响应包含敏感配置，已拒绝")
                return content.strip(), reported_model
    except httpx.HTTPStatusError as exc:
        raise AgentCallFailed(f"模型服务返回 HTTP {exc.response.status_code}") from None
    except (TimeoutError, httpx.TimeoutException):
        raise AgentCallFailed("模型调用超时") from None
    except (httpx.RequestError, KeyError, IndexError, ValueError, TypeError):
        raise AgentCallFailed("模型连接失败或响应格式无效") from None
    finally:
        slots.release()


def ask_live(npc, question: str) -> tuple[str, str]:
    if npc.hp <= 0:
        raise AgentCallFailed("该 NPC 已死亡")
    memories = "\n".join(
        f"- [{m.source_type}，来源 {','.join(m.source_event_ids)}] {m.text}"
        for m in npc.memories[-8:]
    )
    return asyncio.run(complete([
        {"role": "system", "content": NPC_PERSONA + "\n这里是终端对话，只输出角色当前说的话。"},
        {"role": "user", "content": (
            f"角色资料：{npc.name}，职业 {ROLE_NAMES[npc.role]}，住处 {npc.residence}，"
            f"当前位置 {LOCATIONS[npc.location][0]}，当前目标 {GOAL_NAMES.get(npc.goal, '回家')}，"
            f"性格 {npc.personality}\n"
            f"个人记忆：\n{memories or '无'}\n玩家问题：{question[:500]}"
        )},
    ], max_tokens=220))
