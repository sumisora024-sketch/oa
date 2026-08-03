from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user
from app.models import User
from app.schemas import AiAssistantChatIn, AiAssistantChatOut, AiAssistantConfigOut
from app.services.dify_assistant import DifyAssistantError, get_dify_assistant_config, send_dify_chat_message

router = APIRouter(prefix="/ai-assistant", tags=["ai_assistant"])


@router.get("/config", response_model=AiAssistantConfigOut)
def assistant_config(user: User = Depends(get_current_user)):
    config = get_dify_assistant_config()
    return {
        "enabled": config.enabled,
        "provider": "dify",
        "title": config.title,
        "greeting": config.greeting,
        "app_url": config.app_url,
        "supports_conversation": True,
    }


@router.post("/chat", response_model=AiAssistantChatOut)
async def assistant_chat(payload: AiAssistantChatIn, user: User = Depends(get_current_user)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message is required")
    try:
        result = await send_dify_chat_message(
            message=message,
            conversation_id=payload.conversation_id,
            user=user,
            inputs=payload.inputs,
        )
    except DifyAssistantError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"provider": "dify", **result}
