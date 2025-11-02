#!/usr/bin/env python3
import csv
import os
import sys
from supabase import create_client, Client

if len(sys.argv) < 2:
    print("Usage: python supabase_push.py Cleaned.csv")
    sys.exit(1)

csv_path = sys.argv[1]

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)

with open(csv_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

for row in rows:
    supabase.table("places").upsert(row, on_conflict="profile_url").execute()

print(f"Pushed {len(rows)} rows to Supabase.")
