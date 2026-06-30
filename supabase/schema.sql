-- Group-synced mahjong trackers. Run this in the Supabase SQL editor.
-- All access goes through the `track` Edge Function using the service role,
-- which validates Telegram initData first. RLS is enabled with NO policies, so
-- the public anon key cannot read or write these tables directly.

create extension if not exists pgcrypto;

create table if not exists trackers (
  id          uuid primary key default gen_random_uuid(),
  code        text unique not null,                 -- short share code (?startapp=)
  game        text not null default 'sg',           -- 'sg' for now
  name        text not null default '',
  players     jsonb not null default '[]',           -- ["Alice","Bob",...]; [] = stub, not set up yet
  bases       jsonb not null default '{"tai":0.1,"yao":0.2,"gang":0.2}',
  tg_chat_id  bigint unique,                         -- bound Telegram group (null = app-made "your own" group)
  created_at  timestamptz not null default now()
);

-- If the table already exists from the first version, add the new column:
alter table trackers add column if not exists tg_chat_id bigint unique;
-- Relax the not-null defaults so the bot can create empty stubs:
alter table trackers alter column name set default '';
alter table trackers alter column name drop not null;
alter table trackers alter column players set default '[]';

create table if not exists actions (
  id          uuid primary key default gen_random_uuid(),
  tracker_id  uuid not null references trackers(id) on delete cascade,
  actioner    text not null,                         -- Telegram display name that entered it
  summary     text not null,
  transfers   jsonb not null,                        -- [{payer,payee,amount}]
  created_at  timestamptz not null default now()
);
create index if not exists actions_tracker_idx on actions (tracker_id, created_at);

alter table trackers enable row level security;
alter table actions  enable row level security;
-- No policies on purpose: the anon key gets nothing. The Edge Function uses the
-- service-role key (which bypasses RLS) after validating initData.
