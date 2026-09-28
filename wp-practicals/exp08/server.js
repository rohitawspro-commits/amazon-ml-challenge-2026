// CampusLibrary API - custom authentication and authorization middleware (no auth libraries).
const express = require('express');
const crypto = require('crypto');

const PORT = 3008;
const SECRET = process.env.TOKEN_SECRET || crypto.randomBytes(32).toString('hex');
const TOKEN_TTL = 15 * 60;                        // seconds

const hash = (pw, salt) => crypto.scryptSync(pw, salt, 32).toString('hex');
const users = [
  { id: 1, username: 'rohit',  role: 'student',   salt: 's1' },
  { id: 2, username: 'priya',  role: 'student',   salt: 's2' },
  { id: 3, username: 'mehta',  role: 'librarian', salt: 's3' },
  { id: 4, username: 'admin',  role: 'admin',     salt: 's4' }
].map(u => ({ ...u, hash: hash(u.username + '@123', u.salt) }));

const books = [
  { id: 101, title: 'Clean Code', copies: 3 },
  { id: 102, title: 'Operating System Concepts', copies: 2 }
];
const loans = [{ userId: 1, bookId: 101, due: '2026-10-12' }, { userId: 2, bookId: 102, due: '2026-10-05' }];

// ---- token helpers: base64url(payload) + "." + HMAC-SHA256 signature ----
const b64 = s => Buffer.from(s).toString('base64url');
function sign(user) {
  const payload = b64(JSON.stringify({ sub: user.id, role: user.role, exp: Math.floor(Date.now() / 1000) + TOKEN_TTL }));
  const sig = crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');
  return `${payload}.${sig}`;
}
function verify(token) {
  const [payload, sig] = String(token).split('.');
  if (!payload || !sig) throw new Error('malformed token');
  const expected = crypto.createHmac('sha256', SECRET).update(payload).digest();
  const given = Buffer.from(sig, 'base64url');
  if (given.length !== expected.length || !crypto.timingSafeEqual(given, expected)) throw new Error('bad signature');
  const data = JSON.parse(Buffer.from(payload, 'base64url').toString());
  if (data.exp < Date.now() / 1000) throw new Error('token expired');
  return data;
}

// ---- middleware ----
function requestLogger(req, res, next) {
  req.id = crypto.randomUUID().slice(0, 8);
  const start = process.hrtime.bigint();
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - start) / 1e6;
    const who = req.user ? `${req.user.username}(${req.user.role})` : 'guest';
    console.log(`[${req.id}] ${req.method.padEnd(6)} ${req.originalUrl.padEnd(18)} -> ${res.statusCode}  ${who.padEnd(17)} ${ms.toFixed(1)} ms`);
  });
  next();
}

function authenticate(req, res, next) {                // who are you? (optional)
  const header = req.get('Authorization') || '';
  if (!header.startsWith('Bearer ')) return next();   // guest request
  try {
    const data = verify(header.slice(7));
    req.user = users.find(u => u.id === data.sub);
    if (!req.user) throw new Error('unknown user');
    next();
  } catch (err) {
    res.status(401).json({ error: `Invalid token: ${err.message}` });
  }
}

const requireLogin = (req, res, next) =>
  req.user ? next() : res.status(401).json({ error: 'Login required' });

const authorize = (...roles) => (req, res, next) =>
  roles.includes(req.user.role) ? next()
    : res.status(403).json({ error: `Role '${req.user.role}' cannot ${req.method} ${req.baseUrl}${req.path}` });

// Owner of the resource, or one of the given staff roles.
const selfOr = (...roles) => (req, res, next) =>
  Number(req.params.userId) === req.user.id || roles.includes(req.user.role) ? next()
    : res.status(403).json({ error: 'You can only view your own loans' });

function rateLimit(max, windowMs) {                     // simple fixed-window limiter per IP
  const hits = new Map();
  return (req, res, next) => {
    const now = Date.now(), rec = hits.get(req.ip) || { n: 0, start: now };
    if (now - rec.start > windowMs) { rec.n = 0; rec.start = now; }
    rec.n++; hits.set(req.ip, rec);
    rec.n > max ? res.status(429).json({ error: 'Too many login attempts, wait a minute' }) : next();
  };
}

// ---- app ----
const app = express();
app.use(requestLogger, express.json(), authenticate);

app.post('/api/login', rateLimit(5, 60_000), (req, res) => {
  const { username, password } = req.body || {};
  const user = users.find(u => u.username === username);
  if (!user || hash(String(password), user.salt) !== user.hash)
    return res.status(401).json({ error: 'Wrong username or password' });
  res.json({ token: sign(user), expiresIn: TOKEN_TTL });
});

app.get('/api/books', (req, res) => res.json(books));                               // public
app.get('/api/me', requireLogin, ({ user }, res) => res.json({ id: user.id, username: user.username, role: user.role }));
app.get('/api/loans/:userId', requireLogin, selfOr('librarian', 'admin'),
  (req, res) => res.json(loans.filter(l => l.userId === Number(req.params.userId))));
app.post('/api/books', requireLogin, authorize('librarian', 'admin'), (req, res) => {
  const book = { id: 100 + books.length + 1, title: req.body.title, copies: req.body.copies || 1 };
  books.push(book);
  res.status(201).json(book);
});
app.delete('/api/books/:id', requireLogin, authorize('admin'), (req, res) => {
  const i = books.findIndex(b => b.id === Number(req.params.id));
  if (i === -1) return res.status(404).json({ error: 'Book not found' });
  res.json(books.splice(i, 1)[0]);
});

app.use((req, res) => res.status(404).json({ error: 'Route not found' }));
app.use((err, req, res, next) => {                                                  // error handler
  console.error(`[${req.id}] ${err.message}`);
  res.status(err.status || 500).json({ error: err.type === 'entity.parse.failed' ? 'Invalid JSON body' : 'Server error' });
});

app.listen(PORT, () => console.log(`CampusLibrary API on http://localhost:${PORT}`));
