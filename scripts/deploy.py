"""Deploy the Invoice SaaS — FREE TIER, delete-and-recreate.

Pushes local code to a new private GitHub repo, deletes any suspended existing
Render services with our names, then creates two free web services (API +
frontend) with correct Dockerfile paths and env vars, and polls until the API
health endpoint is live.

Env: GITHUB_TOKEN, RENDER_API_KEY, RENDER_OWNER_ID (optional)
Cost: $0.
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


def gh(t): return {"Authorization": f"Bearer {t}", "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": UA}
def rd(k): return {"Authorization": f"Bearer {k}", "Accept": "application/json",
                   "Content-Type": "application/json", "User-Agent": UA}


def read_env_secrets():
    keep = {"SUPABASE_URL","SUPABASE_ANON_KEY","SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_JWT_ISSUER","SUPABASE_JWT_AUDIENCE","DATABASE_URL",
            "DIRECT_DATABASE_URL","AWS_REGION","AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY","PREVIEW_TOKEN_SECRET"}
    out = {}
    if os.path.isfile(".env"):
        for line in open(".env", encoding="utf-8"):
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s: continue
            k, v = s.split("=", 1)
            if k in keep and v: out[k] = v
    return out


def list_services(key):
    st, body = http("GET", f"{RENDER}/services?limit=50", rd(key))
    out = {}
    if st == 200 and isinstance(body, list):
        for item in body:
            svc = item.get("service", item)
            out[svc.get("name")] = svc.get("id")
    return out


def delete_service(key, sid):
    st, body = http("DELETE", f"{RENDER}/services/{sid}", rd(key))
    return st in (200, 202, 204)


def create(key, payload):
    return http("POST", f"{RENDER}/services", rd(key), payload)


def main():
    gt = os.environ.get("GITHUB_TOKEN"); rk = os.environ.get("RENDER_API_KEY")
    if not gt or not rk:
        print("ERROR: set GITHUB_TOKEN and RENDER_API_KEY", file=sys.stderr); sys.exit(2)
    repo_name = os.environ.get("GITHUB_REPO_NAME", "invoice-saas")
    secrets = read_env_secrets()
    if "DATABASE_URL" not in secrets:
        print("ERROR: .env missing DATABASE_URL"); sys.exit(1)

    # owner id for team-scoped creation
    owner_id = os.environ.get("RENDER_OWNER_ID")
    if not owner_id:
        st, body = http("GET", f"{RENDER}/owners", rd(rk))
        if st == 200 and isinstance(body, list) and body:
            owner_id = body[0].get("owner", {}).get("id")
    print(f"[render] owner_id = {owner_id}")

    # 1) GitHub: create private repo + push
    st, me = http("GET", f"{GITHUB}/user", gh(gt))
    if st != 200: print("GitHub auth failed:", st, me); sys.exit(1)
    owner = me["login"]
    print(f"[github] authenticated as {owner}")
    st, body = http("GET", f"{GITHUB}/repos/{owner}/{repo_name}", gh(gt))
    if st != 200:
        st, body = http("POST", f"{GITHUB}/user/repos", gh(gt),
                        {"name": repo_name, "private": True, "auto_init": False})
        if st not in (200, 201): print("[github] create repo failed:", st, body); sys.exit(1)
        print(f"[github] created private repo {owner}/{repo_name}")
    else:
        print(f"[github] repo {owner}/{repo_name} exists; will push")
    remote = f"https://{owner}:{gt}@github.com/{owner}/{repo_name}.git"
    subprocess.run(["git","remote","remove","origin"], capture_output=True)
    subprocess.run(["git","remote","add","origin", remote], check=True)
    subprocess.run(["git","push","-u","origin","HEAD:main","--force"], check=True,
                   env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    repo_url = f"https://github.com/{owner}/{repo_name}"
    print(f"[github] pushed -> {repo_url}")

    api_url = "https://invoice-saas-api.onrender.com"
    web_url = "https://invoice-saas-web.onrender.com"
    secrets["FRONTEND_BASE_URL"] = web_url
    secrets["BACKEND_BASE_URL"] = api_url

    # 2) Delete any existing services with our names (they are suspended/stale)
    existing = list_services(rk)
    for name in ("invoice-saas-api", "invoice-saas-web"):
        sid = existing.get(name)
        if sid:
            ok = delete_service(rk, sid)
            print(f"[render] deleted existing {name} ({sid}) -> {ok}")
            time.sleep(5)

    # 3) Create API (free web service)
    api_envs = [{"key": k, "value": v} for k, v in secrets.items()] + [
        {"key": "REDIS_URL", "value": ""},
        {"key": "APP_ENV", "value": "production"},
        {"key": "EXTRACTION_PROVIDER", "value": "mock"},
        {"key": "STORAGE_BACKEND", "value": "supabase"},
        {"key": "SUPABASE_STORAGE_ORIGINALS_BUCKET", "value": "invoice-originals"},
        {"key": "SUPABASE_STORAGE_EXPORTS_BUCKET", "value": "invoice-exports"},
        {"key": "SUPABASE_STORAGE_OCR_RAW_BUCKET", "value": "ocr-raw-results"},
        {"key": "WEB_CONCURRENCY", "value": "1"},
    ]
    api_payload = {
        "type": "web_service", "name": "invoice-saas-api", "region": "ohio",
        "repo": repo_url, "branch": "main",
        "serviceDetails": {
            "runtime": "docker",
            "dockerfilePath": "./backend/Dockerfile",
            "dockerContext": "./backend",
            "plan": "free",
            "healthCheckPath": "/api/health",
        },
        "envVars": api_envs,
    }
    if owner_id: api_payload["ownerId"] = owner_id
    st, body = create(rk, api_payload)
    print(f"[render] create API -> {st}", (body if isinstance(body,str) else "")[:160])
    if st not in (200, 201): print("  body:", str(body)[:400]); sys.exit(1)

    # 4) Create frontend (free web service)
    web_envs = [
        {"key": "NEXT_PUBLIC_SUPABASE_URL", "value": secrets.get("SUPABASE_URL", "")},
        {"key": "NEXT_PUBLIC_SUPABASE_ANON_KEY", "value": secrets.get("SUPABASE_ANON_KEY", "")},
        {"key": "NEXT_PUBLIC_BACKEND_BASE_URL", "value": api_url},
        {"key": "BACKEND_BASE_URL", "value": api_url},
        {"key": "NODE_ENV", "value": "production"},
    ]
    web_payload = {
        "type": "web_service", "name": "invoice-saas-web", "region": "ohio",
        "repo": repo_url, "branch": "main",
        "serviceDetails": {
            "runtime": "docker",
            "dockerfilePath": "./frontend/Dockerfile",
            "dockerContext": "./frontend",
            "plan": "free",
        },
        "envVars": web_envs,
    }
    if owner_id: web_payload["ownerId"] = owner_id
    st, body = create(rk, web_payload)
    print(f"[render] create web -> {st}", (body if isinstance(body,str) else "")[:160])
    if st not in (200, 201): print("  body:", str(body)[:400]); sys.exit(1)

    # 5) Poll API health
    print(f"[render] waiting for {api_url}/api/health (free tier build ~3-8 min)...")
    for i in range(80):
        st, body = http("GET", f"{api_url}/api/health", {"User-Agent": UA}, timeout=20)
        if st == 200:
            print(f"\n✅ API LIVE: {body}")
            print(f"✅ Frontend: {web_url}")
            print(f"✅ API:      {api_url}")
            print("\nFree tier: services sleep after 15 min idle (~30s cold start).")
            return
        if i % 4 == 0: print(f"   ...waiting ({i*15}s)")
        time.sleep(15)
    print("[render] API not healthy yet — check Render dashboard logs.")


if __name__ == "__main__":
    main()