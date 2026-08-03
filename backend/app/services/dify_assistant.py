import json
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.models import User


@dataclass
class DifyAssistantConfig:
    enabled: bool
    endpoint: str
    api_key: str
    title: str
    greeting: str
    response_mode: str
    timeout_seconds: int
    app_url: str | None = None
    default_inputs: dict | None = None


class DifyAssistantError(Exception):
    pass


def normalize_dify_chat_endpoint(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlparse(text)
    path = parsed.path.rstrip("/")

    if path.endswith("/chat-messages"):
        endpoint_path = path
    elif "v1" in path.split("/"):
        parts = path.split("/")
        v1_index = parts.index("v1")
        endpoint_path = "/".join(parts[: v1_index + 1]) + "/chat-messages"
    elif path.startswith("/app/"):
        endpoint_path = "/v1/chat-messages"
    elif path in {"", "/"}:
        endpoint_path = "/v1/chat-messages"
    else:
        endpoint_path = f"{path}/chat-messages"

    return urlunparse((parsed.scheme, parsed.netloc, endpoint_path, "", "", ""))


def _parse_default_inputs(raw: str) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def get_dify_assistant_config() -> DifyAssistantConfig:
    settings = get_settings()
    endpoint = normalize_dify_chat_endpoint(settings.dify_assistant_api_base)
    default_inputs = _parse_default_inputs(settings.dify_assistant_default_inputs)
    return DifyAssistantConfig(
        enabled=bool(settings.dify_assistant_enabled and endpoint and settings.dify_assistant_api_key),
        endpoint=endpoint,
        api_key=settings.dify_assistant_api_key,
        title=settings.dify_assistant_title,
        greeting=settings.dify_assistant_greeting,
        response_mode=settings.dify_assistant_response_mode,
        timeout_seconds=settings.dify_assistant_timeout_seconds,
        app_url=settings.dify_assistant_app_url or settings.dify_assistant_api_base or None,
        default_inputs=default_inputs,
    )


def build_user_key(user: User) -> str:
    return user.login_id or user.email or f"oa-user-{user.id}"


def normalize_dify_language(value: str | None) -> str:
    text = (value or "").strip()
    mapping = {
        "ja": "ja-JP",
        "ja-jp": "ja-JP",
        "jp": "ja-JP",
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "cn": "zh-CN",
    }
    return mapping.get(text.lower(), "ja-JP")


def build_inputs(user: User, payload_inputs: dict | None = None) -> dict:
    config = get_dify_assistant_config()
    inputs = dict(config.default_inputs or {})
    if payload_inputs:
        inputs.update({key: value for key, value in payload_inputs.items() if value is not None})
    inputs["language"] = normalize_dify_language(inputs.get("language"))
    inputs.update(
        {
            "oa_user_id": str(user.id),
            "oa_user_role": user.role,
            "oa_user_name": user.full_name,
        }
    )
    return inputs


def extract_sources(metadata: dict | None) -> list[dict]:
    resources = (metadata or {}).get("retriever_resources") or []
    sources = []
    for item in resources:
        if not isinstance(item, dict):
            continue
        title = item.get("document_name") or item.get("title") or item.get("dataset_name") or "source"
        sources.append(
            {
                "title": title,
                "content": item.get("content") or "",
                "score": item.get("score"),
            }
        )
    return sources[:5]


async def send_dify_chat_message(
    *,
    message: str,
    conversation_id: str | None,
    user: User,
    inputs: dict | None = None,
) -> dict:
    config = get_dify_assistant_config()
    if not config.enabled:
        raise DifyAssistantError("AIアシスタントが未設定です。DIFY_ASSISTANT_API_BASE と DIFY_ASSISTANT_API_KEY を確認してください。")

    body = {
        "inputs": build_inputs(user, inputs),
        "query": message,
        "response_mode": config.response_mode or "blocking",
        "user": build_user_key(user),
        "auto_generate_name": True,
    }
    if conversation_id:
        body["conversation_id"] = conversation_id

    try:
        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            response = await client.post(
                config.endpoint,
                headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.RequestError as exc:
        raise DifyAssistantError(f"Dify に接続できません: {exc}") from exc

    if response.status_code >= 400:
        raise DifyAssistantError(f"Dify error {response.status_code}: {response.text[:500]}")

    data = response.json()
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return {
        "answer": data.get("answer") or data.get("message") or "",
        "conversation_id": data.get("conversation_id") or conversation_id,
        "message_id": data.get("message_id") or data.get("id"),
        "task_id": data.get("task_id"),
        "metadata": metadata,
        "sources": extract_sources(metadata),
    }
