"""화면(app/static)을 Firebase Hosting(https://jeju-local-agent.web.app)에 올린다.

화면만 Firebase에 두고, API는 Cloud Run 서버를 부른다 (config.js의 window.JEJU_API).
Firebase CLI 로그인 없이 gcloud 로그인 토큰으로 Hosting REST API를 쓴다.

사용법:
  python scripts/deploy_firebase.py
  python scripts/deploy_firebase.py --api https://<cloud-run-주소> --site jeju-local-agent --project jeju-36607
"""
import argparse
import gzip
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "app" / "static"
HOST = "https://firebasehosting.googleapis.com/v1beta1"
sys.stdout.reconfigure(encoding="utf-8")


def token() -> str:
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    return subprocess.run([exe, "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://je-ju-426798142372.asia-northeast3.run.app")
    ap.add_argument("--site", default="jeju-local-agent")
    ap.add_argument("--project", default="jeju-36607")
    a = ap.parse_args()

    h = {"Authorization": f"Bearer {token()}", "x-goog-user-project": a.project}
    files = {}
    for p in sorted(STATIC.iterdir()):
        if p.is_file():
            data = p.read_bytes()
            if p.name == "config.js":  # 화면이 부를 API 서버 주소
                data = f'window.JEJU_API = "{a.api}";\n'.encode()
            gz = gzip.compress(data, mtime=0)
            files["/" + p.name] = (hashlib.sha256(gz).hexdigest(), gz)

    config = {"headers": [{"glob": "**/*.@(html|js|css|webmanifest)", "headers": {"Cache-Control": "no-cache"}}],
              "rewrites": [{"glob": "**", "path": "/index.html"}]}
    v = requests.post(f"{HOST}/sites/{a.site}/versions", headers=h, json={"config": config}, timeout=30)
    v.raise_for_status()
    version = v.json()["name"]

    pop = requests.post(f"{HOST}/{version}:populateFiles", headers=h,
                        json={"files": {k: hv for k, (hv, _) in files.items()}}, timeout=30)
    pop.raise_for_status()
    pj = pop.json()
    need = set(pj.get("uploadRequiredHashes", []))
    for name, (hv, gz) in files.items():
        if hv in need:
            r = requests.post(f"{pj['uploadUrl']}/{hv}", headers={**h, "Content-Type": "application/octet-stream"}, data=gz, timeout=60)
            r.raise_for_status()
            print("올림", name)

    requests.patch(f"{HOST}/{version}?update_mask=status", headers=h, json={"status": "FINALIZED"}, timeout=30).raise_for_status()
    rel = requests.post(f"{HOST}/sites/{a.site}/releases?versionName={version}", headers=h, json={}, timeout=30)
    rel.raise_for_status()
    print(f"배포 완료: https://{a.site}.web.app  (API: {a.api})")


if __name__ == "__main__":
    main()
