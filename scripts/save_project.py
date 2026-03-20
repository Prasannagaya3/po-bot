"""
Save PO Bot project to local folder.

Usage:
  python scripts/save_project.py "Project Name" JIRA_KEY backlog/filename.json
  python scripts/save_project.py "Project Name" JIRA_KEY backlog/filename.json "Team Name"

Requires GITHUB_TOKEN environment variable, or a .env file in the repo root.

Creates:
  D:\\Work\\Unity_Applications\\Product Development\\{project_name}\\
    original_docs\\          (empty — place source documents here)
    backlog.json             (copy of the generated backlog from GitHub)
    standardised_doc.md      (copy of the standardised document from GitHub)
    project_info.txt         (project metadata)
"""

import sys, os, re, json, datetime, requests

# ── Hardcoded repo info ────────────────────────────────────────────────────────
GH_OWNER    = "Prasannagaya3"
GH_REPO     = "po-bot"
GH_API      = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}"
JIRA_DOMAIN = "triogames.atlassian.net"
BASE_DIR    = r"D:\Work\Unity_Applications\Product Development"
# ──────────────────────────────────────────────────────────────────────────────


def load_token():
    """Load GITHUB_TOKEN from env, then from .env at repo root."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    # Try .env file in repo root (two levels up from scripts/)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(repo_root, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def gh_download(gh_path, token):
    """Fetch a file from the repo and return (text_content, error_string)."""
    url = f"{GH_API}/contents/{gh_path}"
    r = requests.get(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "PO-Bot-SaveScript",
    }, timeout=30)
    if r.status_code == 404:
        return None, f"not found in repo ({gh_path})"
    if not r.ok:
        return None, f"GitHub error {r.status_code}"
    data = r.json()
    raw_url = data.get("download_url")
    if not raw_url:
        return None, "no download_url returned"
    raw = requests.get(raw_url, headers={"User-Agent": "PO-Bot-SaveScript"}, timeout=30)
    if not raw.ok:
        return None, f"download failed ({raw.status_code})"
    return raw.text, None


def derive_std_path(backlog_path):
    """
    Derive standardised doc path from backlog path.

    backlog/my-product_20260320_073541_20260320_081234.json
    →  standardised/my-product_20260320_073541.md
    """
    filename = os.path.basename(backlog_path)
    name = re.sub(r"\.json$", "", filename)
    # Strip the final _YYYYMMDD_HHMMSS timestamp added by stage 2
    std_name = re.sub(r"_\d{8}_\d{6}$", "", name)
    return f"standardised/{std_name}.md"


def safe_dir_name(name):
    """Strip characters illegal in Windows folder names."""
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip(". ")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        print("ERROR: Missing arguments.")
        print('Usage: python scripts/save_project.py "Project Name" JIRA_KEY backlog/filename.json')
        sys.exit(1)

    project_name = sys.argv[1].strip()
    jira_key     = sys.argv[2].strip().upper()
    backlog_path = sys.argv[3].strip()          # e.g. backlog/my-product_20260320_123456.json
    team_name    = sys.argv[4].strip() if len(sys.argv) >= 5 else ""

    token = load_token()
    if not token:
        print("\nERROR: GITHUB_TOKEN not set.")
        print("  Option 1: set GITHUB_TOKEN=ghp_...  (in your terminal, then re-run)")
        print("  Option 2: create a .env file in the repo root with: GITHUB_TOKEN=ghp_...")
        sys.exit(1)

    print(f"\nSaving project: {project_name} ({jira_key})")
    print("─" * 54)

    # ── Create folder structure ────────────────────────────────────────────────
    folder_name = safe_dir_name(project_name)
    project_dir = os.path.join(BASE_DIR, folder_name)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "original_docs"), exist_ok=True)
    print(f"  + Folder created")

    # ── Fetch backlog.json ─────────────────────────────────────────────────────
    print(f"  Fetching {backlog_path} ...", end=" ", flush=True)
    backlog_text, err = gh_download(backlog_path, token)
    if err:
        print(f"FAILED\n  ERROR: {err}")
        sys.exit(1)
    print("OK")

    out_backlog = os.path.join(project_dir, "backlog.json")
    with open(out_backlog, "w", encoding="utf-8") as f:
        f.write(backlog_text)
    print(f"  + backlog.json")

    # Count stories for project_info.txt
    story_count = 0
    try:
        bl = json.loads(backlog_text)
        story_count = sum(len(ep.get("stories", [])) for ep in bl.get("epics", []))
    except Exception:
        pass

    # ── Fetch standardised_doc.md ──────────────────────────────────────────────
    std_path = derive_std_path(backlog_path)
    print(f"  Fetching {std_path} ...", end=" ", flush=True)
    std_text, err = gh_download(std_path, token)
    if std_text:
        print("OK")
        out_std = os.path.join(project_dir, "standardised_doc.md")
        with open(out_std, "w", encoding="utf-8") as f:
            f.write(std_text)
        print(f"  + standardised_doc.md")
    else:
        print(f"not found — skipping")

    # ── Write project_info.txt ─────────────────────────────────────────────────
    jira_url = f"https://{JIRA_DOMAIN}/jira/software/projects/{jira_key}/board"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"Project Name  : {project_name}",
        f"Jira Key      : {jira_key}",
        f"Jira URL      : {jira_url}",
        f"Date Created  : {now}",
        f"Stories       : {story_count}",
    ]
    if team_name:
        lines.append(f"Team          : {team_name}")
    lines += [
        f"",
        f"Source Repo   : https://github.com/{GH_OWNER}/{GH_REPO}",
        f"Backlog File  : {backlog_path}",
    ]
    out_info = os.path.join(project_dir, "project_info.txt")
    with open(out_info, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  + project_info.txt")

    print(f"\n  Folder: {project_dir}\n")


if __name__ == "__main__":
    main()
