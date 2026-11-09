"""터미널에서 Agent와 대화한다 (화면 없이 시연·테스트용).

사용법:
  python scripts/chat.py                 # 유형은 Agent가 판단
  python scripts/chat.py --mode owner    # 사장님
  python scripts/chat.py --mode tourist  # 관광객
  python scripts/chat.py --mode owner --say "자매국수 사장인데 손님들이 뭐래?"   # 한 번 묻고 끝

대화 중 명령:
  /img 경로 [질문]   사진(메뉴판 등)을 함께 보냄
  /trace            도구 결과 전체 보기 켜기/끄기
  /quit             종료
"""
import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stdin.reconfigure(encoding="utf-8")

from app.agent import loop  # noqa: E402

DIM, BOLD, CYAN, RED, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[31m", "\033[0m"


def short(obj, n=160) -> str:
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


async def ask(session: loop.Session, text: str, image: bytes | None, media_type: str, trace: bool):
    async for ev in loop.run(session, text, image, media_type):
        t = ev["type"]
        if t == "text":
            print(ev["text"], end="", flush=True)
        elif t == "tool_call":
            print(f"\n{CYAN}▶ {ev['name']}{RESET} {DIM}{short(ev['input'])}{RESET}")
        elif t == "tool_result":
            mark = f"{RED}✗{RESET}" if ev["is_error"] else "✓"
            body = json.dumps(ev["result"], ensure_ascii=False, indent=1, default=str) if trace else short(ev["result"])
            print(f"  {mark} {DIM}{body}{RESET}")
        elif t == "error":
            print(f"\n{RED}[오류] {ev['message']}{RESET}")
        elif t == "done":
            print()


async def repl(session: loop.Session, trace: bool):
    print(f"{BOLD}제주 동네가게 도우미{RESET} ({loop.MODEL}) — /img 경로, /trace, /quit")
    while True:
        try:
            line = (await asyncio.to_thread(input, f"\n{BOLD}나>{RESET} ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/trace":
            trace = not trace
            print(f"trace {'켜짐' if trace else '꺼짐'}")
            continue
        img, mt = None, ""
        if line.startswith("/img "):
            parts = line[5:].strip().split(maxsplit=1)
            try:
                img, mt = load(parts[0])
            except OSError as e:
                print(f"{RED}사진을 열 수 없음: {e}{RESET}")
                continue
            line = parts[1] if len(parts) > 1 else "이 사진으로 메뉴판 만들어 주세요."
        print(f"{BOLD}도우미>{RESET} ", end="")
        await ask(session, line, img, mt, trace)


def load(path):
    p = Path(path)
    return p.read_bytes(), mimetypes.guess_type(p.name)[0] or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["owner", "tourist"], default="")
    ap.add_argument("--say", help="한 번만 묻고 종료")
    ap.add_argument("--image", help="--say 와 함께 보낼 사진")
    ap.add_argument("--trace", action="store_true")
    a = ap.parse_args()

    session = loop.Session(mode=a.mode)
    if a.say:
        img, mt = load(a.image) if a.image else (None, "")
        asyncio.run(ask(session, a.say, img, mt, a.trace))
    else:
        asyncio.run(repl(session, a.trace))


if __name__ == "__main__":
    main()
