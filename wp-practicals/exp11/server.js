// ServerPulse - REST API with simulated server metrics, plus the static SPA.
const express = require('express');
const path = require('path');

const PORT = 3011;
const HISTORY = 30;
const servers = [
  ['web-01', 'Mumbai'], ['web-02', 'Mumbai'], ['api-01', 'Pune'],
  ['db-01', 'Pune'], ['cache-01', 'Hyderabad'], ['worker-01', 'Chennai']
].map(([name, region], i) => ({ id: i + 1, name, region, base: [35, 45, 60, 40, 78, 50][i],
                               cpu: 40, mem: 35 + i * 8, history: [], down: false }));

const clamp = v => Math.max(1, Math.min(99, v));
function tick() {                                        // new reading every 2 s
  for (const s of servers) {
    s.cpu = clamp(Math.round(s.cpu + (s.base - s.cpu) * 0.2 + (Math.random() - 0.5) * 16));   // random walk around base
    s.mem = clamp(Math.round(s.mem + (Math.random() - 0.5) * 5));
    s.down = s.name === 'worker-01' ? Math.random() < 0.5 : false;   // one flaky server
    s.history.push(s.down ? 0 : s.cpu);
    if (s.history.length > HISTORY) s.history.shift();
  }
}
for (let i = 0; i < HISTORY; i++) tick();
setInterval(tick, 2000);

const status = s => s.down ? 'down' : s.cpu > 85 || s.mem > 90 ? 'critical' : s.cpu > 70 ? 'warning' : 'healthy';
const summary = s => ({ id: s.id, name: s.name, region: s.region, cpu: s.down ? null : s.cpu,
                        mem: s.down ? null : s.mem, status: status(s) });

const app = express();
app.use(express.static(path.join(__dirname, 'public')));
app.get('/api/servers', (req, res) =>
  res.json({ time: new Date().toISOString(), servers: servers.map(summary) }));
app.get('/api/servers/:id', (req, res) => {
  const s = servers.find(x => x.id === Number(req.params.id));
  if (!s) return res.status(404).json({ error: 'No such server' });
  res.json({ ...summary(s), history: s.history });
});
app.listen(PORT, () => console.log(`ServerPulse on http://localhost:${PORT}`));
