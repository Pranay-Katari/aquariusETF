-- Aquarius initial Supabase migration. Run once with a database administrator.

begin;


CREATE TABLE etfs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	symbol VARCHAR(12) NOT NULL, 
	description VARCHAR(4000) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_etfs_user_id ON etfs (user_id);

alter table public.etfs enable row level security;

revoke all on public.etfs from anon, authenticated;

grant select on public.etfs to authenticated;

create policy "owner reads etfs" on public.etfs for select to authenticated using (user_id = auth.uid()::text);


CREATE TABLE backtests (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	etf_id VARCHAR(36) NOT NULL, 
	portfolio_version INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	config JSON NOT NULL, 
	snapshot JSON NOT NULL, 
	metrics JSON NOT NULL, 
	warnings JSON NOT NULL, 
	error VARCHAR(1000), 
	artifact_path VARCHAR(1000), 
	checksum VARCHAR(64), 
	engine_version VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(etf_id) REFERENCES etfs (id)
)

;

CREATE INDEX ix_backtests_etf_id ON backtests (etf_id);

CREATE INDEX ix_backtests_user_id ON backtests (user_id);

CREATE INDEX ix_backtests_status ON backtests (status);

alter table public.backtests enable row level security;

revoke all on public.backtests from anon, authenticated;

grant select on public.backtests to authenticated;

create policy "owner reads backtests" on public.backtests for select to authenticated using (user_id = auth.uid()::text);


CREATE TABLE etf_holdings (
	id VARCHAR(36) NOT NULL, 
	etf_id VARCHAR(36) NOT NULL, 
	ticker VARCHAR(10) NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (etf_id, ticker), 
	FOREIGN KEY(etf_id) REFERENCES etfs (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_etf_holdings_etf_id ON etf_holdings (etf_id);

alter table public.etf_holdings enable row level security;

revoke all on public.etf_holdings from anon, authenticated;

grant select on public.etf_holdings to authenticated;

create policy "owner reads etf_holdings" on public.etf_holdings for select to authenticated using (exists (select 1 from public.etfs e where e.id = etf_id and e.user_id = auth.uid()::text));


CREATE TABLE order_previews (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	etf_id VARCHAR(36) NOT NULL, 
	portfolio_version INTEGER NOT NULL, 
	payload JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(etf_id) REFERENCES etfs (id)
)

;

CREATE INDEX ix_order_previews_user_id ON order_previews (user_id);

alter table public.order_previews enable row level security;

revoke all on public.order_previews from anon, authenticated;

grant select on public.order_previews to authenticated;

create policy "owner reads order_previews" on public.order_previews for select to authenticated using (user_id = auth.uid()::text);


CREATE TABLE research_runs (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	etf_id VARCHAR(36) NOT NULL, 
	payload JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(etf_id) REFERENCES etfs (id)
)

;

CREATE INDEX ix_research_runs_user_id ON research_runs (user_id);

alter table public.research_runs enable row level security;

revoke all on public.research_runs from anon, authenticated;

grant select on public.research_runs to authenticated;

create policy "owner reads research_runs" on public.research_runs for select to authenticated using (user_id = auth.uid()::text);


CREATE TABLE orders (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	preview_id VARCHAR(36) NOT NULL, 
	client_order_id VARCHAR(48) NOT NULL, 
	payload JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(preview_id) REFERENCES order_previews (id), 
	UNIQUE (client_order_id)
)

;

CREATE INDEX ix_orders_user_id ON orders (user_id);

alter table public.orders enable row level security;

revoke all on public.orders from anon, authenticated;

grant select on public.orders to authenticated;

create policy "owner reads orders" on public.orders for select to authenticated using (user_id = auth.uid()::text);

-- All writes go through the authenticated FastAPI business layer.

-- This prevents direct REST writes from bypassing versioning, validation or order approvals.

-- DATABASE_URL is server-only and must be a privileged application connection.

commit;
