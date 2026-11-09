"""Agent 루프: Claude가 도구를 고르고 → 실행 → 결과를 보고 다시 판단하는 과정을 끝날 때까지 반복한다.

화면(웹)에는 진행 상황을 이벤트로 흘려 보낸다.
  {"type": "text", "text": "..."}                  답변 글자 (스트리밍)
  {"type": "tool_call", "id", "name", "input"}      도구 호출 시작
  {"type": "tool_result", "id", "name", "is_error", "result"}
  {"type": "done", "stop_reason": "..."}
  {"type": "error", "message": "..."}
"""
import asyncio
import base64
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator

import anthropic
from dotenv import load_dotenv

from app.agent import prompts, tools
from app.data.db import ROOT

load_dotenv(ROOT / ".env")
log = logging.getLogger(__name__)

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("CLAUDE_EFFORT", "medium")
MAX_TURNS = 12          # 한 질문에 도구를 오가는 최대 횟수
MAX_JSON_RETRIES = 2
# 안전 분류기가 요청을 거절하면 서버가 다른 모델로 자동 재시도 (Claude API 전용, 지원 모델만)
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
# 비용 계산용 단가 (USD / 100만 토큰: 입력, 출력, 캐시 읽기, 캐시 쓰기). 2026-10 기준, 바뀔 수 있음
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20, 2.5),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}


def cost_usd(model: str, u) -> float:
    p = PRICES.get(model)
    if not p:
        return 0.0
    return (u.input_tokens * p[0] + u.output_tokens * p[1]
            + (u.cache_read_input_tokens or 0) * p[2] + (u.cache_creation_input_tokens or 0) * p[3]) / 1e6
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
UPLOADS = ROOT / "data/output/uploads"


@dataclass
class Session:
    mode: str = ""                       # owner | tourist | ""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    user_turn: int = 0                   # 사용자 메시지 차례 번호 (승인 도구가 같은 차례 자기승인을 막는 데 사용)
    messages: list = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def user_content(text: str, image: bytes | None = None, media_type: str = "") -> list[dict]:
    """사용자 입력 → content 블록. 메뉴판 사진이 있으면 글자보다 앞에 넣는다."""
    content = []
    if image:
        if media_type not in IMAGE_TYPES:
            raise ValueError(f"지원하지 않는 이미지 형식: {media_type}")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(image).decode()},
        })
    content.append({"type": "text", "text": text or "이 사진을 봐 주세요."})
    return content


async def run(session: Session, text: str, image: bytes | None = None, media_type: str = "",
              model: str | None = None) -> AsyncIterator[dict]:
    """사용자 메시지 하나를 처리하며 이벤트를 내보낸다. session.messages는 끝에 덧붙이기만 한다."""
    session.user_turn += 1
    ctx = {"session_id": session.session_id, "user_turn": session.user_turn}
    if image:
        # 사장님 사진을 저장해 두고 ID를 알려 준다 → 카드에 실제 사진으로 넣을 수 있음 (save_draft의 photo)
        ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(media_type, "jpg")
        name = f"{session.session_id[:8]}_{session.user_turn}.{ext}"
        UPLOADS.mkdir(parents=True, exist_ok=True)
        (UPLOADS / name).write_bytes(image)
        text = f"{text}\n\n[첨부 사진 ID: {name}]"
    session.messages.append({"role": "user", "content": user_content(text, image, media_type)})
    if len(session.messages) == 1 and session.mode in prompts.MODE_HINT:
        # 화면에서 알려준 사용자 유형은 대화 중 시스템 메시지로 전달 (첫 사용자 메시지 바로 뒤)
        session.messages.append({"role": "system", "content": prompts.MODE_HINT[session.mode]})

    model = model or MODEL
    extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    json_retries = 0
    for _ in range(MAX_TURNS):
        try:
            async with client().beta.messages.stream(
                model=model,
                max_tokens=16000,
                system=[{"type": "text", "text": prompts.SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=tools.TOOL_SPECS,
                messages=session.messages,
                output_config={"effort": EFFORT},
                **extra,
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield {"type": "text", "text": event.text}
                response = await stream.get_final_message()
            json_retries = 0
        except ValueError:
            # 도구 입력 JSON을 SDK가 아예 해석하지 못한 경우: 같은 턴을 다시 요청 (횟수 제한)
            json_retries += 1
            if json_retries > MAX_JSON_RETRIES:
                yield {"type": "error", "message": "도구 입력을 해석하지 못했습니다. 다시 질문해 주세요."}
                return
            continue
        except anthropic.AuthenticationError:
            yield {"type": "error", "message": "Claude API 키가 없거나 잘못됐습니다. .env 의 ANTHROPIC_API_KEY 를 확인하세요."}
            return
        except anthropic.RateLimitError:
            yield {"type": "error", "message": "요청이 많아 잠시 막혔습니다. 조금 뒤 다시 시도해 주세요."}
            return
        except anthropic.APIStatusError as e:
            yield {"type": "error", "message": f"Claude API 오류 ({e.status_code}): {e.message}"}
            return
        except anthropic.APIConnectionError:
            yield {"type": "error", "message": "인터넷 연결을 확인해 주세요 (Claude API 접속 실패)."}
            return
        except Exception as e:
            if "authentication" in str(e).lower():
                msg = "Claude API 키가 설정되지 않았습니다. .env 에 ANTHROPIC_API_KEY 를 넣고 다시 실행해 주세요."
            else:
                log.exception("agent loop failed")
                msg = f"처리 중 오류가 났습니다 ({type(e).__name__})."
            yield {"type": "error", "message": msg}
            return

        # 응답 전체(생각 블록·폴백 블록 포함)를 그대로 덧붙여야 다음 요청이 유효하다
        session.messages.append({"role": "assistant", "content": response.content})
        u = response.usage
        yield {"type": "usage", "model": model, "input": u.input_tokens, "output": u.output_tokens,
               "cache_read": u.cache_read_input_tokens or 0, "cache_write": u.cache_creation_input_tokens or 0,
               "usd": round(cost_usd(model, u), 5)}

        if response.stop_reason == "pause_turn":
            continue
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason == "refusal" or not tool_uses:
            yield {"type": "done", "stop_reason": response.stop_reason}
            return
        if response.stop_reason == "max_tokens":
            yield {"type": "error", "message": "답변이 너무 길어 중간에 끊겼습니다. 질문을 나눠 주세요."}
            # 잘린 tool_use에는 결과를 줄 수 없으므로 오류 결과로 짝을 맞춘다
            session.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "is_error": True, "content": "입력이 잘려 실행하지 않음"}
                for b in tool_uses
            ]})
            return

        # 도구 실행 (여러 개면 동시에), 결과는 한 메시지에 모아 돌려준다
        for b in tool_uses:
            yield {"type": "tool_call", "id": b.id, "name": b.name, "input": b.input}
        outs = await asyncio.gather(*(asyncio.to_thread(tools.run, b.name, b.input, ctx) for b in tool_uses))
        results = []
        for b, (out, is_error) in zip(tool_uses, outs):
            yield {"type": "tool_result", "id": b.id, "name": b.name, "is_error": is_error, "result": out}
            results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": is_error, "content": tools.to_content(out)})
        session.messages.append({"role": "user", "content": results})

    yield {"type": "error", "message": f"도구를 {MAX_TURNS}번 넘게 오갔지만 답을 정리하지 못했습니다."}
