// Usage: node seed.js [--posts 40] [--seed 7] [--db codejournal.db]
const { DatabaseSync } = require('node:sqlite');
const fs = require('fs');
const path = require('path');

const args = Object.fromEntries(process.argv.slice(2).join(' ').split('--').filter(Boolean)
  .map(s => s.trim().split(/\s+/)));
const POSTS = Number(args.posts || 40);
const dbFile = path.join(__dirname, args.db || 'codejournal.db');

// mulberry32: small seeded random generator, same --seed gives the same data every time
let s = Number(args.seed || 7) >>> 0;
const rand = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const pick = arr => arr[Math.floor(rand() * arr.length)];
const int = (a, b) => a + Math.floor(rand() * (b - a + 1));
const daysAgo = n => new Date(Date.UTC(2026, 8, 28) - n * 864e5).toISOString().slice(0, 10);
const slugify = t => t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

const AUTHORS = [['rohitp', 'Rohit Pujari'], ['sneha_k', 'Sneha Kulkarni'], ['arjun.dev', 'Arjun Nair'],
                 ['farah', 'Farah Khan'], ['vikram', 'Vikram Joshi']];
const TAGS = ['javascript', 'nodejs', 'css', 'sql', 'react', 'security', 'career', 'devops'];
const TOPICS = ['Understanding', 'A Beginner Guide to', '5 Mistakes in', 'Deep Dive into', 'Why I Switched to', 'Testing'];
const SUBJECTS = ['Async/Await', 'CSS Grid', 'SQL Joins', 'React Hooks', 'JWT Tokens', 'Docker Volumes',
                  'Express Middleware', 'Git Rebase', 'Flexbox', 'Database Indexes'];
const NAMES = ['Aman', 'Pooja', 'Kiran', 'Neel', 'Divya', 'Sahil', 'Meera'];
const REMARKS = ['Very clear explanation, thanks!', 'Can you add an example with error handling?',
                 'This fixed my bug.', 'Which version of Node did you use?', 'Bookmarked for exams.'];
const REPLIES = ['Good question - I will update the post.', 'Node 22, but it works on 20 too.', 'Glad it helped!'];

if (fs.existsSync(dbFile)) fs.unlinkSync(dbFile);                  // start from an empty file
const db = new DatabaseSync(dbFile);
db.exec(fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8'));

const ins = {
  author:  db.prepare('INSERT INTO authors (username, full_name, email, joined_on) VALUES (?, ?, ?, ?)'),
  tag:     db.prepare('INSERT INTO tags (name) VALUES (?)'),
  post:    db.prepare(`INSERT INTO posts (author_id, title, slug, body, status, views, published_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)`),
  postTag: db.prepare('INSERT OR IGNORE INTO post_tags (post_id, tag_id) VALUES (?, ?)'),
  comment: db.prepare('INSERT INTO comments (post_id, parent_id, name, body, created_at) VALUES (?, ?, ?, ?, ?)')
};

const t0 = performance.now();
const count = { authors: 0, tags: 0, posts: 0, post_tags: 0, comments: 0 };
db.exec('BEGIN');                                                  // one transaction for all rows
try {
  AUTHORS.forEach(([u, n], i) => { ins.author.run(u, n, `${u.replace(/\W/g, '')}@codejournal.dev`, daysAgo(400 - i * 30)); count.authors++; });
  TAGS.forEach(t => { ins.tag.run(t); count.tags++; });
  const used = new Set();
  for (let i = 0; i < POSTS; i++) {
    let title;
    do { title = `${pick(TOPICS)} ${pick(SUBJECTS)}`; } while (used.has(title) && used.size < TOPICS.length * SUBJECTS.length);
    const slug = used.has(title) ? `${slugify(title)}-${i}` : slugify(title);
    used.add(title);
    const published = rand() < 0.8;
    const { lastInsertRowid: postId } = ins.post.run(int(1, AUTHORS.length), title, slug,
      `Notes about ${title.toLowerCase()} written for CodeJournal.`, published ? 'published' : 'draft',
      published ? int(20, 2500) : 0, published ? daysAgo(int(1, 90)) : null);
    count.posts++;
    for (let k = int(1, 3); k > 0; k--) count.post_tags += Number(ins.postTag.run(postId, int(1, TAGS.length)).changes);
    if (!published) continue;
    for (let c = int(0, 4); c > 0; c--) {
      const { lastInsertRowid: cid } = ins.comment.run(postId, null, pick(NAMES), pick(REMARKS), daysAgo(int(0, 30)));
      count.comments++;
      if (rand() < 0.4) { ins.comment.run(postId, cid, 'author', pick(REPLIES), daysAgo(int(0, 5))); count.comments++; }
    }
  }
  db.exec('COMMIT');
} catch (err) {
  db.exec('ROLLBACK');                                             // nothing half-inserted
  console.error('Seeding failed, rolled back:', err.message);
  process.exit(1);
}
console.log(`Seeded ${path.basename(dbFile)} (seed=${args.seed || 7}) in ${(performance.now() - t0).toFixed(1)} ms`);
console.table(count);
