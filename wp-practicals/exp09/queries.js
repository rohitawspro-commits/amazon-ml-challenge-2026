const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync(require('path').join(__dirname, 'codejournal.db'));
const show = (title, sql, ...p) => { console.log('\n' + title); console.table(db.prepare(sql).all(...p)); };

show('1. Posts and total views per author (published only)', `
  SELECT a.username, COUNT(p.id) AS posts, SUM(p.views) AS total_views
  FROM authors a LEFT JOIN posts p ON p.author_id = a.id AND p.status = 'published'
  GROUP BY a.id ORDER BY total_views DESC`);

show('2. Most used tags', `
  SELECT t.name AS tag, COUNT(*) AS posts FROM tags t JOIN post_tags pt ON pt.tag_id = t.id
  GROUP BY t.id ORDER BY posts DESC, tag LIMIT 5`);

show('3. Top 5 posts from the view v_post_stats', `
  SELECT title, author, views, comment_count AS comments, tag_list AS tags
  FROM v_post_stats WHERE status = 'published' ORDER BY views DESC LIMIT 5`);

const busiest = db.prepare(`SELECT post_id FROM comments WHERE parent_id IS NOT NULL
  GROUP BY post_id ORDER BY COUNT(*) DESC LIMIT 1`).get();
show(`4. Comment thread of post ${busiest.post_id} (recursive CTE)`, `
  WITH RECURSIVE thread(id, depth, sort_path, name, body) AS (
    SELECT id, 0, printf('%05d', id), name, body FROM comments WHERE post_id = ? AND parent_id IS NULL
    UNION ALL
    SELECT c.id, t.depth + 1, t.sort_path || '/' || printf('%05d', c.id), c.name, c.body
    FROM comments c JOIN thread t ON c.parent_id = t.id)
  SELECT substr('      ', 1, depth * 3) || name AS commenter, body FROM thread ORDER BY sort_path`, busiest.post_id);

console.log('\nQuery plan for posts of one author:');
for (const r of db.prepare(`EXPLAIN QUERY PLAN SELECT * FROM posts WHERE author_id = 2`).all()) console.log('  ' + r.detail);
