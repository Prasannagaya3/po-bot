"""
PO Bot — Cloudflare + GitHub Setup
===================================
Usage:
  python setup_cloudflare.py CF_ACCOUNT_ID CF_API_TOKEN GH_TOKEN APP_PIN
         JIRA_TOKEN

Where:
  CF_ACCOUNT_ID  — from dash.cloudflare.com (in the URL after /accounts/)
  CF_API_TOKEN   — Cloudflare API token with Workers:Edit permission
  GH_TOKEN       — Your GitHub classic token (ghp_...)
  APP_PIN        — A PIN you choose to protect the web app (e.g. 2468)
  JIRA_TOKEN     — Your Jira API token (ATATT3x...)
"""

import sys, time, base64, json, requests, io

# ── Hardcoded values (already known) ──────────────────────────────────────────
GH_OWNER     = "Prasannagaya3"
GH_REPO      = "po-bot"
JIRA_DOMAIN  = "triogames.atlassian.net"
JIRA_EMAIL   = "Prasannakuppu@gmail.com"
WORKER_NAME  = "po-bot-worker"
CF_BASE      = "https://api.cloudflare.com/client/v4"

# Team config lives here as a secret — NOT in the repo
# po: auto-invited to every project, never shown in the member selection UI
TEAMS_CONFIG = json.dumps({
    "po": {
        "name": "Prasanna",
        "email": "prasannakuppu@gmail.com"
    },
    "teams": [
        {
            "id": "unity_dev",
            "name": "Unity Dev Team",
            "primary": "Game development, Unity coding",
            "also_covers": ["UI/UX implementation", "Store deployment"],
            "color": "#4F46E5",
            "members": [
                {
                    "name": "Prasanna7",
                    "email": "prasanna7gayathri@gmail.com",
                    "role": "developer",
                    "title": "Unity3D Developer"
                }
            ]
        },
        {
            "id": "3d_team",
            "name": "3D Team",
            "primary": "3D models, Textures, Animation",
            "also_covers": ["Sound engineering"],
            "color": "#10B981",
            "members": [
                {
                    "name": "Gowtham",
                    "email": "gowthamghayth@gmail.com",
                    "role": "developer",
                    "title": "3D Modeller"
                }
            ]
        },
        {
            "id": "backend",
            "name": "Backend Team",
            "primary": "API, server, database",
            "also_covers": [],
            "color": "#0EA5E9",
            "members": [
                {
                    "name": "Gokul",
                    "email": "gokulavarathan5@gmail.com",
                    "role": "developer",
                    "title": "Backend Developer"
                }
            ]
        }
    ]
})
# ──────────────────────────────────────────────────────────────────────────────


def cf(method, path, token, **kwargs):
    r = requests.request(method, f"{CF_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        **kwargs, timeout=30)
    return r


def gh_push(path, content, gh_token, msg):
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
    enc = base64.b64encode(content.encode()).decode()
    existing = requests.get(url, headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }, timeout=15)
    data = {"message": msg, "content": enc}
    if existing.status_code == 200:
        data["sha"] = existing.json()["sha"]
    r = requests.put(url, headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }, json=data, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR pushing {path}: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print(f"  + {path}")


def gh_delete(path, gh_token, msg):
    """Delete a file from the GitHub repo (no-op if it doesn't exist)."""
    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/contents/{path}"
    existing = requests.get(url, headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }, timeout=15)
    if existing.status_code == 404:
        print(f"  - {path} (not in repo — skipping)")
        return
    sha = existing.json().get("sha", "")
    r = requests.delete(url, headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }, json={"message": msg, "sha": sha}, timeout=30)
    if r.status_code in (200, 204):
        print(f"  - deleted {path}")
    else:
        print(f"  WARNING: Could not delete {path}: {r.status_code} {r.text[:100]}")


def set_secret(account_id, cf_token, name, value):
    r = cf("PUT", f"/accounts/{account_id}/workers/scripts/{WORKER_NAME}/secrets",
           cf_token, json={"name": name, "text": value, "type": "secret_text"})
    if r.status_code not in (200, 201):
        print(f"  ERROR setting secret {name}: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    print(f"  + Secret {name}")


def main():
    if len(sys.argv) != 6:
        print(__doc__)
        print("\nERROR: Wrong number of arguments.")
        print("Usage: python setup_cloudflare.py CF_ACCOUNT_ID CF_API_TOKEN GH_TOKEN APP_PIN JIRA_TOKEN")
        sys.exit(1)

    cf_account  = sys.argv[1].strip()
    cf_token    = sys.argv[2].strip()
    gh_token    = sys.argv[3].strip()
    app_pin     = sys.argv[4].strip()
    jira_token  = sys.argv[5].strip()

    print("\n" + "="*55)
    print("  PO Bot — Cloudflare + GitHub Setup")
    print("="*55)

    # ── 1. Validate Cloudflare token ──────────────────────────────────────────
    print("\n[1/5] Validating Cloudflare credentials...")
    r = cf("GET", "/user/tokens/verify", cf_token)
    if r.status_code != 200:
        print(f"  ERROR: Invalid Cloudflare token ({r.status_code})")
        print("  Make sure the token has 'Workers Scripts: Edit' permission.")
        sys.exit(1)
    print(f"  Cloudflare token valid.")

    # ── 2. Validate GitHub token ──────────────────────────────────────────────
    print("\n[2/5] Validating GitHub credentials...")
    me = requests.get("https://api.github.com/user", headers={
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }, timeout=15)
    if me.status_code != 200:
        print(f"  ERROR: Invalid GitHub token ({me.status_code})")
        sys.exit(1)
    print(f"  GitHub: {me.json()['login']}")

    # ── 3. Deploy Worker ──────────────────────────────────────────────────────
    print("\n[3/5] Deploying Cloudflare Worker...")

    with open("worker.js", encoding="utf-8") as f:
        script = f.read()

    metadata = json.dumps({
        "main_module": "worker.js",
        "bindings": [],
        "compatibility_date": "2024-01-01",
        "usage_model": "bundled"
    })

    files = {
        "metadata": ("metadata.json", io.StringIO(metadata), "application/json"),
        "worker.js": ("worker.js", io.StringIO(script), "application/javascript+module"),
    }

    r = requests.put(
        f"{CF_BASE}/accounts/{cf_account}/workers/scripts/{WORKER_NAME}",
        headers={"Authorization": f"Bearer {cf_token}"},
        files=files,
        timeout=60,
    )

    if r.status_code not in (200, 201):
        print(f"  ERROR deploying Worker: {r.status_code}")
        print(f"  {r.text[:400]}")
        sys.exit(1)
    print(f"  Worker deployed: {WORKER_NAME}")

    # Enable Worker subdomain if not already
    cf("POST", f"/accounts/{cf_account}/workers/scripts/{WORKER_NAME}/subdomain",
       cf_token, json={"enabled": True})

    # Get Worker URL
    worker_url = f"https://{WORKER_NAME}.{cf_account[:8]}.workers.dev"
    r3 = cf("GET", f"/accounts/{cf_account}/workers/subdomain", cf_token)
    if r3.status_code == 200:
        subdomain = r3.json().get("result", {}).get("subdomain", "")
        if subdomain:
            worker_url = f"https://{WORKER_NAME}.{subdomain}.workers.dev"
    print(f"  Worker URL: {worker_url}")

    # ── 4. Set Worker secrets ─────────────────────────────────────────────────
    print("\n[4/5] Setting Worker secrets...")
    secrets = {
        "GITHUB_TOKEN":   gh_token,
        "GITHUB_REPO":    f"{GH_OWNER}/{GH_REPO}",
        "JIRA_DOMAIN":    JIRA_DOMAIN,
        "JIRA_EMAIL":     JIRA_EMAIL,
        "JIRA_TOKEN":     jira_token,
        "APP_PIN":        app_pin,
        "TEAMS_CONFIG":   TEAMS_CONFIG,
        # Used by the worker to self-update TEAMS_CONFIG via /api/update-teams
        "CF_ACCOUNT_ID":  cf_account,
        "CF_API_TOKEN":   cf_token,
    }
    for name, value in secrets.items():
        set_secret(cf_account, cf_token, name, value)
        time.sleep(0.3)

    # ── 5. Push files to GitHub ────────────────────────────────────────────────
    print("\n[5/5] Pushing files to GitHub...")

    # Delete config/teams.json — team data now lives in TEAMS_CONFIG secret
    gh_delete("config/teams.json", gh_token, "security: remove team emails from repo")
    time.sleep(0.5)

    # Push config.js with the real worker URL injected
    config_js = f"window.PO_BOT_WORKER_URL = '{worker_url}';\n"
    gh_push("config.js", config_js, gh_token, "config: update Worker URL")
    time.sleep(0.5)

    # Push setup script itself
    with open("setup_cloudflare.py", encoding="utf-8") as f:
        gh_push("setup_cloudflare.py", f.read(), gh_token, "feat: update setup script")
    time.sleep(0.5)

    # Push pipeline script
    with open("scripts/generate_backlog.py", encoding="utf-8") as f:
        gh_push("scripts/generate_backlog.py", f.read(), gh_token, "feat: update pipeline script")
    time.sleep(0.5)

    # Push local save script
    with open("scripts/save_project.py", encoding="utf-8") as f:
        gh_push("scripts/save_project.py", f.read(), gh_token, "feat: update save_project script")
    time.sleep(0.5)

    # Push workflow
    with open(".github/workflows/step1-generate-backlog.yml", encoding="utf-8") as f:
        gh_push(".github/workflows/step1-generate-backlog.yml", f.read(), gh_token, "feat: update workflow")
    time.sleep(0.5)

    # Push worker source
    with open("worker.js", encoding="utf-8") as f:
        gh_push("worker.js", f.read(), gh_token, "feat: update Cloudflare Worker")
    time.sleep(0.5)

    # Push index.html as-is (worker URL now comes from config.js, not index.html)
    with open("index.html", encoding="utf-8") as f:
        gh_push("index.html", f.read(), gh_token, "feat: update frontend")
    time.sleep(1)

    print(f"""
{'='*55}
  Setup complete!

  Worker URL  : {worker_url}
  Frontend    : https://{GH_OWNER}.github.io/{GH_REPO}
  Your PIN    : {app_pin}

  Secrets set : GITHUB_TOKEN, GITHUB_REPO, JIRA_DOMAIN,
                JIRA_EMAIL, JIRA_TOKEN, APP_PIN, TEAMS_CONFIG,
                CF_ACCOUNT_ID, CF_API_TOKEN

  Security:
  - config/teams.json deleted from repo
  - Team member emails stored only in TEAMS_CONFIG secret
  - Processed docs deleted from repo after backlog generation
  - Worker URL served via config.js (not hardcoded in index.html)

  NEXT STEP (one-time, 2 minutes):
  Set up Cloudflare Pages to serve your frontend:

  1. Go to: dash.cloudflare.com
  2. Click Pages -> Create a project
  3. Connect to GitHub -> select {GH_OWNER}/{GH_REPO}
  4. Build settings:
       Framework preset: None
       Build command:    (leave empty)
       Output directory: /
  5. Click Deploy

{'='*55}
""")


if __name__ == "__main__":
    main()
