-- Durable, user-scoped Copilot transcripts and semantic-memory index.
begin;

create extension if not exists vector;

create table if not exists public.chat_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default 'New basket idea' check (char_length(title) <= 160),
  proposal jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.chat_conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (char_length(content) between 1 and 4000),
  embedding vector(256),
  created_at timestamptz not null default now()
);

create index if not exists chat_conversations_user_updated_idx on public.chat_conversations(user_id, updated_at desc);
create index if not exists chat_messages_conversation_created_idx on public.chat_messages(conversation_id, created_at);
create index if not exists chat_messages_embedding_idx on public.chat_messages using hnsw (embedding vector_cosine_ops);

alter table public.chat_conversations enable row level security;
alter table public.chat_messages enable row level security;
revoke all on public.chat_conversations, public.chat_messages from anon, authenticated;
grant select on public.chat_conversations, public.chat_messages to authenticated;
create policy "owner reads conversations" on public.chat_conversations for select to authenticated using (user_id = auth.uid());
create policy "owner reads messages" on public.chat_messages for select to authenticated using (user_id = auth.uid());

commit;
