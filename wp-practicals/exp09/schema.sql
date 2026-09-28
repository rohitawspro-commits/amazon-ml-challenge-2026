-- CodeJournal: a developer blog
PRAGMA foreign_keys = ON;

CREATE TABLE authors (
  id        INTEGER PRIMARY KEY,
  username  TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  email     TEXT NOT NULL UNIQUE CHECK (email LIKE '%_@_%._%'),
  joined_on TEXT NOT NULL
);

CREATE TABLE posts (
  id           INTEGER PRIMARY KEY,
  author_id    INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  slug         TEXT NOT NULL UNIQUE,
  body         TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  views        INTEGER NOT NULL DEFAULT 0 CHECK (views >= 0),
  published_at TEXT,
  CHECK (status = 'draft' OR published_at IS NOT NULL)      -- published posts need a date
);

CREATE TABLE tags (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE post_tags (                                     -- many-to-many
  post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
  PRIMARY KEY (post_id, tag_id)
);

CREATE TABLE comments (
  id         INTEGER PRIMARY KEY,
  post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  parent_id  INTEGER REFERENCES comments(id) ON DELETE CASCADE, -- NULL = top-level, else a reply
  name       TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_posts_author   ON posts(author_id);
CREATE INDEX idx_posts_status   ON posts(status, published_at);
CREATE INDEX idx_comments_post  ON comments(post_id);
CREATE INDEX idx_post_tags_tag  ON post_tags(tag_id);

CREATE VIEW v_post_stats AS
SELECT p.id, p.title, a.username AS author, p.status, p.views,
       (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
       (SELECT GROUP_CONCAT(t.name, ', ') FROM post_tags pt JOIN tags t ON t.id = pt.tag_id
         WHERE pt.post_id = p.id) AS tag_list
FROM posts p JOIN authors a ON a.id = p.author_id;
