const logEl = document.getElementById('log');
const locationEl = document.getElementById('location');
const inventoryEl = document.getElementById('inventory');
const entitiesEl = document.getElementById('entities');
const debugEl = document.getElementById('debug');

function addLog(text, label = 'Engine') {
  const div = document.createElement('div');
  div.className = 'entry';
  div.innerHTML = `<strong>${label}:</strong> ${text}`;
  logEl.prepend(div);
}

function render(state) {
  if (state.error) {
    addLog(state.error, 'Error');
    return;
  }

  if (state.narrative) addLog(state.narrative);

  const w = state.world_state || {};
  locationEl.textContent = `Location: ${w.current_location ?? 'Unknown'}`;
  inventoryEl.textContent = `Inventory: ${(w.inventory || []).join(', ') || '(empty)'}`;

  entitiesEl.innerHTML = '';
  (state.known_entities || []).forEach((e) => {
    const li = document.createElement('li');
    li.textContent = `${e.name} (${e.type})`;
    entitiesEl.appendChild(li);
  });

  debugEl.textContent = JSON.stringify(state.debug || {}, null, 2);
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
