"""
PO Bot — Two-Stage Pipeline
===========================
Stage 1 (MODE=standardise): Raw docs → clean product document → standardised/
Stage 2 (MODE=generate):    Clean doc → structured backlog JSON → backlog/
"""

import os, sys, json
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# TEXT EXTRACTION
# ---------------------------------------------------------------------------

def extract_text(filepath):
    ext = filepath.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        import PyPDF2
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages).strip()
        if not text:
            raise ValueError("PDF appears image-based. Use a text-based PDF or .txt instead.")
        return text
    elif ext == "docx":
        from docx import Document
        doc = Document(filepath)
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        for t in doc.tables:
            for r in t.rows:
                lines.append(" | ".join(c.text.strip() for c in r.cells))
        return "\n".join(lines)
    elif ext in ("txt", "md"):
        return open(filepath, encoding="utf-8").read()
    else:
        raise ValueError(f"Unsupported format: .{ext}  (use .pdf .docx .md .txt)")


# ---------------------------------------------------------------------------
# STAGE 1 — STANDARDISE
# ---------------------------------------------------------------------------

STANDARDISE_SYSTEM = """You are a senior product documentation specialist.
Your job is to take ANY raw input — rough notes, bullet points, chat messages,
partial specs, spreadsheets, or well-written documents — and convert it into
a clean, structured product document.

RULES:
- Extract and organise all information that was given
- Fill gaps intelligently based on context and common sense
- Do NOT invent features that were not mentioned or clearly implied
- If you make an assumption, add a note like: [Assumed: users need login]
- Group features logically by functional area
- Be specific — vague features make weak user stories
- Output ONLY the structured document — no preamble, no explanation"""

STANDARDISE_PROMPT = """Convert the following raw input into a clean, structured product document.

Use EXACTLY this format:

# [Product Name]

## Product Overview
[2-3 sentences: what it is, what problem it solves, who it is for]

## Problem Statement
[What specific problem does this solve and why does it need to exist?]

## Target Users
- **[Persona Name]**: [what they need and why they use the product]
- **[Persona Name]**: [what they need and why they use the product]

## Core Features

### [Feature Area 1]
- [Specific feature with enough detail to write a user story]
- [Specific feature]

### [Feature Area 2]
- [Specific feature]

## Non-Functional Requirements
- Platform: [iOS / Android / Web / etc.]
- [Performance requirements]
- [Technical constraints]

## Out of Scope
- [Feature explicitly not in this version]

---
RAW INPUT:
{raw_text}
---"""


def stage1_standardise(raw_text, doc_name):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print("  Stage 1: Standardising document...")

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        system=STANDARDISE_SYSTEM,
        messages=[{"role": "user", "content": STANDARDISE_PROMPT.format(raw_text=raw_text[:10000])}]
    )
    return msg.content[0].text.strip()


# ---------------------------------------------------------------------------
# STAGE 2 — GENERATE BACKLOG
# ---------------------------------------------------------------------------

BACKLOG_SYSTEM = """You are a Principal Product Owner with 15 years of Agile/Scrum experience.
Read a product document and produce a complete sprint-ready product backlog.
PROCESS:
1. Identify personas  2. Extract vision  3. Group into 4-8 Epics
4. Write 2-6 User Stories per Epic  5. 2-3 Acceptance Criteria per story (Given/When/Then)
6. Story points: 1=trivial 2=small 3=medium 5=large 8=complex 13=very complex
7. MoSCoW: Must Have=MVP, Should Have=important, Could Have=nice-to-have, Wont Have=out of scope
8. Sprint 1=walking skeleton, Sprint 2=all Must Haves, Sprint 3+=Should/Could Haves
RULES: Base only on document content. Story IDs: US-001... Epic IDs: E1...
OUTPUT: valid JSON only - no markdown, start with { end with }

TEAM ASSIGNMENT — assign each story to exactly one team based on the work involved:
- "unity_dev" → Unity3D coding, gameplay mechanics, UI/UX implementation, scenes, builds, store deployment, any programming
- "3d_team"   → 3D models, textures, rigging, animation, VFX, particle effects, art assets, sound, audio engineering
- "backend"   → APIs, server logic, databases, authentication, cloud services, data pipelines, analytics backend"""

BACKLOG_PROMPT = """Return a complete product backlog as JSON:
{{
  "project_name": "string",
  "vision": "one sentence",
  "personas": ["persona 1"],
  "epics": [{{
    "id": "E1", "name": "string", "description": "string",
    "stories": [{{
      "id": "US-001", "title": "max 8 words",
      "user_story": "As a [persona], I want [action], so that [benefit]",
      "acceptance_criteria": ["Given X When Y Then Z", "Given X When Y Then Z"],
      "story_points": 3, "priority": "Must Have", "sprint": 1,
      "team": "unity_dev",
      "notes": ""
    }}]
  }}]
}}
IMPORTANT: Every story MUST have a "team" field set to exactly one of: "unity_dev", "3d_team", "backend".
Choose based on what the story actually requires to implement — not the epic name.
DOCUMENT:
---
{doc_text}
---"""


def stage2_generate(doc_text, doc_name):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print("  Stage 2: Generating backlog...")

    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=BACKLOG_SYSTEM,
        messages=[{"role": "user", "content": BACKLOG_PROMPT.format(doc_text=doc_text[:12000])}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1][4:] if parts[1].startswith("json") else parts[1]
    return json.loads(raw.strip())


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    mode     = os.environ.get("MODE", "standardise").strip()
    doc_file = os.environ.get("DOC_FILE", "").strip()
    doc_name = os.environ.get("DOC_NAME", "doc").strip()
    extra    = os.environ.get("EXTRA_FILES", "").strip()

    if not doc_file or not os.path.exists(doc_file):
        print(f"DOC_FILE not set or not found: {doc_file}")
        sys.exit(0)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n{'='*50}\n  PO Bot — {mode.upper()}\n  File: {doc_file}\n{'='*50}")

    print("\n[1] Extracting text...")
    raw_text = extract_text(doc_file)

    if extra:
        for extra_file in extra.split(","):
            extra_file = extra_file.strip()
            if extra_file and os.path.exists(extra_file):
                print(f"  + Merging: {extra_file}")
                raw_text += "\n\n---\n\n" + extract_text(extra_file)

    print(f"  {len(raw_text):,} characters total")

    if mode == "standardise":
        print("\n[2] Standardising with Claude...")
        clean_doc = stage1_standardise(raw_text, doc_name)

        os.makedirs("standardised", exist_ok=True)
        out = f"standardised/{doc_name}_{ts}.md"
        with open(out, "w", encoding="utf-8") as f:
            f.write(clean_doc)
        print(f"  Saved: {out}")
        print(f"\n{'='*50}\n  Stage 1 complete: {out}\n{'='*50}\n")

    elif mode == "generate":
        print("\n[2] Generating backlog with Claude...")
        backlog = stage2_generate(raw_text, doc_name)

        stories = sum(len(e["stories"]) for e in backlog["epics"])
        sprints = max(s["sprint"] for e in backlog["epics"] for s in e["stories"])
        print(f"  Project: {backlog.get('project_name')}")
        print(f"  Epics: {len(backlog['epics'])}  Stories: {stories}  Sprints: {sprints}")

        backlog["_meta"] = {
            "source_document": doc_file,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_review"
        }

        os.makedirs("backlog", exist_ok=True)
        out = f"backlog/{doc_name}_{ts}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(backlog, f, indent=2, ensure_ascii=False)
        print(f"  Saved: {out}")

        print(f"\n  Sprint summary:")
        for n in range(1, sprints + 1):
            ss = [s for e in backlog["epics"] for s in e["stories"] if s["sprint"] == n]
            pts = sum(s["story_points"] for s in ss)
            must = sum(1 for s in ss if s["priority"] == "Must Have")
            print(f"    Sprint {n}: {len(ss)} stories ({pts} pts) - {must} Must Have")

        print(f"\n{'='*50}\n  Stage 2 complete: {out}\n{'='*50}\n")

    else:
        print(f"Unknown MODE: {mode}. Use 'standardise' or 'generate'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
