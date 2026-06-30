"""Deploy the Invoice SaaS to GitHub + Render — FREE TIER ONLY.

Creates only the two free web services (API + frontend). No Redis, no worker:
the API runs extraction/exports inline (REDIS_URL empty -> inline fallback).

Needs env: GITHUB_TOKEN, RENDER_API_KEY
Optional: GITHUB_REPO_NAME (default invoice-saas)

Cost: $0. Trade-offs: services sleep after 15 min idle (cold start ~30s), no
true background processing.

Tokens are used in-session only; nothing is written to disk.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

UA = "pi-deploy/1.0"
RENDER = "https://api.render.com/v1"
GITHUB = "https://api.github.com"


def http(method, url, headers, body=None, timeout=90):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ct = r.headers.get("content-type", "")
            return r.status, (json.loads(raw) if raw and "json" in ct else raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def gh(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": UA}


def rd(key):
    return {"Authorization": f"Bearer {key}", "Accept": "application/json",
            "Content-Type": "application/json", "User-Agent": UA}


def read_env_secrets():
    """Read backend secrets from local .env (never committed)."""
    secrets = {
        "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_ISSUER", "SUPABASE_JWT_AUDIENCE",
        "DATABASE_URL", "DIRECT_DATABASE_URL",
        "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "PREVIEW_TOKEN_SECRET",
    }
    out = {}
    if os.path.isfile(".env"):
        for line in open(".env", encoding="utf-8"):
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k in secrets and v:
                out[k] = v
    return out


def find_service(key, name):
    st, body = http("GET", f"{RENDER}/services?name={name}&limit=20", rd(key))
    if st == 200 and isinstance(body, list):
        for item in body:
            svc = item.get("service", item)
            if svc.get("name") == name:
                return svc.get("id")
    return None


def create_service(key, payload, name):
    existing = find_service(key, name)
    if existing:
        print(f"[render] {name} exists -> {existing}")
        return existing
    st, body = http("POST", f"{RENDER}/services", rd(key), payload)
    if st in (200, 201):
        sid = body["service"]["id"]
        print(f"[render] created {name} -> {sid}")
        return sid
    print(f"[render] create {name} FAILED: {st} {str(body)[:300]}")
    return None


def main():
    gh_token = os.environ.get("GITHUB_TOKEN")
    render_key = os.environ.get("RENDER_API_KEY")
    if not gh_token or not render_key:
        print("ERROR: set GITHUB_TOKEN and RENDER_API_KEY", file=sys.stderr); sys.exit(2)
    repo_name = os.environ.get("GITHUB_REPO_NAME", "invoice-saas")
    secrets = read_env_secrets()
    if "DATABASE_URL" not in secrets:
        print("ERROR: .env missing DATABASE_URL"); sys.exit(1)

    # 1) GitHub — create private repo + push
    st, me = http("GET", f"{GITHUB}/user", gh(gh_token))
    if st != 200:
        print("GitHub auth failed:", st, me); sys.exit(1)
    owner = me["login"]
    print(f"[github] authenticated as {owner}")
    st, body = http("GET", f"{GITHUB}/repos/{owner}/{repo_name}", gh(gh_token))
    if st != 200:
        st, body = http("POST", f"{GITHUB}/user/repos", gh(gh_token),
                        {"name": repo_name, "private": True, "auto_init": False})
        if st not in (200, 201):
            print("[github] create repo failed:", st, body); sys.exit(1)
        print(f"[github] created private repo {owner}/{repo_name}")
    else:
        print(f"[github] repo {owner}/{repo_name} exists")
    remote = f"https://{owner}:{gh_token}@github.com/{owner}/{repo_name}.git"
    subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote], check=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD:main", "--force"], check=True,
                   env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    repo_url = f"https://github.com/{owner}/{repo_name}"
    print(f"[github] pushed -> {repo_url}")

    api_url = "https://invoice-saas-api.onrender.com"
    web_url = "https://invoice-saas-web.onrender.com"
    secrets["FRONTEND_BASE_URL"] = web_url
    secrets["BACKEND_BASE_URL"] = api_url

    # 2) API web service (free) — inline fallback, no Redis
    api_envs = [{"key": k, "value": v} for k, v in secrets.items()]
    api_envs += [
        {"key": "REDIS_URL", "value": ""},                  # inline fallback
        {"key": "APP_ENV", "value": "production"},
        {"key": "EXTRACTION_PROVIDER", "value": "mock"},    # flip to "textract" later
        {"key": "STORAGE_BACKEND", "value": "supabase"},
        {"key": "SUPABASE_STORAGE_ORIGINALS_BUCKET", "value": "invoice-originals"},
        {"key": "SUPABASE_STORAGE_EXPORTS_BUCKET", "value": "invoice-exports"},
        {"key": "SUPABASE_STORAGE_OCR_RAW_BUCKET", "value": "ocr-raw-results"},
        {"key": "WEB_CONCURRENCY", "value": "1"},
    ]
    create_service(render_key, {
        "type": "web", "name": "invoice-saas-api", "region": "ohio",
        "repoUrl": repo_url, "branch": "main",
        "dockerfilePath": "./backend/Dockerfile", "dockerContext": "./backend",
        "plan": "free", "healthCheckPath": "/api/health",
        "envVars": api_envs,
    }, "invoice-saas-api")

    # 3) Frontend web service (free)
    create_service(render_key, {
        "type": "web", "name": "invoice-saas-web", "region": "ohio",
        "repoUrl": repo_url, "branch": "main",
        "dockerfilePath": "./frontend/Dockerfile", "dockerContext": "./frontend",
        "plan": "free", "envVars": [
            {"key": "NEXT_PUBLIC_SUPABASE_URL", "value": secrets.get("SUPABASE_URL", "")},
            {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY", "value": secrets.get("SUPABASE_ANON_KEY", "")},
            {"key": "NEXT_PUBLIC_BACKEND_BASE_URL", "value": api_url},
            {"key": "BACKEND_BASE_URL", "value": api_url},
            {"key": "NODE_ENV", "value": "production"},
        ],
    }, "invoice-saas-web")

    # 4) Wait for API health (free tier builds + boots can take a few minutes)
    print(f"[render] waiting for {api_url}/api/health (this can take 3-8 min on free tier)...")
    for i in range(80):
        st, body = http("GET", f"{api_url}/api/health", {"User-Agent": UA}, timeout=20)
        if st == 200:
            print(f"[render] API LIVE: {body}")
            print(f"\n✅ Frontend: {web_url}\n✅ API:      {api_url}")
            print("\nFree tier: services sleep after 15 min idle (first hit ~30s cold start).")
            return
        if i % 4 == 0:
            print(f"   ...still waiting ({i*15}s elapsed)")
        time.sleep(15)
    print("[render] API not healthy yet — check Render dashboard logs.")


if __name__ == "__main__":
    main()