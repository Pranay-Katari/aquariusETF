create table if not exists public.chat_usages (
  user_id uuid primary key references auth.users(id) on delete cascade,
  window_started_at timestamptz not null default now(),
  request_count integer not null default 0 check (request_count >= 0)
);

alter table public.chat_usages enable row level security;
revoke all on public.chat_usages from anon, authenticated;
