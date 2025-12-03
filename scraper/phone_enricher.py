#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv, sys, os, time, random, unicodedata, re, argparse, platform, logging
from typing import Dict, Any, List, Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

try:
    import winreg
except Exception:
    winreg = None

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import (
    USER_AGENTS,
    CHROME_VERSION_FALLBACK,
    PAGELOAD_TIMEOUT,
    SCRIPT_TIMEOUT,
    ENRICH_JITTER_MIN,
    ENRICH_JITTER_MAX,
    PHONE_RESTART_EVERY,
    PHONE_ENRICH_LIMIT,
    LOG_FORMAT,
    LOG_LEVEL,
)

DETAIL_PHONE_XP = "//button[.//div[contains(text(),'Phone') or contains(text(),'الهاتف') or contains(text(),'اتصال')]] | //a[contains(@href,'tel:')]"

PHONE_RE = re.compile(r"(?:\+?20)?0?\d{8,11}")
NBSP_REPL = {"\u00A0": " ", "\u202F": " "}


def nfc(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    for k, v in NBSP_REPL.items():
        s = s.replace(k, v)
    return s.strip()


def strong_phone_extract(s: str) -> str:
    if not s:
        return ""
    m = PHONE_RE.search(re.sub(r"[^\d+]", "", s))
    return m.group(0) if m else ""


def normalize_phone_e164(s: str) -> str:
    if not s:
        return ""
    s = nfc(s)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    if digits.startswith("20") and len(digits) >= 11:
        return "+" + digits
    if digits.startswith("0") and len(digits) >= 10:
        return "+20" + digits.lstrip("0")
    if digits.startswith("1") and len(digits) == 10:
        return "+20" + digits
    if digits.startswith("2") and len(digits) >= 9:
        return "+20" + digits
    return "+20" + digits


def jitter(a=ENRICH_JITTER_MIN, b=ENRICH_JITTER_MAX):
    time.sleep(random.uniform(a, b))


def get_installed_chrome_major() -> Optional[int]:
    try:
        if platform.system().lower() != "windows" or winreg is None:
            return None
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                k = winreg.OpenKey(root, r"Software\\Google\\Chrome\\BLBeacon")
                v, _ = winreg.QueryValueEx(k, "version")
                return int(str(v).split(".")[0])
            except OSError:
                pass
    except Exception:
        return None
    return None


def new_driver(headless: bool):
    ua = random.choice(USER_AGENTS)
    logging.info("Launching phone-enricher browser: UA=%s | headless=%s", ua, headless)
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--user-agent=" + ua)
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--blink-settings=imagesEnabled=true")
    major = get_installed_chrome_major() or CHROME_VERSION_FALLBACK
    d = uc.Chrome(options=opts, version_main=major)
    try:
        d.set_page_load_timeout(PAGELOAD_TIMEOUT)
        d.set_script_timeout(SCRIPT_TIMEOUT)
    except Exception:
        pass
    return d


def get_phone_from_page(driver, url: str, timeout: int = 8) -> str:
    if not url:
        return ""
    try:
        logging.debug("Opening profile for phone enrichment: %s", url)
        driver.get(url)
    except WebDriverException as e:
        logging.warning("Navigation failed for %s: %s", url, e)
        return ""
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, DETAIL_PHONE_XP))
        )
    except TimeoutException:
        logging.debug("No phone element found for %s within timeout", url)
        return ""
    raw = el.get_attribute("href") or el.text or ""
    raw = raw.strip()
    if raw.startswith("tel:"):
        raw = raw[4:]
    ph = strong_phone_extract(raw) or raw
    return nfc(ph)


def read_csv(path: str) -> (List[str], List[Dict[str, Any]]):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        rows = [dict(x) for x in r]
        return r.fieldnames, rows


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, Any]]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def process(input_csv: str, output_csv: str, limit: Optional[int] = None, headless: bool = True):
    logging.info("Starting phone enrichment: in=%s out=%s limit=%s", input_csv, output_csv, limit)
    fieldnames, rows = read_csv(input_csv)
    logging.info("Loaded %d rows from input", len(rows))

    if "phone" not in fieldnames:
        fieldnames.append("phone")
    if "phone_e164" not in fieldnames:
        fieldnames.append("phone_e164")

    driver = new_driver(headless=headless)
    updated = 0
    try:
        total = len(rows)
        if limit is not None:
            total = min(total, limit)
        for idx, row in enumerate(rows):
            if limit is not None and idx >= limit:
                break

            if PHONE_RESTART_EVERY and idx > 0 and idx % PHONE_RESTART_EVERY == 0:
                logging.info("Restarting browser after %d rows to stay fresh", idx)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = new_driver(headless=headless)

            url = (row.get("profile_url") or "").strip()
            if not url:
                continue

            phone = get_phone_from_page(driver, url)
            jitter()
            if not phone:
                continue

            row["phone"] = phone
            row["phone_e164"] = normalize_phone_e164(phone)
            updated += 1

            if updated % 20 == 0:
                logging.info("Progress: updated_phones=%d / processed_rows=%d", updated, idx + 1)
                write_csv(output_csv, fieldnames, rows)

        write_csv(output_csv, fieldnames, rows)
        logging.info("Phone enrichment finished. Total updated rows: %d", updated)
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--limit", type=int, default=PHONE_ENRICH_LIMIT)
    ap.add_argument("--no-headless", action="store_true")
    ap.add_argument("--log", dest="log", default=LOG_LEVEL)
    args = ap.parse_args()

    level = getattr(logging, args.log.upper(), getattr(logging, LOG_LEVEL, logging.INFO))
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler("phone_enricher.log", encoding="utf-8"),
            logging.StreamHandler(stream=sys.stdout),
        ],
    )

    logging.info(
        "CLI args: in=%s out=%s limit=%s no_headless=%s log=%s",
        args.inp,
        args.out,
        args.limit,
        args.no_headless,
        args.log,
    )

    process(args.inp, args.out, limit=args.limit, headless=not args.no_headless)


if __name__ == "__main__":
    main()
