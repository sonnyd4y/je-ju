"""data/manifest.csv 기준으로 data/raw/<id>/ 에 파일이 들어왔는지 확인한다.

사용법: python scripts/check_data.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")


def main():
    rows = list(csv.DictReader(open(ROOT / "data/manifest.csv", encoding="utf-8-sig")))
    ready = 0
    print(f"{'상태':<4} {'ID':>5}  {'우선순위':<8} 데이터명")
    for r in rows:
        files = [p for p in (ROOT / r["저장위치"]).glob("*") if p.is_file() and p.name != ".gitkeep"]
        ok = bool(files)
        ready += ok
        mark = "OK" if ok else "--"
        extra = f"  ({len(files)}개 파일)" if ok else f"  ← {r['상세페이지']}"
        print(f"{mark:<4} {r['id']:>5}  {r['우선순위']:<8} {r['데이터명']}{extra}")
    print(f"\n준비 완료 {ready}/{len(rows)}")
    missing_p1 = [r["id"] for r in rows if r["우선순위"].startswith("P1")
                  and not any(p.name != ".gitkeep" for p in (ROOT / r["저장위치"]).glob("*"))]
    if missing_p1:
        print("P1(우선) 미준비:", ", ".join(missing_p1))


if __name__ == "__main__":
    main()
