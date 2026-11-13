"""대회 최종 결과물 zip 만들기.

    python scripts/make_submission.py

결과 (`제출/`, 저장소에는 올리지 않음):
    제출/제주동네가게_AI_Agent_최종결과물.zip          처리된 DB 포함 (심사위원이 바로 실행)
    제출/제주동네가게_AI_Agent_최종결과물_DB제외.zip   DB 제외 (데이터는 허브에서 받아 다시 만들어야 함)
    제출/최종결과물/제주동네가게_AI_Agent/            zip 내용 (확인용)
    제출/기획서/                                    기획서 PDF를 두는 곳 (직접 작성)

- 코드·문서는 git이 추적하는 파일만 넣는다 → .env, 허브 원본(data/raw)은 들어가지 않는다.
- 평가용 키: `제출/평가용.env`가 있으면 허용된 변수(AI API·모델 설정)만 골라 zip 안 `.env`로 넣는다.
  대회 규칙상 제출 가능한 키는 '외부 AI API 평가용 키'뿐이다. 네이버·허브 키는 넣지 않는다.
- 마지막에 로컬 .env의 실제 키 값이 zip 어디에도 없는지 검사한다 (평가용 .env 제외).
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "제출"
NAME = "제주동네가게_AI_Agent"
STAGE = OUT / "최종결과물" / NAME

# 평가용 .env에 넣어도 되는 변수 (외부 AI API 키 + 모델·한도 설정)
EVAL_ENV_ALLOWED = {
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "CLAUDE_MODEL", "CLAUDE_EFFORT", "CLAUDE_MODEL_OWNER", "CLAUDE_MODEL_TOURIST",
    "GEMINI_IMAGE_MODEL", "GEMINI_DAILY_LIMIT", "DEMO_DAILY_LIMIT", "DATA_MODE",
}
# 저장소에는 있지만 제출물에는 필요 없는 것
SKIP_TRACKED = {".gcloudignore", "asdf.py"}
# 실행에 필요한 처리 데이터 (저장소 제외 → 따로 넣음)
PROCESSED = ["demand_model.joblib", "demand_metrics.json", "review_sentiment_meta.json"]
# 사람 검증 표본 (허브 데이터 일부 포함 → 공개 저장소 제외, 심사용 zip에만)
EXTRA = sorted((ROOT / "docs" / "검증").glob("*.xlsx"))


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    files = [f for f in out.decode("utf-8").split("\0") if f]
    untracked = subprocess.run(["git", "ls-files", "-z", "--others", "--exclude-standard"],
                               cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    if untracked.strip("\0"):
        print("  주의: 커밋 안 된 새 파일은 넣지 않습니다:", [f for f in untracked.split("\0") if f][:10])
    return [f for f in files if f not in SKIP_TRACKED and (ROOT / f).is_file()]


def read_env(path: Path) -> dict[str, str]:
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def copy_db(dst: Path) -> None:
    """WAL에 남은 내용까지 합쳐 깨끗한 한 파일로 복사 (작업 중 초안·신고 기록은 비움)."""
    src = sqlite3.connect(ROOT / "data" / "processed" / "jeju.db")
    out = sqlite3.connect(dst)
    src.backup(out)
    src.close()
    for t in ("drafts", "store_reports"):
        out.execute(f"DELETE FROM {t}")
    out.commit()
    out.execute("VACUUM")
    out.close()


def stage(with_db: bool) -> Path:
    # 매번 새 임시 폴더에 만든다 (편집기·탐색기가 잡고 있는 이전 폴더를 지우다 실패하지 않게)
    build = Path(tempfile.mkdtemp(prefix="build_", dir=OUT))
    STAGE = build / NAME
    for f in tracked_files():
        d = STAGE / f
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, d)
    for p in EXTRA:
        d = STAGE / p.relative_to(ROOT)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d)
    proc = STAGE / "data" / "processed"
    proc.mkdir(parents=True, exist_ok=True)
    for name in PROCESSED:
        shutil.copy2(ROOT / "data" / "processed" / name, proc / name)
    if with_db:
        copy_db(proc / "jeju.db")
    for sub in ("output/cards", "output/uploads", "output/backgrounds"):
        (STAGE / "data" / sub).mkdir(parents=True, exist_ok=True)

    eval_env = read_env(OUT / "평가용.env")
    if eval_env:
        bad = sorted(set(eval_env) - EVAL_ENV_ALLOWED)
        if bad:
            print("  평가용.env에서 제출 불가 변수는 뺐습니다:", bad)
        lines = ["# 평가용 키 (사용 한도 설정, 평가 기간 종료 후 폐기). 발급 방법: docs/API키_발급.md"]
        lines += [f"{k}={v}" for k, v in eval_env.items() if k in EVAL_ENV_ALLOWED]
        (STAGE / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return STAGE


def secret_check(stage_dir: Path) -> None:
    """로컬 .env의 실제 키 값이 평가용 .env 밖 어디에도 없는지 확인."""
    secrets = {k: v for k, v in read_env(ROOT / ".env").items() if len(v) >= 8 and not v.startswith("claude-")}
    allowed_vals = set(read_env(stage_dir / ".env").values())
    hits = []
    for p in stage_dir.rglob("*"):
        if not p.is_file() or p.name == ".env" or p.suffix in (".db", ".joblib", ".png", ".jpg", ".xlsx"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for k, v in secrets.items():
            if v in text and v not in allowed_vals:
                hits.append(f"{p.relative_to(stage_dir)}: {k}")
    eval_env = read_env(stage_dir / ".env")
    leaked = [k for k in eval_env if k not in EVAL_ENV_ALLOWED]
    if hits or leaked:
        sys.exit(f"키가 섞여 들어갔습니다. zip을 만들지 않습니다: {hits + leaked}")


def make_zip(stage_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(stage_dir.rglob("*")):
            arc = Path(NAME) / p.relative_to(stage_dir)
            if p.is_dir():
                if not any(p.iterdir()):
                    z.writestr(str(arc).replace("\\", "/") + "/", "")
                continue
            z.write(p, arc)
    print(f"  {zip_path.name}: {zip_path.stat().st_size / 1e6:.1f}MB")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "기획서").mkdir(exist_ok=True)
    print("평가용 키:", "제출/평가용.env 사용" if (OUT / "평가용.env").exists()
          else "없음 (zip 안 .env 없음 → 심사위원이 키를 넣어야 AI 대화 가능)")
    for with_db, zname in ((False, f"{NAME}_최종결과물_DB제외.zip"), (True, f"{NAME}_최종결과물.zip")):
        d = stage(with_db)
        secret_check(d)
        make_zip(d, OUT / zname)
    # 마지막(DB 포함) 내용을 확인용 폴더로. 이전 폴더를 못 지우면 그대로 두고 알린다
    shutil.rmtree(STAGE, ignore_errors=True)
    for b in OUT.glob("build_*"):
        if b != d.parent:
            shutil.rmtree(b, ignore_errors=True)
    if STAGE.exists():
        print("확인용 폴더를 바꾸지 못했습니다 (열려 있음). 최신 내용:", d)
    else:
        STAGE.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(STAGE))
        shutil.rmtree(d.parent, ignore_errors=True)
        print("확인용 폴더:", STAGE)


if __name__ == "__main__":
    main()
