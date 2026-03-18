-- ============================================================
-- LeadSignal — Supabase Schema
-- Production table: production_maps
-- Last updated: 2026-03-18
-- ============================================================

-- ── Main production table ────────────────────────────────────
create table if not exists public.production_maps (
  id              bigserial primary key,
  created_at      timestamptz default now(),
  name            text,
  correct_name    text,
  profile_url     text unique,
  photo_urls      text,
  category        text,
  query_location  text,
  address_line    text,
  phone           text,
  website         text,
  rating          numeric,
  opening_hours   text,
  social_links    text,
  phone_verified  boolean not null default false
);

-- Index for fast phone enrichment queries (unverified rows)
create index if not exists idx_production_maps_phone_verified
  on public.production_maps (phone_verified)
  where phone_verified = false;

-- ── Supporting tables ─────────────────────────────────────────
create table if not exists public.lead_requests (
  id         uuid primary key default gen_random_uuid(),
  location   text,
  category   text,
  email      text,
  created_at timestamptz default now()
);

create table if not exists public.sitemap_cache (
  id           integer primary key default 1,
  body         text,
  generated_at timestamptz default now()
);

-- ── Dead tables (do not use) ──────────────────────────────────
-- The following tables are unused and can be dropped safely:
--   public.places          (old table, superseded by production_maps)
--   public.places2         (old table, superseded by production_maps)
--   public.places_backup   (empty backup, no longer needed)
--   public.places_test     (empty test table)
--   public.places_to_fix   (empty migration helper, done)
--   public.places_to_fix_unique (empty migration helper, done)
--   public.map_places      (empty intermediate table, done)
--   public.products        (price comparison project, unrelated to LeadSignal)

-- To drop them all at once (run manually when ready):
-- drop table if exists public.places cascade;
-- drop table if exists public.places2 cascade;
-- drop table if exists public.places_backup cascade;
-- drop table if exists public.places_test cascade;
-- drop table if exists public.places_to_fix cascade;
-- drop table if exists public.places_to_fix_unique cascade;
-- drop table if exists public.map_places cascade;
