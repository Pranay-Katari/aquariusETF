-- Persist the backtest preferences with each user-owned container.
-- Safe to run on the existing Supabase project.

alter table public.etfs
  add column if not exists config jsonb not null default '{}'::jsonb;
