-- MoodDrobe: saved items and search history for logged-in users.
-- Safe to run more than once. Does not touch the better-auth tables.
-- Apply:  docker exec -i mooddrobe_postgres psql -U postgres -d mydb < sql/0001_saved_items_user_history.sql

CREATE TABLE IF NOT EXISTS saved_items (
  id            text PRIMARY KEY,
  user_id       text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  product_id    text NOT NULL,
  image_url     text,
  category_name text,
  source        text,
  created_at    timestamp NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS saved_items_user_product_uidx ON saved_items (user_id, product_id);

CREATE TABLE IF NOT EXISTS user_history (
  id         text PRIMARY KEY,
  user_id    text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  kind       text NOT NULL CHECK (kind IN ('vibe', 'photo')),
  text       text NOT NULL,
  scene      text,
  created_at timestamp NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS user_history_user_created_idx ON user_history (user_id, created_at);
