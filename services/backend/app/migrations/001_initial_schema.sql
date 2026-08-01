create extension if not exists pgcrypto;

create table if not exists feeders (
  id text primary key,
  substation_id text not null,
  name text,
  created_at timestamptz not null default now()
);

create table if not exists distribution_transformers (
  id text primary key,
  feeder_id text not null references feeders(id),
  latitude double precision not null,
  longitude double precision not null,
  capacity_kva integer not null check (capacity_kva > 0),
  households_served integer not null check (households_served >= 0),
  created_at timestamptz not null default now()
);

create table if not exists poles (
  id text primary key,
  feeder_id text not null references feeders(id),
  dt_id text not null references distribution_transformers(id),
  latitude double precision not null,
  longitude double precision not null,
  seq_on_line integer check (seq_on_line > 0),
  parent_pole_id text references poles(id),
  pole_type text not null,
  ward text not null,
  pincode text,
  device_id text unique,
  created_at timestamptz not null default now()
);

create table if not exists topology_edges (
  id uuid primary key default gen_random_uuid(),
  feeder_id text not null references feeders(id),
  dt_id text not null references distribution_transformers(id),
  parent_pole_id text references poles(id),
  child_pole_id text not null references poles(id),
  source text not null check (source in ('known', 'inferred')),
  confidence double precision not null check (confidence >= 0 and confidence <= 1),
  distance_m double precision not null check (distance_m >= 0),
  created_at timestamptz not null default now(),
  unique (dt_id, child_pole_id)
);

create table if not exists telemetry_events (
  id uuid primary key default gen_random_uuid(),
  device_id text not null,
  pole_id text not null references poles(id),
  event text not null check (event in ('heartbeat', 'power_lost', 'power_restored', 'boot')),
  energized boolean not null,
  device_ts timestamptz not null,
  received_at timestamptz not null default now(),
  seq integer not null check (seq >= 0),
  battery_mv integer not null check (battery_mv >= 0),
  rssi integer not null,
  firmware text not null,
  is_duplicate boolean not null default false,
  is_stale boolean not null default false
);

create table if not exists pole_states (
  pole_id text primary key references poles(id),
  state text not null check (state in ('live', 'dark', 'unknown')),
  source_event_id uuid references telemetry_events(id),
  last_event_at timestamptz,
  last_heartbeat_at timestamptz,
  confidence double precision not null check (confidence >= 0 and confidence <= 1),
  updated_at timestamptz not null default now()
);

create table if not exists device_states (
  device_id text primary key,
  pole_id text references poles(id),
  last_seq integer check (last_seq >= 0),
  seq_epoch integer not null default 0 check (seq_epoch >= 0),
  status text not null check (status in ('online', 'offline', 'suspect')),
  firmware text,
  last_seen_at timestamptz,
  last_rssi integer,
  updated_at timestamptz not null default now()
);

create table if not exists scheduled_outages (
  id text primary key,
  scope text not null check (scope in ('feeder', 'dt')),
  target_id text not null,
  start_at timestamptz not null,
  end_at timestamptz not null,
  reason text not null,
  created_at timestamptz not null default now(),
  check (end_at > start_at)
);

create table if not exists incidents (
  id uuid primary key default gen_random_uuid(),
  incident_type text not null check (incident_type in ('span', 'dt', 'feeder', 'sensor')),
  status text not null check (status in ('detected', 'planned', 'suppressed', 'closed')),
  feeder_id text references feeders(id),
  dt_id text references distribution_transformers(id),
  upstream_pole_id text references poles(id),
  downstream_pole_id text references poles(id),
  latitude double precision,
  longitude double precision,
  pincode text,
  affected_poles integer not null default 0 check (affected_poles >= 0),
  confidence double precision not null check (confidence >= 0 and confidence <= 1),
  confidence_reasons jsonb not null default '[]'::jsonb,
  opened_at timestamptz not null default now(),
  verified_at timestamptz,
  closed_at timestamptz
);

create table if not exists tickets (
  id uuid primary key default gen_random_uuid(),
  incident_id uuid not null unique references incidents(id),
  lifecycle_status text not null check (
    lifecycle_status in ('detected', 'acknowledged', 'crew_assigned', 'resolved', 'verified', 'closed')
  ),
  assigned_crew text,
  operator_note text,
  resolved_marked_at timestamptz,
  verified_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists ticket_events (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id),
  event_type text not null,
  actor text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_transformers_feeder_id
  on distribution_transformers(feeder_id);

create index if not exists idx_poles_feeder_dt
  on poles(feeder_id, dt_id);

create index if not exists idx_poles_parent_pole_id
  on poles(parent_pole_id);

create index if not exists idx_topology_edges_parent
  on topology_edges(dt_id, parent_pole_id);

create index if not exists idx_topology_edges_child
  on topology_edges(dt_id, child_pole_id);

create unique index if not exists idx_telemetry_dedupe
  on telemetry_events(device_id, seq, event, energized, device_ts);

create index if not exists idx_telemetry_pole_received
  on telemetry_events(pole_id, received_at desc);

create index if not exists idx_scheduled_outages_target_window
  on scheduled_outages(scope, target_id, start_at, end_at);

create index if not exists idx_incidents_status_opened
  on incidents(status, opened_at desc);

create index if not exists idx_incidents_scope
  on incidents(feeder_id, dt_id, status);
