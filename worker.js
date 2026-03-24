// PO Bot — Cloudflare Worker (ES Module syntax)
// Two-stage pipeline: standardise → generate → approve to Jira

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-PIN',
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

function checkPin(request, env) {
  return request.headers.get('X-PIN') === env.APP_PIN;
}

async function ghFetch(path, env, opts = {}) {
  const url = path.startsWith('http')
    ? path
    : `https://api.github.com/repos/${env.GITHUB_REPO}/${path}`;
  return fetch(url, {
    ...opts,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
      'User-Agent': 'PO-Bot-Worker',
      ...(opts.headers || {}),
    },
  });
}

// Upload (or update) a single file in the GitHub repo
async function uploadToGitHub(path, content_base64, env, message) {
  const existRes = await ghFetch(`contents/${path}`, env);
  const putBody = { message: message || `upload ${path}`, content: content_base64 };
  if (existRes.status === 200) {
    putBody.sha = (await existRes.json()).sha;
  }
  return ghFetch(`contents/${path}`, env, {
    method: 'PUT',
    body: JSON.stringify(putBody),
  });
}

// Find the step1/generate workflow (only needed for PDF/DOCX fallback)
async function getWorkflow(env) {
  const wfRes = await ghFetch('actions/workflows', env);
  if (!wfRes.ok) return null;
  const wfData = await wfRes.json();
  return (wfData.workflows || []).find(
    w => w.path.includes('step1') || w.path.includes('generate')
  ) || null;
}

function timestamp() {
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}${p(d.getUTCMonth()+1)}${p(d.getUTCDate())}_${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}`;
}

function encodeBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

async function callClaude(system, user, env, maxTokens) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-sonnet-4-6',
      max_tokens: maxTokens,
      system,
      messages: [{ role: 'user', content: user }],
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Claude API error ${res.status}: ${err.slice(0, 200)}`);
  }
  const data = await res.json();
  return data.content[0].text.trim();
}

const STANDARDISE_SYSTEM = `You are a senior game product manager and technical producer at a Unity game studio.
Your job is to take ANY raw input — rough notes, Slack messages, voice memo transcripts, bullet points,
or partial specs — and convert it into a clean, complete game product document ready for sprint planning.

RULES:
- Extract and organise ALL information given — nothing is too small to capture
- Fill gaps intelligently using game development common sense
- If you make an assumption, mark it clearly: [Assumed: ...]
- Be SPECIFIC — "add enemies" is useless. "Add 3 enemy types: melee grunt, ranged archer, boss" is useful
- Think in terms of what each team needs to actually build this:
    Unity Dev: scenes, scripts, physics, animation controllers, UI, builds, store
    3D Team: models, textures, rigs, animations, VFX, audio, sound effects
    Backend: APIs, databases, cloud saves, leaderboards, analytics, auth
- Surface ALL technical constraints, platform targets, and performance goals
- Output ONLY the structured document — no preamble, no explanation`;

const STANDARDISE_PROMPT_TPL = `Convert the following raw input into a clean, structured game product document.

Use EXACTLY this format:

# [Game Title]

## Game Overview
[2-3 sentences: genre, core loop, platform, and what makes it fun/unique]

## Problem / Opportunity
[Why does this game need to exist? What gap does it fill? Who is the target player?]

## Target Players
- **[Player Type 1]**: [age, gaming experience, what they want from this game]
- **[Player Type 2]**: [age, gaming experience, what they want from this game]

## Game Design

### Core Gameplay Loop
[Step-by-step description of the main gameplay cycle — what the player does every session]

### Game Mechanics
- [Specific mechanic with enough detail to implement — e.g. "Double-jump with 0.3s coyote time"]

### Progression System
- [How the player advances — levels, XP, unlocks, difficulty curve]

### Win / Lose Conditions
- [Clear win state]
- [Clear fail state and consequences]

## Visual & Audio Direction

### Art Style
[Describe the look — reference games or styles, colour palette, perspective (2D/3D/isometric), tone]

### 3D / 2D Assets Required
- Characters: [list with description]
- Environments: [list with description]
- UI elements: [list with description]
- VFX: [list — particles, shaders, effects]

### Audio
- Music: [style, number of tracks, when they play]
- SFX: [key sound effects needed]

## Technical Specifications
- Engine: Unity [version if specified]
- Platform: [iOS / Android / PC / Console / WebGL]
- Target frame rate: [e.g. 60fps mobile, 120fps PC]
- Orientation: [Portrait / Landscape / Both]
- Min device spec: [e.g. iPhone X, Android 8.0]
- Multiplayer: [Yes/No — if yes, real-time or turn-based]
- Backend services: [cloud saves / leaderboards / analytics / auth / none]

## Monetisation (if applicable)
- Model: [Premium / Free-to-play / Ads / IAP]

## Features by Area

### Core Gameplay
- [Specific implementable feature]

### UI / UX
- [Specific screen or flow]

### Backend & Services
- [Specific backend feature]

### Store & Deployment
- [Platform-specific requirement]

## Out of Scope (v1)
- [Feature explicitly excluded from this version]

## Open Questions
- [Anything unclear that needs a decision before work starts]

---
RAW INPUT:
{raw_text}
---`;

const BACKLOG_SYSTEM = `You are a Principal Product Owner at a Unity game studio.
Create a sprint-ready backlog from the game document.

EPICS: Pick 4-6 from this list (only what the document supports):
Core Gameplay Mechanics | Characters & Animation | Environments & Level Design |
UI / UX | Audio & Visual FX | Backend & Services | Store & Release | QA & Polish

STORIES: 2-4 per epic. Each story = one deliverable unit of work.
CRITERIA: exactly 2 per story, Given/When/Then format, testable by QA.
POINTS: 1=trivial 2=small 3=medium 5=large 8=complex
PRIORITY: Must Have=MVP blocker | Should Have=important | Could Have=nice-to-have
SPRINTS: Sprint 1=walking skeleton, Sprint 2-3=all Must Haves, Sprint 4+=rest

TEAM (every story must have one):
"unity_dev"  = C# scripts, Unity scenes, physics, UI canvas, build pipeline, store deployment
"3d_team"    = 3D models, textures, rigs, animations, VFX, shader graph, SFX, music
"backend"    = APIs, Firebase/PlayFab, databases, cloud saves, leaderboards, auth, analytics

OUTPUT: valid JSON only — no markdown, no explanation.`;

const BACKLOG_PROMPT_TPL = `Return the backlog as JSON using EXACTLY this schema:

{
  "project_name": "string",
  "epics": [
    {
      "name": "string",
      "stories": [
        {
          "title": "string — action verb + object, max 8 words",
          "criteria": [
            "Given ... When ... Then ...",
            "Given ... When ... Then ..."
          ],
          "points": 3,
          "priority": "Must Have",
          "sprint": 1,
          "team": "unity_dev"
        }
      ]
    }
  ]
}

GAME DOCUMENT:
---
{doc_text}
---`;

// POST /api/standardise — decode text and call Claude directly in background
async function handleStandardise(request, env, ctx) {
  const body = await request.json().catch(() => null);
  if (!body || !body.filename || !body.content_base64)
    return jsonResponse({ error: 'Missing filename or content_base64' }, 400);

  const { filename, content_base64, extra_files = [] } = body;
  const docName = filename.replace(/\.[^.]+$/, '');
  const ext = filename.split('.').pop().toLowerCase();

  // PDF / DOCX: still need GitHub Actions for text extraction
  if (ext === 'pdf' || ext === 'docx') {
    const primaryPath = `docs/${filename}`;
    const upRes = await uploadToGitHub(primaryPath, content_base64, env, `docs: upload ${filename}`);
    if (!upRes.ok) return jsonResponse({ error: `Upload failed (${upRes.status})` }, 500);
    const extraPaths = [];
    for (const ef of extra_files) {
      const p = `docs/${ef.filename}`;
      const r = await uploadToGitHub(p, ef.content_base64, env, `docs: upload ${ef.filename}`);
      if (r.ok) extraPaths.push(p);
    }
    const wf = await getWorkflow(env);
    if (!wf) return jsonResponse({ error: 'Workflow not found.' }, 500);
    const trigRes = await ghFetch(`actions/workflows/${wf.id}/dispatches`, env, {
      method: 'POST',
      body: JSON.stringify({ ref: 'main', inputs: { doc_path: primaryPath, mode: 'standardise', extra_files: extraPaths.join(',') } }),
    });
    if (!trigRes.ok) return jsonResponse({ error: `Trigger failed (${trigRes.status})` }, 500);
    return jsonResponse({ doc_name: docName, status: 'triggered' });
  }

  // TXT / MD: if ANTHROPIC_API_KEY is set, call Claude directly (fast path)
  // Otherwise fall back to GitHub Actions
  const hasAnthropicKey = env.ANTHROPIC_API_KEY && !env.ANTHROPIC_API_KEY.startsWith('placeholder') && env.ANTHROPIC_API_KEY.startsWith('sk-');

  if (!hasAnthropicKey) {
    // GitHub Actions fallback
    const primaryPath = `docs/${filename}`;
    const upRes = await uploadToGitHub(primaryPath, content_base64, env, `docs: upload ${filename}`);
    if (!upRes.ok) return jsonResponse({ error: `Upload failed (${upRes.status})` }, 500);
    const extraPaths = [];
    for (const ef of extra_files) {
      const p = `docs/${ef.filename}`;
      const r = await uploadToGitHub(p, ef.content_base64, env, `docs: upload ${ef.filename}`);
      if (r.ok) extraPaths.push(p);
    }
    const wf = await getWorkflow(env);
    if (!wf) return jsonResponse({ error: 'Workflow not found.' }, 500);
    const trigRes = await ghFetch(`actions/workflows/${wf.id}/dispatches`, env, {
      method: 'POST',
      body: JSON.stringify({ ref: 'main', inputs: { doc_path: primaryPath, mode: 'standardise', extra_files: extraPaths.join(',') } }),
    });
    if (!trigRes.ok) return jsonResponse({ error: `Trigger failed (${trigRes.status})` }, 500);
    return jsonResponse({ doc_name: docName, status: 'triggered' });
  }

  let rawText;
  try {
    const bytes = Uint8Array.from(atob(content_base64), c => c.charCodeAt(0));
    rawText = new TextDecoder('utf-8').decode(bytes);
  } catch (_) {
    return jsonResponse({ error: 'Could not decode file content' }, 400);
  }
  for (const ef of extra_files) {
    try {
      const bytes = Uint8Array.from(atob(ef.content_base64), c => c.charCodeAt(0));
      rawText += '\n\n---\n\n' + new TextDecoder('utf-8').decode(bytes);
    } catch (_) {}
  }

  const ts = timestamp();
  const outPath = `standardised/${docName}_${ts}.md`;

  ctx.waitUntil((async () => {
    try {
      const cleanDoc = await callClaude(
        STANDARDISE_SYSTEM,
        STANDARDISE_PROMPT_TPL.replace('{raw_text}', rawText.slice(0, 10000)),
        env, 3000
      );
      await uploadToGitHub(outPath, encodeBase64(cleanDoc), env, `pipeline: standardise ${docName}`);
    } catch (_) {}
  })());

  return jsonResponse({ doc_name: docName, status: 'started' });
}

// GET /api/poll-standard?doc_name=xxx — poll standardised/ folder for result
async function handlePollStandard(request, env) {
  const docName = new URL(request.url).searchParams.get('doc_name');
  if (!docName) return jsonResponse({ error: 'Missing doc_name' }, 400);

  const listRes = await ghFetch('contents/standardised', env);
  if (!listRes.ok) return jsonResponse({ status: 'waiting' });

  const files = await listRes.json();
  if (!Array.isArray(files)) return jsonResponse({ status: 'waiting' });

  const match = files.find(
    f => f.name.startsWith(docName) && f.name.endsWith('.md') && !f.name.includes('gitkeep')
  );
  if (!match) return jsonResponse({ status: 'waiting' });

  const rawRes = await fetch(match.download_url, { headers: { 'User-Agent': 'PO-Bot-Worker' } });
  if (!rawRes.ok) return jsonResponse({ status: 'waiting' });

  const content = await rawRes.text();
  const stdName = match.name.replace(/\.md$/, '');
  return jsonResponse({ status: 'ready', std_path: match.path, std_name: stdName, content });
}

// POST /api/generate — call Claude directly in background, no GitHub Actions
async function handleGenerate(request, env, ctx) {
  const body = await request.json().catch(() => null);
  if (!body || !body.std_path)
    return jsonResponse({ error: 'Missing std_path' }, 400);

  const { std_path, std_content_base64 } = body;

  // Decode the (possibly user-edited) standardised doc
  let docText;
  if (std_content_base64) {
    try {
      const bytes = Uint8Array.from(atob(std_content_base64), c => c.charCodeAt(0));
      docText = new TextDecoder('utf-8').decode(bytes);
    } catch (_) {}
  }
  if (!docText) {
    // Fall back to reading from GitHub
    const res = await ghFetch(`contents/${std_path}`, env);
    if (!res.ok) return jsonResponse({ error: 'Could not read standardised doc' }, 500);
    const data = await res.json();
    const bytes = Uint8Array.from(atob((data.content || '').replace(/\n/g, '')), c => c.charCodeAt(0));
    docText = new TextDecoder('utf-8').decode(bytes);
  }

  const docName = std_path.split('/').pop().replace(/\.md$/, '');
  const hasAnthropicKey = env.ANTHROPIC_API_KEY && !env.ANTHROPIC_API_KEY.startsWith('placeholder') && env.ANTHROPIC_API_KEY.startsWith('sk-');

  if (!hasAnthropicKey) {
    // GitHub Actions fallback
    if (std_content_base64) {
      const upRes = await uploadToGitHub(std_path, std_content_base64, env, `docs: update standardised doc`);
      if (!upRes.ok) return jsonResponse({ error: `Update failed (${upRes.status})` }, 500);
    }
    const wf = await getWorkflow(env);
    if (!wf) return jsonResponse({ error: 'Workflow not found.' }, 500);
    const trigRes = await ghFetch(`actions/workflows/${wf.id}/dispatches`, env, {
      method: 'POST',
      body: JSON.stringify({ ref: 'main', inputs: { doc_path: std_path, mode: 'generate' } }),
    });
    if (!trigRes.ok) return jsonResponse({ error: `Trigger failed (${trigRes.status})` }, 500);
    return jsonResponse({ doc_name: docName, status: 'triggered' });
  }

  const ts = timestamp();
  const outPath = `backlog/${docName}_${ts}.json`;

  ctx.waitUntil((async () => {
    try {
      let raw = await callClaude(
        BACKLOG_SYSTEM,
        BACKLOG_PROMPT_TPL.replace('{doc_text}', docText.slice(0, 12000)),
        env, 4096
      );
      if (raw.startsWith('```')) {
        const parts = raw.split('```');
        raw = parts[1].startsWith('json') ? parts[1].slice(4) : parts[1];
      }
      const backlog = JSON.parse(raw.trim());
      backlog._meta = { source_document: std_path, generated_at: new Date().toISOString(), status: 'pending_review' };
      await uploadToGitHub(outPath, encodeBase64(JSON.stringify(backlog, null, 2)), env, `pipeline: generate backlog ${docName}`);
    } catch (_) {}
  })());

  return jsonResponse({ doc_name: docName, status: 'started' });
}

// GET /api/get-standard-doc?filename={filename} — fetch standardised doc and return as plain text
async function handleGetStandardDoc(request, env) {
  const filename = new URL(request.url).searchParams.get('filename');
  if (!filename) return new Response('Missing filename', { status: 400, headers: CORS_HEADERS });

  const res = await ghFetch(`contents/standardised/${filename}`, env);
  if (!res.ok) return new Response('Not found', { status: 404, headers: CORS_HEADERS });

  const data = await res.json();
  const content = atob((data.content || '').replace(/\n/g, ''));
  return new Response(content, {
    status: 200,
    headers: { 'Content-Type': 'text/plain; charset=utf-8', ...CORS_HEADERS },
  });
}

// GET /api/teams — return teams config from Worker secret
async function handleGetTeams(request, env) {
  try {
    const config = JSON.parse(env.TEAMS_CONFIG);
    const withEmails = checkPin(request, env);
    return jsonResponse({
      po: withEmails ? config.po : { name: config.po?.name },
      teams: (config.teams || []).map(t => ({
        id: t.id,
        name: t.name,
        primary: t.primary,
        also_covers: t.also_covers,
        color: t.color,
        member_count: (t.members || []).length,
        members: (t.members || []).map(m =>
          withEmails ? m : { name: m.name, title: m.title }
        ),
      })),
    });
  } catch {
    return jsonResponse({ error: 'Teams config not available' }, 500);
  }
}

// Assign a team responsibility label based on story title + epic name
function teamLabelFor(text) {
  const t = text.toLowerCase();
  if (/develop|code|unity|gameplay|scene|ui|deploy|store|build|playstore/.test(t)) return 'unity_dev';
  if (/3d|model|texture|animation|art|render/.test(t)) return '3d_team';
  if (/backend|api|server|database|auth/.test(t)) return 'backend_team';
  if (/audio|sound|music/.test(t)) return '3d_team';
  return 'unity_dev';
}

// GET /api/poll?doc_name=xxx — poll backlog/ folder for result
async function handlePoll(request, env) {
  const docName = new URL(request.url).searchParams.get('doc_name');
  if (!docName) return jsonResponse({ error: 'Missing doc_name' }, 400);

  const listRes = await ghFetch('contents/backlog', env);
  if (!listRes.ok) return jsonResponse({ status: 'waiting' });

  const files = await listRes.json();
  if (!Array.isArray(files)) return jsonResponse({ status: 'waiting' });

  const match = files.find(
    f => f.name.startsWith(docName) && f.name.endsWith('.json') && !f.name.includes('gitkeep')
  );
  if (!match) return jsonResponse({ status: 'waiting' });

  const rawRes = await fetch(match.download_url, { headers: { 'User-Agent': 'PO-Bot-Worker' } });
  if (!rawRes.ok) return jsonResponse({ status: 'waiting' });

  const backlog = await rawRes.json();
  return jsonResponse({ status: 'ready', backlog, filename: match.name });
}

// POST /api/approve — create Jira project and push stories
async function handleApprove(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.backlog) return jsonResponse({ error: 'Missing backlog' }, 400);

  const { backlog, project_members = [] } = body;
  const jiraBase = `https://${env.JIRA_DOMAIN}/rest/api/3`;
  const auth = btoa(`${env.JIRA_EMAIL}:${env.JIRA_TOKEN}`);
  const jHeaders = {
    Authorization: `Basic ${auth}`,
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  const meRes = await fetch(`https://${env.JIRA_DOMAIN}/rest/api/3/myself`, { headers: jHeaders });
  if (!meRes.ok)
    return jsonResponse({ error: `Jira auth failed (${meRes.status}). Check your Jira token.` }, 401);
  const me = await meRes.json();

  // Create project
  const ts = Date.now().toString().slice(-5);
  const rawKey = (backlog.project_name || 'PROJ')
    .replace(/[^a-zA-Z0-9 ]/g, '')
    .split(' ').filter(Boolean)
    .map(w => w[0].toUpperCase()).join('').slice(0, 4) || 'PROJ';
  const projectKey = rawKey + ts;
  const projectName = (backlog.project_name || 'Product Backlog') + ' (' + ts + ')';

  const projRes = await fetch(jiraBase + '/project', {
    method: 'POST', headers: jHeaders,
    body: JSON.stringify({
      key: projectKey,
      name: projectName,
      projectTypeKey: 'software',
      projectTemplateKey: 'com.pyxis.greenhopper.jira:gh-simplified-agility-scrum',
      description: backlog.vision || '',
      leadAccountId: me.accountId,
    }),
  });

  if (!projRes.ok) {
    const err = await projRes.text();
    return jsonResponse({ error: 'Jira project creation failed: ' + err.slice(0, 300) }, 500);
  }
  const proj = await projRes.json();
  const finalKey = proj.key;

  // Discover issue type name: prefer Story, fall back to Task, then first non-subtask
  const metaRes = await fetch(
    jiraBase + '/issue/createmeta?projectKeys=' + finalKey + '&expand=projects.issuetypes',
    { headers: jHeaders }
  );
  let storyTypeName = 'Story';
  if (metaRes.ok) {
    const meta = await metaRes.json();
    const metaProj = (meta.projects || [])[0];
    if (metaProj) {
      const found =
        (metaProj.issuetypes || []).find(t => t.name === 'Story' && !t.subtask) ||
        (metaProj.issuetypes || []).find(t => t.name === 'Task'  && !t.subtask) ||
        (metaProj.issuetypes || []).find(t => !t.subtask);
      if (found) storyTypeName = found.name;
    }
  }

  // Build team → Jira accountId map — only for selected members
  const teamAccountIds = {}; // teamId → accountId
  try {
    const teamsConfig = JSON.parse(env.TEAMS_CONFIG || '{}');
    for (const team of (teamsConfig.teams || [])) {
      // Find first member of this team whose email was selected in the Members screen
      const selectedMember = (team.members || []).find(m => project_members.includes(m.email));
      if (!selectedMember?.email) continue;
      const searchRes = await fetch(
        `${jiraBase}/user/search?query=${encodeURIComponent(selectedMember.email)}&maxResults=1`,
        { headers: jHeaders }
      );
      if (searchRes.ok) {
        const users = await searchRes.json();
        if (users.length > 0) teamAccountIds[team.id] = users[0].accountId;
      }
    }
  } catch (_) {}

  // Create stories — track issue keys by sprint number for sprint assignment
  let issuesCreated = 0;
  const errors = [];
  const issueKeysBySprint = {};

  for (const epic of backlog.epics) {
    for (const story of epic.stories) {
      const acLines = (story.criteria || []).map(ac => `• ${ac}`).join('\n');
      const epicLabel = epic.name.replace(/[^a-zA-Z0-9]/g, '_');
      const priorityLabel = (story.priority || 'Could_Have').replace(/ /g, '_');

      const teamId = story.team || teamLabelFor(`${story.title} ${epic.name}`);
      const assigneeAccountId = teamAccountIds[teamId] || null;

      const issueFields = {
        project: { key: finalKey },
        summary: story.title,
        description: {
          type: 'doc', version: 1,
          content: [
            { type: 'paragraph', content: [{ type: 'text', text: `Epic: ${epic.name}`, marks: [{ type: 'strong' }] }] },
            { type: 'paragraph', content: [{ type: 'text', text: `Acceptance Criteria:\n${acLines}` }] },
            { type: 'paragraph', content: [{ type: 'text', text: `Sprint: ${story.sprint} | Points: ${story.points} | Priority: ${story.priority} | Team: ${teamId}` }] },
          ],
        },
        issuetype: { name: storyTypeName },
        labels: [epicLabel, priorityLabel, `Sprint_${story.sprint}`, teamId],
      };
      if (assigneeAccountId) issueFields.assignee = { accountId: assigneeAccountId };

      const sRes = await fetch(`${jiraBase}/issue`, {
        method: 'POST', headers: jHeaders,
        body: JSON.stringify({ fields: issueFields }),
      });
      if (sRes.ok) {
        issuesCreated++;
        const created = await sRes.json();
        const sn = story.sprint;
        if (!issueKeysBySprint[sn]) issueKeysBySprint[sn] = [];
        issueKeysBySprint[sn].push(created.key);
        // Add assignee as watcher — triggers Jira email notification to them
        if (assigneeAccountId) {
          fetch(`${jiraBase}/issue/${created.key}/watchers`, {
            method: 'POST', headers: jHeaders,
            body: JSON.stringify(assigneeAccountId),
          }).catch(() => {});
        }
      } else {
        const e = await sRes.text();
        errors.push(`${story.id}: ${e.substring(0, 100)}`);
      }
    }
  }

  if (issuesCreated === 0 && errors.length > 0) {
    return jsonResponse({ error: `Stories failed: ${errors[0]}` }, 500);
  }

  // Invite only the selected project members
  let totalInvited = 0;
  try {
    const emails = project_members.filter(Boolean);
    if (emails.length > 0) {
      const invRes = await fetch(`${jiraBase}/project/${finalKey}/role/10002`, {
        method: 'POST', headers: jHeaders,
        body: JSON.stringify({ emailAddress: emails }),
      });
      if (invRes.ok) totalInvited = emails.length;
    }
  } catch (_) {}

  // Create agile sprints and assign stories — best-effort, non-blocking
  let sprintsCreated = 0;
  try {
    const boardRes = await fetch(
      `https://${env.JIRA_DOMAIN}/rest/agile/1.0/board?projectKeyOrId=${finalKey}`,
      { headers: jHeaders }
    );
    if (boardRes.ok) {
      const boardData = await boardRes.json();
      const board = (boardData.values || [])[0];
      if (board) {
        const boardId = board.id;

        // Unique sprint numbers from the backlog, sorted ascending
        const sprintNums = [...new Set(
          backlog.epics.flatMap(e => (e.stories||[]).map(s => Number(s.sprint)))
        )].filter(n => !isNaN(n) && n > 0).sort((a, b) => a - b);

        // Base date: today at 09:00 UTC
        const today = new Date();
        today.setUTCHours(9, 0, 0, 0);

        const sprintIdMap = {};

        for (const n of sprintNums) {
          const start = new Date(today);
          start.setUTCDate(today.getUTCDate() + (n - 1) * 14);
          const end = new Date(today);
          end.setUTCDate(today.getUTCDate() + n * 14);

          const spRes = await fetch(
            `https://${env.JIRA_DOMAIN}/rest/agile/1.0/sprint`,
            {
              method: 'POST', headers: jHeaders,
              body: JSON.stringify({
                name: `Sprint ${n}`,
                originBoardId: boardId,
                startDate: start.toISOString().replace(/\.\d{3}Z$/, '.000Z'),
                endDate: end.toISOString().replace(/\.\d{3}Z$/, '.000Z'),
                goal: `Sprint ${n} stories`,
              }),
            }
          );
          if (spRes.ok) {
            const sp = await spRes.json();
            sprintIdMap[n] = sp.id;
            sprintsCreated++;
          }
        }

        // Move issues into their sprints
        for (const [sprintNumStr, issueKeys] of Object.entries(issueKeysBySprint)) {
          const sprintId = sprintIdMap[Number(sprintNumStr)];
          if (!sprintId || issueKeys.length === 0) continue;
          await fetch(
            `https://${env.JIRA_DOMAIN}/rest/agile/1.0/sprint/${sprintId}/issue`,
            {
              method: 'POST', headers: jHeaders,
              body: JSON.stringify({ issues: issueKeys }),
            }
          );
        }
      }
    }
  } catch (_) {}

  return jsonResponse({
    project_key: finalKey,
    issues_created: issuesCreated,
    jira_url: `https://${env.JIRA_DOMAIN}/jira/software/projects/${finalKey}/board`,
    team_invited: totalInvited,
    sprints_created: sprintsCreated,
  });
}

// PUT /api/update-teams — update TEAMS_CONFIG Cloudflare secret
async function handleUpdateTeams(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.teams) return jsonResponse({ error: 'Missing teams' }, 400);

  const updated = JSON.stringify({ po: body.po || {}, teams: body.teams });
  const r = await fetch(
    `https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/workers/scripts/po-bot-worker/secrets`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${env.CF_API_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name: 'TEAMS_CONFIG', text: updated, type: 'secret_text' }),
    }
  );
  if (!r.ok) {
    const err = await r.text();
    return jsonResponse({ error: 'Failed to update roster: ' + err.slice(0, 200) }, 500);
  }
  return jsonResponse({ success: true });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const path = new URL(request.url).pathname;

    if (path === '/api/verify-pin' && request.method === 'POST') {
      const body = await request.json().catch(() => ({}));
      return body.pin === env.APP_PIN
        ? jsonResponse({ ok: true })
        : jsonResponse({ ok: false }, 401);
    }

    if (!checkPin(request, env)) {
      return jsonResponse({ error: 'Invalid PIN' }, 401);
    }

    if (path === '/api/get-standard-doc' && request.method === 'GET') return handleGetStandardDoc(request, env);
    if (path === '/api/teams'        && request.method === 'GET')  return handleGetTeams(request, env);
    if (path === '/api/standardise'  && request.method === 'POST') return handleStandardise(request, env, ctx);
    if (path === '/api/poll-standard'&& request.method === 'GET')  return handlePollStandard(request, env);
    if (path === '/api/generate'     && request.method === 'POST') return handleGenerate(request, env, ctx);
    if (path === '/api/poll'         && request.method === 'GET')  return handlePoll(request, env);
    if (path === '/api/approve'      && request.method === 'POST') return handleApprove(request, env);
    if (path === '/api/update-teams' && request.method === 'POST') return handleUpdateTeams(request, env);

    return jsonResponse({ error: 'Not found' }, 404);
  },
};
