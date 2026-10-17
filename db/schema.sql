-- LeadSignal schema (Supabase / Postgres 15)
-- Last updated: 2026-10-17

create table if not exists public.production_maps (
  id              bigserial primary key,
  created_at      timestamptz default now(),
  name            text,
  correct_name    text,
  profile_url     text unique,
  category        text,
  query_location  text,
  address_line    text,
  phone           text,
  website         text,
  rating          numeric,
  reviews_count   integer,
  opening_hours   text,
  phone_verified  boolean not null default false
);

create index if not exists idx_pm_cat_loc_rating on public.production_maps (category, query_location, rating desc nulls last);
create index if not exists idx_pm_loc_rating on public.production_maps (query_location, rating desc nulls last);

create table if not exists public.lead_combos (
  category        text not null,
  query_location  text not null,
  n               integer not null default 0,
  n_phone         integer not null default 0,
  n_web           integer not null default 0,
  primary key (category, query_location)
);

create or replace function public.bump_lead_combos()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.lead_combos (category, query_location, n, n_phone, n_web)
  select category, query_location, count(*),
         count(*) filter (where coalesce(phone,'') <> ''),
         count(*) filter (where coalesce(website,'') <> '')
  from new_rows
  where coalesce(category,'') <> '' and coalesce(query_location,'') <> ''
  group by 1, 2
  on conflict (category, query_location) do update
    set n = public.lead_combos.n + excluded.n,
        n_phone = public.lead_combos.n_phone + excluded.n_phone,
        n_web = public.lead_combos.n_web + excluded.n_web;
  return null;
end $$;

revoke all on function public.bump_lead_combos() from public, anon, authenticated;

drop trigger if exists trg_bump_lead_combos on public.production_maps;
create trigger trg_bump_lead_combos
after insert on public.production_maps
referencing new table as new_rows
for each statement execute function public.bump_lead_combos();

create or replace view public.distinct_query_locations
with (security_invoker = on) as
select distinct query_location from public.lead_combos order by query_location;

create or replace function public.get_lead_combos(min_n integer default 1)
returns json language sql stable security invoker set search_path = public as $$
  select coalesce(json_agg(json_build_array(category, query_location, n, n_phone, n_web) order by category, query_location), '[]'::json)
  from public.lead_combos where n >= min_n;
$$;

create or replace function public.lead_stats()
returns json language sql stable security invoker set search_path = public as $$
  select json_build_object(
    'row_count', coalesce(sum(n), 0),
    'phone_pct', case when coalesce(sum(n), 0) = 0 then 0 else round(100.0 * sum(n_phone) / sum(n)) end,
    'locations', count(distinct query_location),
    'categories', count(distinct category)
  ) from public.lead_combos;
$$;

create or replace function public.get_lead_meta()
returns json language sql stable security invoker set search_path = public as $$
  select json_build_object(
    'categories', coalesce((select json_agg(category order by category) from (select distinct category from public.lead_combos) c), '[]'::json),
    'locations', coalesce((select json_agg(query_location order by query_location) from (select distinct query_location from public.lead_combos) l), '[]'::json)
  );
$$;

grant execute on function public.get_lead_combos(integer), public.lead_stats(), public.get_lead_meta() to anon, authenticated;

create table if not exists public.pipeline_state (
  key         text primary key,
  value       text not null,
  updated_at  timestamptz not null default now()
);

create table if not exists public.lead_requests (
  id         uuid primary key default gen_random_uuid(),
  location   text,
  category   text,
  email      text,
  created_at timestamptz default now()
);

alter table public.production_maps enable row level security;
alter table public.lead_combos enable row level security;
alter table public.pipeline_state enable row level security;
alter table public.lead_requests enable row level security;

drop policy if exists "Public read" on public.production_maps;
create policy "Public read" on public.production_maps for select to anon, authenticated using (true);
drop policy if exists "lead_combos read" on public.lead_combos;
create policy "lead_combos read" on public.lead_combos for select to anon, authenticated using (true);

revoke insert, update, delete, truncate on public.production_maps, public.lead_combos from anon, authenticated;
revoke all on public.pipeline_state, public.lead_requests from anon, authenticated;
