#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is not set}"
BATCH_BLOCKS="${BATCH_BLOCKS:-4000}"
MAX_DB_MB="${MAX_DB_MB:-850}"

q() { psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -qtAX -c "$1"; }

COLS="id, created_at, name, correct_name, profile_url, category, query_location, address_line, phone, website, rating, reviews_count, opening_hours, phone_verified"

db_mb() { q "select pg_database_size(current_database()) / 1048576"; }

echo "Database size before: $(db_mb) MB"

q "drop index if exists public.idx_production_maps_category;
   drop index if exists public.idx_production_maps_query_location;
   drop index if exists public.idx_production_maps_category_location;
   drop index if exists public.idx_production_maps_phone_verified;
   drop index if exists public.idx_production_maps_verified_id;
   drop index if exists public.idx_pm_cat_rating;
   drop policy if exists \"public read\" on public.production_maps;
   drop function if exists public.fix_profile_urls_step(integer);"
echo "Dropped unused indexes. Size now: $(db_mb) MB"

already_new=$(q "select to_regclass('public.production_maps_new') is not null")
has_photo=$(q "select count(*) from information_schema.columns where table_schema='public' and table_name='production_maps' and column_name='photo_urls'")

if [[ "$already_new" == "f" && "$has_photo" == "0" ]]; then
  echo "Table is already rebuilt. Nothing else to do."
  exit 0
fi

if [[ "$already_new" == "f" ]]; then
  q "create table public.production_maps_new (
       id bigint not null,
       created_at timestamptz default now(),
       name text,
       correct_name text,
       profile_url text,
       category text,
       query_location text,
       address_line text,
       phone text,
       website text,
       rating numeric,
       reviews_count integer,
       opening_hours text,
       phone_verified boolean not null default false
     );"
  echo "Created production_maps_new"
fi

end_block=$(q "select pg_relation_size('public.production_maps') / 8192")
while true; do
  remaining=$(q "select exists(select 1 from public.production_maps)")
  [[ "$remaining" == "t" ]] || break
  size=$(db_mb)
  if (( size > MAX_DB_MB )); then
    echo "Database is at ${size} MB, above the ${MAX_DB_MB} MB safety limit. Stopping. Re-run later to resume."
    exit 1
  fi
  start=$(( end_block > BATCH_BLOCKS ? end_block - BATCH_BLOCKS : 0 ))
  moved=$(q "with moved as (
               delete from public.production_maps where ctid >= '($start,0)'::tid returning $COLS
             ), ins as (
               insert into public.production_maps_new ($COLS) select $COLS from moved returning 1
             ) select count(*) from ins")
  end_block=$start
  q "vacuum public.production_maps"
  after=$(q "select pg_relation_size('public.production_maps') / 1048576")
  echo "Moved $moved rows from block $start. Old table now ${after} MB. Database $(db_mb) MB."
done

echo "All rows moved. Swapping tables."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q <<'SQL'
set statement_timeout = 0;
begin;
alter sequence public.production_maps_id_seq owned by none;
drop table public.production_maps;
alter table public.production_maps_new rename to production_maps;
alter table public.production_maps alter column id set default nextval('public.production_maps_id_seq');
alter sequence public.production_maps_id_seq owned by public.production_maps.id;
alter table public.production_maps add constraint production_maps_pkey primary key (id);
alter table public.production_maps add constraint production_maps_profile_url_key unique (profile_url);
create index idx_pm_cat_loc_rating on public.production_maps (category, query_location, rating desc nulls last);
create index idx_pm_loc_rating on public.production_maps (query_location, rating desc nulls last);
create trigger trg_bump_lead_combos after insert on public.production_maps
  referencing new table as new_rows for each statement execute function public.bump_lead_combos();
alter table public.production_maps enable row level security;
create policy "Public read" on public.production_maps for select to anon, authenticated using (true);
revoke insert, update, delete, truncate on public.production_maps from anon, authenticated;
grant select on public.production_maps to anon, authenticated;
commit;
analyze public.production_maps;
SQL

echo "Done. Rows: $(q "select count(*) from public.production_maps"). Database size after: $(db_mb) MB"
