import os, sys, json
from datetime import datetime, timezone

def extract_text(filepath):
    ext = filepath.lower().rsplit('.', 1)[-1]
    if ext == 'pdf':
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = '\n\n'.join(p.extract_text() or '' for p in reader.pages).strip()
        if not text:
            raise ValueError('PDF appears image-based. Use .txt instead.')
        return text
    elif ext == 'docx':
        from docx import Document
        doc = Document(filepath)
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        for t in doc.tables:
            for r in t.rows:
                lines.append(' | '.join(c.text.strip() for c in r.cells))
        return '\n'.join(lines)
    elif ext in ('txt', 'md'):
        return open(filepath, encoding='utf-8').read()
    else:
        raise ValueError(f'Unsupported: .{ext}  (use .pdf .docx .md .txt)')

SYSTEM_PROMPT = (
    'You are a Principal Product Owner with 15 years of Agile/Scrum experience. '
    'Read a product document and produce a complete sprint-ready product backlog. '
    'PROCESS: '
    '1. Identify personas  '
    '2. Extract vision  '
    '3. Group into 4-8 Epics  '
    '4. Write 2-6 User Stories per Epic  '
    '5. Write 2-3 Acceptance Criteria per story in Given/When/Then format  '
    '6. Story points: 1=trivial 2=small 3=medium 5=large 8=complex 13=very complex  '
    '7. MoSCoW: Must Have=MVP, Should Have=important, Could Have=nice-to-have, Wont Have=out of scope  '
    '8. Sprint 1=walking skeleton, Sprint 2=all Must Haves, Sprint 3+=Should/Could Haves  '
    'RULES: Base only on document content. Story IDs: US-001... Epic IDs: E1...  '
    'OUTPUT: valid JSON only - no markdown, start with { end with }'
)

USER_PROMPT = '''Return a complete product backlog as JSON:
{{
  "project_name": "string",
  "vision": "one sentence",
  "personas": ["persona 1"],
  "epics": [{{
    "id": "E1", "name": "string", "description": "string",
    "stories": [{{
      "id": "US-001", "title": "max 8 words",
      "user_story": "As a [persona], I want [action], so that [benefit]",
      "acceptance_criteria": ["Given X When Y Then Z"],
      "story_points": 3, "priority": "Must Have", "sprint": 1, "notes": ""
    }}]
  }}]
}}
DOCUMENT:
---
{doc_text}
---'''

def call_claude(doc_text):
    import anthropic
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        raise EnvironmentError('ANTHROPIC_API_KEY is not set.')
    client = anthropic.Anthropic(api_key=key)
    print('  Calling Claude API...')
    msg = client.messages.create(
        model='claude-opus-4-5', max_tokens=4096, system=SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': USER_PROMPT.format(doc_text=doc_text[:12000])}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith('```'):
        parts = raw.split('```')
        raw = parts[1][4:] if parts[1].startswith('json') else parts[1]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        print(f'ERROR: Invalid JSON from Claude:\n{raw[:400]}')
        raise

def main():
    doc_file = os.environ.get('DOC_FILE', '').strip()
    doc_name = os.environ.get('DOC_NAME', 'backlog').strip()
    if not doc_file:
        print('DOC_FILE not set.'); sys.exit(0)
    if not os.path.exists(doc_file):
        print(f'ERROR: {doc_file} not found'); sys.exit(1)
    print(f'\n{"="*50}\n  PO Bot - Step 1\n  Document: {doc_file}\n{"="*50}')
    print('\n[1/3] Extracting text...')
    text = extract_text(doc_file)
    print(f'  {len(text):,} characters')
    print('\n[2/3] Generating backlog with Claude...')
    backlog = call_claude(text)
    stories = sum(len(e['stories']) for e in backlog['epics'])
    sprints = max(s['sprint'] for e in backlog['epics'] for s in e['stories'])
    print(f"  Project : {backlog.get('project_name')}")
    print(f'  Epics: {len(backlog["epics"])}  Stories: {stories}  Sprints: {sprints}')
    print('\n[3/3] Saving JSON...')
    backlog['_meta'] = {
        'source_document': doc_file,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pending_review'
    }
    os.makedirs('backlog', exist_ok=True)
    ts  = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    out = f'backlog/{doc_name}_{ts}.json'
    json.dump(backlog, open(out, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print(f'  Saved: {out}')
    print('\n  Sprint summary:')
    for n in range(1, sprints + 1):
        ss   = [s for e in backlog['epics'] for s in e['stories'] if s['sprint'] == n]
        pts  = sum(s['story_points'] for s in ss)
        must = sum(1 for s in ss if s['priority'] == 'Must Have')
        print(f'    Sprint {n}: {len(ss)} stories ({pts} pts) - {must} Must Have')
    print(f'\n{"="*50}\n  Done: {out}\n{"="*50}\n')

if __name__ == '__main__':
    main()