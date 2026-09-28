const view = document.getElementById('view');
const clock = document.getElementById('clock');
const banner = document.getElementById('banner');
const pauseBtn = document.getElementById('pause');

const BASE_DELAY = 3000, MAX_DELAY = 30000;
let delay = BASE_DELAY, timer = null, paused = false, controller = null, lastOk = null;

// ---- router: #/ -> overview, #/server/3 -> detail ----
function route() {
  const [, page, id] = location.hash.split('/');
  return page === 'server' ? { name: 'detail', id: Number(id) } : { name: 'overview' };
}

// ---- polling with setTimeout, AbortController and exponential back-off ----
async function poll() {
  clearTimeout(timer);
  controller?.abort();                                   // cancel a request that is still running
  controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  const r = route();
  const url = r.name === 'detail' ? `/api/servers/${r.id}` : '/api/servers';
  try {
    const res = await fetch(url, { signal: controller.signal, cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    r.name === 'detail' ? renderDetail(data) : renderOverview(data.servers);
    lastOk = Date.now(); delay = BASE_DELAY; banner.hidden = true;
  } catch (err) {
    if (err.name === 'AbortError' && !paused) return;    // superseded by a newer poll
    delay = Math.min(delay * 2, MAX_DELAY);
    banner.textContent = `Cannot reach server (${err.message}). Retrying in ${delay / 1000} s...`;
    banner.hidden = false;
  } finally {
    clearTimeout(timeout);
  }
  schedule();
}
function schedule() {
  if (!paused && !document.hidden) timer = setTimeout(poll, delay);
}

// ---- rendering ----
const pct = v => v == null ? '--' : v + '%';
const bar = v => `<div class="bar"><i style="width:${v || 0}%"></i></div>`;

function renderOverview(servers) {
  const counts = servers.reduce((acc, s) => ({ ...acc, [s.status]: (acc[s.status] || 0) + 1 }), {});
  view.innerHTML = `<div class="summary">${['healthy', 'warning', 'critical', 'down']
      .map(k => `<span class="${k}">${k}: ${counts[k] || 0}</span>`).join('')}</div>
    <div class="grid">${servers.map(s => `
      <a class="card" href="#/server/${s.id}">
        <div class="row"><span class="name">${s.name}</span><span class="badge ${s.status}">${s.status}</span></div>
        <div class="region">${s.region}</div>
        <div class="metric">CPU ${pct(s.cpu)}${bar(s.cpu)}</div>
        <div class="metric">Memory ${pct(s.mem)}${bar(s.mem)}</div>
      </a>`).join('')}</div>`;
}

function renderDetail(s) {
  view.innerHTML = `<a href="#/">&larr; All servers</a>
    <div class="row" style="margin-top:12px"><div><div class="big">${s.name}</div><div class="region">${s.region}</div></div>
    <span class="badge ${s.status}">${s.status}</span></div>
    <div class="summary" style="margin-top:12px"><span>CPU ${pct(s.cpu)}</span><span>Memory ${pct(s.mem)}</span>
    <span>Samples ${s.history.length}</span></div>
    <canvas id="chart" width="900" height="220"></canvas>`;
  drawChart(document.getElementById('chart'), s.history);
}

function drawChart(canvas, values) {                    // CPU history as a line chart
  const ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height, pad = 28;
  ctx.strokeStyle = '#1e2b47'; ctx.fillStyle = '#64748b'; ctx.font = '12px system-ui';
  for (const v of [0, 50, 100]) {
    const y = h - pad - (v / 100) * (h - 2 * pad);
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - 10, y); ctx.stroke(); ctx.fillText(v + '%', 0, y + 4);
  }
  ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 2; ctx.beginPath();
  values.forEach((v, i) => {
    const x = pad + i * (w - pad - 10) / (values.length - 1), y = h - pad - (v / 100) * (h - 2 * pad);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

// ---- events ----
setInterval(() => {
  clock.textContent = paused ? 'paused' : lastOk ? `updated ${Math.round((Date.now() - lastOk) / 1000)} s ago` : 'connecting...';
}, 1000);
pauseBtn.addEventListener('click', () => {
  paused = !paused;
  pauseBtn.textContent = paused ? 'Resume' : 'Pause';
  paused ? (clearTimeout(timer), controller?.abort()) : poll();
});
document.addEventListener('visibilitychange', () => {   // stop polling in a background tab
  if (document.hidden) clearTimeout(timer); else if (!paused) poll();
});
window.addEventListener('hashchange', poll);
poll();
