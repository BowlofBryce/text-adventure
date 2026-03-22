const logEl = document.getElementById('log');
const locationEl = document.getElementById('location');
const inventoryEl = document.getElementById('inventory');
const conditionsEl = document.getElementById('conditions');
const entitiesEl = document.getElementById('entities');
const aiPillsEl = document.getElementById('aiPills');
const fallbackBannerEl = document.getElementById('fallbackBanner');

const debugAiEl = document.getElementById('debugAi');
const debugWorldEl = document.getElementById('debugWorld');
const debugMemoryEl = document.getElementById('debugMemory');

function addLog(text, label = 'Narrator') {
  const div = document.createElement('div');
  div.className = 'entry';
  div.innerHTML = `<strong>${label}:</strong> ${text}`;
  logEl.prepend(div);
}

function renderPills(status = {}, resolution = {}) {
  const connected = !!status.connected;
  const lastSuccess = !!status.last_call_success;
  const fallback = !!status.fallback_active || !!resolution.fallback_used;
  const model = status.model || 'unknown';

  aiPillsEl.innerHTML = '';
  const pills = [
    {label: connected ? 'Local AI Connected' : 'Local AI Offline', cls: connected ? 'ok' : 'warn'},
    {label: `Model: ${model}`, cls: ''},
    {label: lastSuccess ? 'Last Call: Success' : 'Last Call: Failed', cls: lastSuccess ? 'ok' : 'warn'},
    {label: fallback ? 'Fallback Mode Active' : 'Live AI Mode', cls: fallback ? 'warn' : 'ok'},
  ];

  pills.forEach(({label, cls}) => {
    const span = document.createElement('span');
    span.className = `pill ${cls}`;
    span.textContent = label;
    aiPillsEl.appendChild(span);
  });

  if (fallback) {
    fallbackBannerEl.style.display = 'block';
    const reason = status.last_error || resolution.reason || 'Unknown local AI failure.';
    fallbackBannerEl.textContent = `Fallback active: ${reason}`;
  } else {
    fallbackBannerEl.style.display = 'none';
    fallbackBannerEl.textContent = '';
  }
}

function render(state) {
  if (state.error) {
    addLog(state.error, 'Error');
    return;
  }

  if (state.narrative) addLog(state.narrative, state.resolution?.source === 'fallback' ? 'Fallback' : 'Narrator');

  const w = state.world_state || {};
  locationEl.textContent = `Location: ${w.current_location ?? 'Unknown'}`;
  inventoryEl.textContent = `Inventory: ${(w.inventory || []).join(', ') || '(empty)'}`;

  const conditions = w.active_conditions || {};
  const visibleConditions = Object.keys(conditions)
    .filter((k) => !['last_action', 'last_updated_at'].includes(k))
    .map((k) => `${k}: ${conditions[k]}`)
    .join(' · ');
  conditionsEl.textContent = `Conditions: ${visibleConditions || 'none'}`;

  entitiesEl.innerHTML = '';
  (state.known_entities || []).forEach((e) => {
    if (!['npc', 'item', 'location'].includes(e.type)) return;
    const li = document.createElement('li');
    const subtitle = e.type === 'npc' ? (e.state?.attitude || 'neutral') : (e.attributes?.description || e.type);
    li.innerHTML = `<strong>${e.name}</strong><br/><small>${subtitle}</small>`;
    entitiesEl.appendChild(li);
  });

  renderPills(state.ai_status, state.resolution);

  const dbg = state.debug || {};
  debugAiEl.textContent = JSON.stringify(dbg.ai || {}, null, 2);
  debugWorldEl.textContent = JSON.stringify(dbg.world_state || {}, null, 2);
  debugMemoryEl.textContent = JSON.stringify(
    {
      active_memory: dbg.active_memory || [],
      memory_count: dbg.memory?.memory_count,
      active_meaningful_count: dbg.memory?.active_meaningful_count,
      top_memories: dbg.memory?.memories?.slice(0, 8) || [],
    },
    null,
    2,
  );
}

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  return res.json();
}

document.getElementById('newGameBtn').addEventListener('click', async () => {
  const scenarioId = document.getElementById('scenario').value;
  const initialPrompt = document.getElementById('initialPrompt').value;
  const state = await post('/new-game', {scenarioId, initialPrompt});
  render(state);
});

document.getElementById('actionBtn').addEventListener('click', async () => {
  const action = document.getElementById('actionInput').value;
  if (!action.trim()) return;
  addLog(action, 'Player');
  document.getElementById('actionInput').value = '';
  const state = await post('/action', {action});
  render(state);
});

fetch('/state').then((r) => r.json()).then(render);
