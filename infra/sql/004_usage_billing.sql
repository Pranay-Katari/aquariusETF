-- Adds server-owned usage metering and subscription state.
-- Run after 001_initial.sql with a database administrator connection.

begin;

create table if not exists usage (
  user_id varchar(36) primary key,
  period_start timestamp with time zone not null,
  period_end timestamp with time zone not null,
  runs_used integer not null default 0,
  runs_limit integer not null default 10
);

create table if not exists usage_events (
  run_key varchar(64) primary key,
  user_id varchar(36) not null,
  kind varchar(24) not null,
  status varchar(24) not null default 'pending',
  created_at timestamp with time zone not null
);

create index if not exists ix_usage_events_user_id on usage_events (user_id);

create table if not exists subscriptions (
  user_id varchar(36) primary key,
  stripe_customer_id varchar(255),
  stripe_subscription_id varchar(255),
  status varchar(32) not null default 'inactive',
  price_id varchar(255),
  period_end timestamp with time zone
);

-- The application accesses these tables only through its privileged server
-- connection; prevent direct browser access through Supabase's data API.
alter table public.usage enable row level security;
alter table public.usage_events enable row level security;
alter table public.subscriptions enable row level security;

revoke all on public.usage, public.usage_events, public.subscriptions from anon, authenticated;

commit;
