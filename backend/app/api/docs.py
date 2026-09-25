from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["docs"])

GAME_RULE_MD = (Path(__file__).parent.parent / "docs" / "game_rule.md").read_text(encoding="utf-8")


@router.get("/game_rule.md", response_class=PlainTextResponse)
async def game_rule() -> PlainTextResponse:
    """对战规则与 agent 接入协议（固定内容的 Markdown 文档）。"""
    return PlainTextResponse(GAME_RULE_MD, media_type="text/markdown; charset=utf-8")
