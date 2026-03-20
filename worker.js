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

// Find the step1/generate workflow
async function getWorkflow(env) {
  const wfRes = await ghFetch('actions/workflows', env);
  if (!wfRes.ok) return null;
  const wfData = await wfRes.json();
  return (wfData.workflows || []).find(
    w => w.path.includes('step1') || w.path.includes('generate')
  ) || null;
}

// POST /api/standardise — upload files and trigger standardise workflow
async function handleStandardise(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.filename || !body.content_base64)
    return jsonResponse({ error: 'Missing filename or content_base64' }, 400);

  const { filename, content_base64, extra_files = [] } = body;
  const primaryPath = `docs/${filename}`;

  const upRes = await uploadToGitHub(primaryPath, content_base64, env, `docs: upload ${filename}`);
  if (!upRes.ok) return jsonResponse({ error: `Upload failed (${upRes.status})` }, 500);

  // Upload any extra files for merging
  const extraPaths = [];
  for (const ef of extra_files) {
    const p = `docs/${ef.filename}`;
    const r = await uploadToGitHub(p, ef.content_base64, env, `docs: upload ${ef.filename}`);
    if (r.ok) extraPaths.push(p);
  }

  const wf = await getWorkflow(env);
  if (!wf) return jsonResponse({ error: 'Workflow not found in GitHub Actions.' }, 500);

  const trigRes = await ghFetch(`actions/workflows/${wf.id}/dispatches`, env, {
    method: 'POST',
    body: JSON.stringify({
      ref: 'main',
      inputs: {
        doc_path: primaryPath,
        mode: 'standardise',
        extra_files: extraPaths.join(','),
      },
    }),
  });
  if (!trigRes.ok) return jsonResponse({ error: `Trigger failed (${trigRes.status})` }, 500);

  const docName = filename.replace(/\.[^.]+$/, '');
  return jsonResponse({ doc_name: docName, status: 'triggered' });
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

// POST /api/generate — trigger generate workflow using standardised doc
async function handleGenerate(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !body.std_path)
    return jsonResponse({ error: 'Missing std_path' }, 400);

  const { std_path, std_content_base64 } = body;

  // If user edited the standardised document, save the edits first
  if (std_content_base64) {
    const upRes = await uploadToGitHub(
      std_path, std_content_base64, env, `docs: update standardised doc`
    );
    if (!upRes.ok) return jsonResponse({ error: `Update failed (${upRes.status})` }, 500);
  }

  const wf = await getWorkflow(env);
  if (!wf) return jsonResponse({ error: 'Workflow not found in GitHub Actions.' }, 500);

  const trigRes = await ghFetch(`actions/workflows/${wf.id}/dispatches`, env, {
    method: 'POST',
    body: JSON.stringify({
      ref: 'main',
      inputs: { doc_path: std_path, mode: 'generate' },
    }),
  });
  if (!trigRes.ok) return jsonResponse({ error: `Trigger failed (${trigRes.status})` }, 500);

  // doc_name for polling = std filename without .md
  const docName = std_path.split('/').pop().replace(/\.md$/, '');
  return jsonResponse({ doc_name: docName, status: 'triggered' });
}

// GET /api/teams — return teams config from GitHub (base64 decode)
async function handleGetTeams(request, env) {
  const res = await ghFetch('contents/config/teams.json', env);
  if (!res.ok) return jsonResponse({ error: 'Teams config not found' }, 404);
  const data = await res.json();
  const decoded = atob(data.content.replace(/\n/g, ''));
  return jsonResponse(JSON.parse(decoded));
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

  const { backlog, selected_teams = [] } = body;
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

  // Create stories
  let issuesCreated = 0;
  const errors = [];
  for (const epic of backlog.epics) {
    for (const story of epic.stories) {
      const acLines = (story.acceptance_criteria || []).map(ac => `• ${ac}`).join('\n');
      const epicLabel = epic.name.replace(/[^a-zA-Z0-9]/g, '_');
      const priorityLabel = (story.priority || 'Could_Have').replace(/ /g, '_');

      const sRes = await fetch(`${jiraBase}/issue`, {
        method: 'POST', headers: jHeaders,
        body: JSON.stringify({
          fields: {
            project: { key: finalKey },
            summary: `[${story.id}] ${story.title}`,
            description: {
              type: 'doc', version: 1,
              content: [
                { type: 'paragraph', content: [{ type: 'text', text: `Epic: ${epic.name}`, marks: [{ type: 'strong' }] }] },
                { type: 'paragraph', content: [{ type: 'text', text: story.user_story || '', marks: [{ type: 'em' }] }] },
                { type: 'paragraph', content: [{ type: 'text', text: `Acceptance Criteria:\n${acLines}` }] },
                { type: 'paragraph', content: [{ type: 'text', text: `Sprint: ${story.sprint} | Points: ${story.story_points} | Priority: ${story.priority}` }] },
              ],
            },
            issuetype: { name: storyTypeName },
            labels: [epicLabel, priorityLabel, `Sprint_${story.sprint}`, teamLabelFor(`${story.title} ${epic.name}`)],
          },
        }),
      });
      if (sRes.ok) {
        issuesCreated++;
      } else {
        const e = await sRes.text();
        errors.push(`${story.id}: ${e.substring(0, 100)}`);
      }
    }
  }

  if (issuesCreated === 0 && errors.length > 0) {
    return jsonResponse({ error: `Stories failed: ${errors[0]}` }, 500);
  }

  // Invite selected teams — best-effort, never fails the whole request
  let totalInvited = 0;
  if (selected_teams.length > 0) {
    const cfgRes = await ghFetch('contents/config/teams.json', env);
    if (cfgRes.ok) {
      const cfgData = await cfgRes.json();
      const teamsConfig = JSON.parse(atob(cfgData.content.replace(/\n/g, '')));
      for (const teamId of selected_teams) {
        const team = (teamsConfig.teams || []).find(t => t.id === teamId);
        if (!team || !team.members || team.members.length === 0) continue;
        const emails = team.members.map(m => m.email).filter(Boolean);
        if (emails.length === 0) continue;
        await fetch(`${jiraBase}/project/${finalKey}/role/10002`, {
          method: 'POST', headers: jHeaders,
          body: JSON.stringify({ emailAddress: emails }),
        });
        totalInvited += emails.length;
      }
    }
  }

  return jsonResponse({
    project_key: finalKey,
    issues_created: issuesCreated,
    jira_url: `https://${env.JIRA_DOMAIN}/jira/software/projects/${finalKey}/board`,
    team_invited: totalInvited,
  });
}

export default {
  async fetch(request, env) {
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

    if (path === '/api/teams'        && request.method === 'GET')  return handleGetTeams(request, env);
    if (path === '/api/standardise'  && request.method === 'POST') return handleStandardise(request, env);
    if (path === '/api/poll-standard'&& request.method === 'GET')  return handlePollStandard(request, env);
    if (path === '/api/generate'     && request.method === 'POST') return handleGenerate(request, env);
    if (path === '/api/poll'         && request.method === 'GET')  return handlePoll(request, env);
    if (path === '/api/approve'      && request.method === 'POST') return handleApprove(request, env);

    return jsonResponse({ error: 'Not found' }, 404);
  },
};
