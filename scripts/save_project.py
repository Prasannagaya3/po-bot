"""
Save PO Bot project to local folder.

Usage:
  python scripts/save_project.py "Project Name" JIRA_KEY backlog/filename.json
  python scripts/save_project.py "Project Name" JIRA_KEY backlog/filename.json "C:/path/to/original_doc.pdf"

Arguments:
  1  Project Name       — used as the archive folder name
  2  JIRA_KEY           — e.g. MYGAME93210
  3  backlog_path       — GitHub path, e.g. backlog/mygame_20260320_123456.json
  4  original_doc_path  — (optional) local path to your original document;
                          copied into original_docs/ in the archive

GitHub token is loaded from (in order):
  1. Environment variable  GITHUB_TOKEN
  2. File  D:\\Work\\Unity_Applications\\Product Development\\.po_bot_token
  3. Interactive prompt (saved to the file above for future use)

Creates:
  D:\\Work\\Unity_Applications\\Product Development\\{project_name}\\
    original_docs\\         (source doc copied here if path provided)
    backlog.json            (copy from GitHub)
    standardised_doc.md     (copy from GitHub)
    project_info.txt        (project metadata)
"""

import sys, os, re, json, shutil, datetime, requests

# ── Hardcoded repo info ────────────────────────────────────────────────────────
GH_OWNER    = "Prasannagaya3"
GH_REPO     = "po-bot"
GH_API      = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}"
JIRA_DOMAIN = "triogames.atlassian.net"
BASE_DIR    = r"D:\Work\Unity_Applications\Product Development"
TOKEN_FILE  = os.path.join(BASE_DIR, ".po_bot_token")
# ──────────────────────────────────────────────────────────────────────────────


def load_token():
    """
    Load GITHUB_TOKEN from:
      1. Environment variable GITHUB_TOKEN
      2. D:\\Work\\Unity_Applications\\Product Development\\.po_bot_token
      3. Interactive prompt — saves to the file for future use
    """
    # 1. Environment variable
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    # 2. Saved token file
    if os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if token:
            return token

    # 3. Prompt once, then save
    print("\n  GitHub token not found.")
    print("  Create a classic token at https://github.com/settings/tokens")
    print("  with 'repo' scope, then paste it below.")
    token = input("  GitHub token (ghp_...): ").strip()
    if not token:
        print("  ERROR: No token provided.")
        sys.exit(1)
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    print(f"  Token saved to {TOKEN_FILE} — won't be asked again.")
    return token


def gh_download(gh_path, token):
    """Fetch a file from the repo. Returns (text_content, error_string)."""
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
    → standardised/my-product_20260320_073541.md
    """
    filename = os.path.basename(backlog_path)
    name = re.sub(r"\.json$", "", filename)
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

    project_name      = sys.argv[1].strip()
    jira_key          = sys.argv[2].strip().upper()
    backlog_path      = sys.argv[3].strip()
    original_doc_path = sys.argv[4].strip() if len(sys.argv) >= 5 else ""

    token = load_token()

    print(f"\nSaving project: {project_name} ({jira_key})")
    print("─" * 54)

    # ── Create folder structure ────────────────────────────────────────────────
    folder_name  = safe_dir_name(project_name)
    project_dir  = os.path.join(BASE_DIR, folder_name)
    orig_docs_dir = os.path.join(project_dir, "original_docs")
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(orig_docs_dir, exist_ok=True)
    print(f"  + Folder created")

    # ── Copy original document if provided ────────────────────────────────────
    if original_doc_path:
        if os.path.exists(original_doc_path):
            dest = os.path.join(orig_docs_dir, os.path.basename(original_doc_path))
            shutil.copy2(original_doc_path, dest)
            print(f"  + original_docs/{os.path.basename(original_doc_path)}")
        else:
            print(f"  ! Original doc not found: {original_doc_path} — skipping")

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
