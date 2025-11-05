#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, csv, sys, unicodedata, json, logging, os, random, re, time, platform
from urllib.parse import quote_plus
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Tuple

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.keys import Keys

try:
    from urllib3.exceptions import ReadTimeoutError, NewConnectionError, MaxRetryError
except Exception:
    ReadTimeoutError = NewConnectionError = MaxRetryError = Exception

try:
    import winreg
except Exception:
    winreg = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]
ACCEPT_LANG = [
    "en-US,en;q=0.9,ar;q=0.7",
    "en-GB,en;q=0.9,ar;q=0.7",
    "ar-EG,ar;q=0.9,en;q=0.6",
]
def canonicalize_maps_url(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    if u.startswith("//"):
        u = "https:" + u
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    u = re.sub(r"(?i)[&?](?:hl|utm_[^=]+|fbclid|gclid|hsa_[^=]+|entry|ved|sa|source|authuser)=[^&#]*", "", u)
    u = re.sub(r"[&?]+$", "", u)
    return u

def slug_from_profile_url(u: str) -> str:
    if not u:
        return ""
    m = re.search(r"/maps/place/([^/]+)", u)
    return re.sub(r"[-_+]+", " ", m.group(1)).strip().lower() if m else ""

def norm_name_for_compare(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\b(branch|فرع)\b", "", s).strip()
    return s
CARD_CONTAINER_CSS = "div.Nv2PK"
CARD_TITLE_CSS = ".qBF1Pd"
CARD_ANCHOR_CSS = "a.hfpxzc"
INFO_ROW_CSS = ".W4Efsd"
DETAIL_NAME_XP = "//h1[contains(@class,'fontHeadline') or contains(@class,'DUwDvf') or @role='heading']"
DETAIL_RATING_XP = "//span[contains(@aria-label,'rating') or contains(@class,'F7nice') or contains(@class,'ceNzKf')]"
DETAIL_REVIEW_COUNT_XP = "//button[.//span[contains(text(),'reviews') or contains(text(),'review') or contains(text(),'تقييم')]]//span[1]"
DETAIL_HOURS_STATUS_XP = "//span[(@aria-label and (contains(@aria-label,'Open') or contains(@aria-label,'Closed'))) or (contains(normalize-space(.),'Open') or contains(normalize-space(.),'Closed') or contains(normalize-space(.),'24 hours'))][1]"
DETAIL_ADDRESS_XP = "//button[.//div[contains(text(),'Address') or contains(text(),'العنوان')]] | //div[contains(@aria-label,'Address')]"
DETAIL_PHONE_XP = "//button[.//div[contains(text(),'Phone') or contains(text(),'الهاتف') or contains(text(),'اتصال')]] | //a[contains(@href,'tel:')]"
DETAIL_WEBSITE_BTN_XP = "//div[contains(@class,'m6QErb') and contains(@class,'WNBkOb')]//a[@href and (contains(@aria-label,'Website') or .//span[normalize-space()='Website'])]"
DETAIL_SOCIAL_LINKS_XP = "//a[@href and (contains(@href,'facebook.com') or contains(@href,'instagram.com') or contains(@href,'x.com') or contains(@href,'twitter.com') or contains(@href,'tiktok.com'))]"
DETAIL_PHOTOS_IMG_XP = "//img[contains(@src,'googleusercontent') or contains(@src,'ggpht')][@src]"

SCROLL_BATCH = 6
MAX_SCROLL_TRIES = 50
RESTART_EVERY_CATEGORIES = 1
PAGELOAD_TIMEOUT = 30
SCRIPT_TIMEOUT = 20
READ_TIMEOUT = 120

CSV_FIELDS = [
    "category","query_location","name","category_line","address_line","plus_code","phone","website","profile_url","rating","reviews_count","opening_hours","social_links","photo_urls","timestamp"
]

@dataclass
class Place:
    category: str
    query_location: str
    name: str = ""
    category_line: str = ""
    address_line: str = ""
    plus_code: str = ""
    phone: str = ""
    website: str = ""
    profile_url: str = ""
    rating: str = ""
    reviews_count: str = ""
    opening_hours: str = ""
    social_links: str = ""
    photo_urls: str = ""
    timestamp: str = ""

def jitter(a=0.6, b=1.6):
    time.sleep(random.uniform(a, b))


def read_existing_profile_urls(csv_path: str) -> Set[str]:
    seen = set()
    if not os.path.exists(csv_path):
        return seen
    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                url = canonicalize_maps_url((row.get("profile_url") or "").strip())
                if url:
                    seen.add(url)
    except Exception as e:
        logging.warning("Resume: failed to read existing CSV: %s", e)
    return seen


def init_csv(csv_path: str) -> None:
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def append_csv(csv_path: str, place: Place) -> None:
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writerow({k: _norm(v) for k, v in asdict(place).items()})


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


def new_driver(headless: bool, proxy: Optional[str]):
    ua = random.choice(USER_AGENTS)
    lang = random.choice(ACCEPT_LANG)
    logging.info("Launching browser: UA=%s | Lang=%s | Headless=%s", ua, lang, headless)
    opts = uc.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--user-agent=" + ua)
    opts.add_argument("--accept-language=" + lang)
    opts.add_argument("--lang=" + lang.split(",")[0])
    opts.add_argument("--window-size=1280,1000")
    opts.add_argument("--blink-settings=imagesEnabled=true")
    opts.add_argument("--disable-features=Translate,IsolateOrigins,site-per-process")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
        logging.info("Using proxy: %s", proxy)
    major = get_installed_chrome_major() or 141
    driver = uc.Chrome(options=opts, version_main=major)
    try:
        driver.set_page_load_timeout(PAGELOAD_TIMEOUT)
        driver.set_script_timeout(SCRIPT_TIMEOUT)
    except Exception:
        pass
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass
    return driver


def wait_for(driver, by, value, timeout=20):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def any_present(driver, selectors: List[Tuple[str, str]], timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        for by, value in selectors:
            try:
                els = driver.find_elements(by, value)
                if els:
                    return els
            except Exception:
                pass
        time.sleep(0.2)
    return []


def safe_text(el) -> str:
    try:
        return el.text.strip()
    except Exception:
        return ""


def clean_rating_text(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"\d+(?:\.\d+)?", s)
    return m.group(0) if m else ""


def clean_reviews_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace(",", "")
    m = re.search(r"\d+", s)
    return m.group(0) if m else ""


def looks_like_rating_line(s: str) -> bool:
    if not s:
        return False
    return bool(re.match(r"^\s*\d+(?:\.\d+)?\s*(?:\([0-9,]+\))?", s))


def looks_like_hours(s: str) -> bool:
    if not s:
        return False
    return bool(re.search(r"Open|Closed|Closes|Opens|يفتح|مفتوح|مغلق|٢٤ ساعة|24 hours", s, re.I))


def strong_phone_extract(s: str) -> str:
    if not s:
        return ""
    m = re.search(r"(?:\+?20)?0?\d{8,11}", re.sub(r"[^\d+]", "", s))
    return m.group(0) if m else ""


def extract_card_basic(driver, card) -> Dict[str, str]:
    name = ""; profile_url = ""
    try:
        a = card.find_element(By.CSS_SELECTOR, CARD_ANCHOR_CSS)
        profile_url = a.get_attribute("href") or ""
        name = a.get_attribute("aria-label") or ""
    except Exception:
        pass
    if not name:
        try:
            t = card.find_element(By.CSS_SELECTOR, CARD_TITLE_CSS)
            name = safe_text(t)
        except Exception:
            pass
    category_line = ""; address_line = ""; opening_hours = ""; phone = ""
    try:
        rows = card.find_elements(By.CSS_SELECTOR, INFO_ROW_CSS)
        texts = [safe_text(r) for r in rows if safe_text(r)]
        texts = [t for t in texts if not looks_like_rating_line(t)]
        for tx in texts:
            if not opening_hours and looks_like_hours(tx):
                opening_hours = re.sub(r"\s+", " ", tx)
            if not phone:
                p = strong_phone_extract(tx)
                if p:
                    phone = p
        for tx in texts:
            if "·" in tx and not category_line and not address_line:
                parts = [p.strip() for p in tx.split("·", 1)]
                if len(parts) == 2 and parts[0] and parts[1]:
                    category_line, address_line = parts
                    break
        if not category_line and texts:
            category_line = texts[0]
        if not address_line and len(texts) > 1:
            address_line = texts[1]
    except Exception:
        pass
    return {
        "name": name,
        "profile_url": profile_url,
        "category_line": category_line,
        "address_line": address_line,
        "opening_hours": opening_hours,
        "phone": phone,
        "website": "",
    }


def open_card_detail(driver, card) -> None:
    try:
        a = card.find_element(By.CSS_SELECTOR, CARD_ANCHOR_CSS)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", a)
        jitter(0.2, 0.6)
        a.click()
    except Exception:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
        jitter(0.2, 0.6)
        card.click()
    try:
        WebDriverWait(driver, 15).until(
            lambda d: d.find_elements(By.XPATH, DETAIL_NAME_XP)
            or any(
                (e.get_attribute("src") or "").startswith("http")
                for e in d.find_elements(By.XPATH, DETAIL_PHOTOS_IMG_XP)
            )
        )
    except TimeoutException:
        pass


def grab_address_and_plus(driver):
    selectors = [
        ("xpath", "//button[@data-item-id='address']"),
        ("xpath", "//button[contains(@aria-label, 'Address')]"),
        ("xpath", "//div[contains(text(),'Address') or contains(text(),'العنوان')]")
    ]
    for mode, sel in selectors:
        try:
            el = driver.find_element(By.XPATH, sel) if mode == "xpath" else driver.find_element(By.CSS_SELECTOR, sel)
            txt = el.get_attribute("aria-label") or el.text
            if txt:
                txt = txt.replace("\n", " ").strip()
                plus = ""
                m = re.search(r"[A-Z0-9]{4}\+[A-Z0-9]{2,}", txt)
                if m:
                    plus = m.group(0)
                txt = re.sub(r"[A-Z0-9]{4}\+[A-Z0-9]{2,}", "", txt).strip()
                return txt, plus
        except Exception:
            pass
    return "", ""


def extract_detail(driver) -> Dict[str, str]:
    name = rating = reviews_count = opening_hours = address = phone = website = ""
    social_links: List[str] = []
    photos: List[str] = []
    plus_code = ""
    try:
        el = driver.find_element(By.XPATH, DETAIL_NAME_XP)
        name = safe_text(el)
    except Exception:
        pass
    try:
        el = driver.find_element(By.XPATH, DETAIL_RATING_XP)
        rating = clean_rating_text(el.get_attribute("aria-label") or safe_text(el))
    except Exception:
        pass
    try:
        el = driver.find_element(By.XPATH, DETAIL_REVIEW_COUNT_XP)
        reviews_count = clean_reviews_text(safe_text(el))
    except Exception:
        pass
    try:
        el = driver.find_element(By.XPATH, DETAIL_HOURS_STATUS_XP)
        opening_hours = safe_text(el)
    except Exception:
        pass
    addr, plus = grab_address_and_plus(driver)
    address = addr
    plus_code = plus
    try:
        el = driver.find_element(By.XPATH, DETAIL_PHONE_XP)
        p = el.get_attribute("href") or safe_text(el)
        if p.startswith("tel:"):
            p = p.replace("tel:", "")
        phone = strong_phone_extract(p) or p.strip()
    except Exception:
        pass
    try:
        el = driver.find_element(By.XPATH, DETAIL_WEBSITE_BTN_XP)
        website = el.get_attribute("href") or ""
    except Exception:
        pass
    try:
        links = driver.find_elements(By.XPATH, DETAIL_SOCIAL_LINKS_XP)
        social_links = list({l.get_attribute("href") for l in links if l.get_attribute("href")})
    except Exception:
        pass
    try:
        WebDriverWait(driver, 8).until(
            lambda d: any(
                (e.get_attribute("src") or "").startswith("http") or (e.get_attribute("src") or "").startswith("//")
                for e in d.find_elements(By.XPATH, DETAIL_PHOTOS_IMG_XP)
            )
        )
    except TimeoutException:
        pass
    try:
        imgs = driver.find_elements(By.XPATH, DETAIL_PHOTOS_IMG_XP)
        for im in imgs[:6]:
            src = (im.get_attribute("src") or "").strip()
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("http"):
                photos.append(src)
    except Exception:
        pass
    return {
        "name": name,
        "rating": rating,
        "reviews_count": reviews_count,
        "opening_hours": opening_hours,
        "address": address,
        "plus_code": plus_code,
        "phone": phone,
        "website": website,
        "social_links": ", ".join(social_links),
        "photo_urls": ", ".join(photos),
    }


def _get_results_feed(driver):
    xpaths = [
        "//div[@role='feed' and contains(@class,'m6QErb')]",
        "//div[@role='feed' and starts-with(@aria-label, 'Results for')]",
        "//div[contains(@class,'m6QErb') and (starts-with(@aria-label,'Results for') or @role='feed')]",
    ]
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            if el:
                return el
        except Exception:
            pass
    try:
        return driver.find_element(By.CSS_SELECTOR, "div.m6QErb")
    except Exception:
        return None


def _click_more_places_if_present(driver):
    candidates = [
        (By.XPATH, "//button[.//span[contains(.,'More places') or contains(.,'View all')]]"),
        (By.XPATH, "//a[contains(.,'More places') or contains(.,'View all')]"),
        (By.XPATH, "//button[contains(.,'More places') or contains(.,'View all')]"),
    ]
    for by, sel in candidates:
        try:
            el = WebDriverWait(driver, 2.5).until(EC.element_to_be_clickable((by, sel)))
            logging.info("Clicking entry chip: %s", safe_text(el))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            jitter(0.2, 0.5)
            el.click()
            jitter(0.8, 1.2)
            return True
        except Exception:
            continue
    return False


def _zoom_out_once(driver):
    try:
        btn = driver.find_element(By.XPATH, "//button[@aria-label='Zoom out']")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        jitter(0.1, 0.3)
        btn.click()
        jitter(0.3, 0.6)
    except Exception:
        pass


def scroll_results_pane(driver, seen: Optional[Set[str]] = None, category: str = "") -> None:
    _click_more_places_if_present(driver)
    feed = None
    try:
        feed = WebDriverWait(driver, 10).until(lambda d: _get_results_feed(d))
    except TimeoutException:
        logging.warning("Results feed not found; falling back to body scroll.")
    if feed is None:
        try:
            feed = driver.find_element(By.TAG_NAME, "body")
        except Exception:
            return
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'nearest'});", feed)
        jitter(0.15, 0.35)
        feed.click()
    except Exception:
        pass
    no_growth_runs = 0
    for i in range(MAX_SCROLL_TRIES):
        cards = driver.find_elements(By.CSS_SELECTOR, CARD_CONTAINER_CSS)
        count = len(cards)
        uniq = len(seen) if seen is not None else -1
        logging.info("[scroll %02d] visible_cards=%d%s", i + 1, count, (f" | uniques_so_far={uniq}" if uniq >= 0 else ""))
        prev_count = count
        try:
            prev_height = driver.execute_script("return arguments[0].scrollHeight", feed)
            prev_top = driver.execute_script("return arguments[0].scrollTop", feed)
        except Exception:
            prev_height = None; prev_top = None
        steps = random.randint(3, 6)
        for _ in range(steps):
            delta = random.randint(320, 800)
            try:
                driver.execute_script("arguments[0].scrollBy(0, arguments[1]);", feed, delta)
            except Exception:
                try:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
                except Exception:
                    pass
            jitter(0.25, 0.7)
        deadline = time.time() + random.uniform(5.5, 8.0)
        grew = False
        reached_end_hint = False
        while time.time() < deadline:
            try:
                cards_now = driver.find_elements(By.CSS_SELECTOR, CARD_CONTAINER_CSS)
                if len(cards_now) > prev_count:
                    grew = True
                    break
                if feed is not None:
                    h = driver.execute_script("return arguments[0].scrollHeight", feed)
                    t = driver.execute_script("return arguments[0].scrollTop", feed)
                    ch = driver.execute_script("return arguments[0].clientHeight", feed)
                    if prev_height is not None and h > prev_height + 12:
                        grew = True
                        break
                    if t + ch >= h - 4:
                        reached_end_hint = True
                        break
                try:
                    end_nodes = driver.find_elements(
                        By.XPATH,
                        "//span[contains(. ,\"You've reached the end\") or contains(. ,\"You\u2019ve reached the end\")] | //div[contains(. ,\"You've reached the end\") or contains(. ,\"You\u2019ve reached the end\")]",
                    )
                    if end_nodes:
                        reached_end_hint = True
                        break
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(0.25)
        if not grew:
            no_growth_runs += 1
        else:
            no_growth_runs = 0
        if reached_end_hint or no_growth_runs >= 3:
            logging.info("Stopping scroll: %s", "end-of-list" if reached_end_hint else f"no-growth x{no_growth_runs}")
            break


def build_search_url(query: str, location: str, hl: str = "en", gl: str = "eg") -> str:
    q = quote_plus(f"{query} in {location}")
    return f"https://www.google.com/maps/search/{q}?hl={hl}&gl={gl}"


def get_with_retry(driver, url: str, tries=2, cool=2.5):
    last = None
    for i in range(tries):
        try:
            driver.execute_cdp_cmd("Page.enable", {})
            driver.get(url)
            WebDriverWait(driver, PAGELOAD_TIMEOUT).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, CARD_CONTAINER_CSS)) > 0)
            return
        except (WebDriverException, ReadTimeoutError, NewConnectionError, MaxRetryError, TimeoutException) as e:
            last = e
            logging.warning("Navigation attempt %d/%d failed: %s", i + 1, tries, e)
            try:
                driver.get("about:blank")
            except Exception:
                pass
            time.sleep(cool)
    raise last if last else RuntimeError("navigation failed")


def harvest_category(driver, category: str, location: str, csv_path: str, seen: Set[str], max_places: int) -> int:
    url = build_search_url(category, location)
    logging.info("Navigating to search: %s", url)
    get_with_retry(driver, url, tries=2, cool=2.5)
    jitter(1.0, 1.6)
    _zoom_out_once(driver)
    _click_more_places_if_present(driver)
    scroll_results_pane(driver, seen=seen, category=category)
    cards = driver.find_elements(By.CSS_SELECTOR, CARD_CONTAINER_CSS)
    logging.info("Total cards discovered for '%s': %d", category, len(cards))
    total_written = 0
    for idx, card in enumerate(cards, start=1):
        try:
            basic = extract_card_basic(driver, card)
            profile_url = canonicalize_maps_url((basic.get("profile_url") or "").strip())
            if profile_url and profile_url in seen:
                continue
            detail = {}
            try:
                open_card_detail(driver, card)
                jitter(0.5, 1.1)
                detail = extract_detail(driver)
            except Exception:
                detail = {}
            name = detail.get("name") or basic.get("name") or ""
            slug_guess = slug_from_profile_url(profile_url)
            nm_norm = norm_name_for_compare(name)
            if slug_guess and nm_norm and nm_norm not in slug_guess:
                logging.warning("NAME_SLUG_MISMATCH | name='%s' | slug='%s' | url=%s", name, slug_guess, profile_url)
            address_line = detail.get("address") or basic.get("address_line") or ""
            address_line = re.sub(r'^\s*(Address|العنوان)\s*:\s*', '', address_line, flags=re.I)
            opening_hours = detail.get("opening_hours") or basic.get("opening_hours") or ""
            phone = detail.get("phone") or basic.get("phone") or ""
            website = detail.get("website") or basic.get("website") or ""
            rating = detail.get("rating") or ""
            reviews_count = detail.get("reviews_count") or ""
            plus_code = detail.get("plus_code") or ""
            place = Place(
                category=category,
                query_location=location,
                name=name,
                category_line=basic.get("category_line", ""),
                address_line=address_line,
                plus_code=plus_code,
                phone=phone,
                website=website,
                profile_url=profile_url,
                rating=rating,
                reviews_count=reviews_count,
                opening_hours=opening_hours,
                social_links=detail.get("social_links", ""),
                photo_urls=detail.get("photo_urls", ""),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            append_csv(csv_path, place)
            total_written += 1
            if profile_url:
                seen.add(profile_url)
            logging.info("[%s %d/%d] Saved: %s | %s", category, total_written, max_places, place.name, profile_url)
            if total_written >= max_places:
                logging.info("Reached max-places=%d for category '%s'", max_places, category)
                break
            jitter(0.5, 1.2)
        except StaleElementReferenceException:
            continue
        except Exception as e:
            logging.warning("Error on card %d: %s", idx, e)
            continue
    return total_written


def parse_args():
    p = argparse.ArgumentParser(description="Map-like places harvester with watchdog and per-category recycle")
    g = p.add_argument_group("Inputs")
    g.add_argument("--categories", type=str, default="", help="Comma-separated categories")
    g.add_argument("--categories-file", type=str, default="", help="Text file with one category per line")
    g.add_argument("--location", type=str, required=True, help="Search location")
    g.add_argument("--max-places", type=int, default=500, help="Max places per category")
    g.add_argument("--output", type=str, required=True, help="Output CSV path")
    r = p.add_argument_group("Runtime")
    r.add_argument("--headless", action="store_true", help="Run browser headless")
    r.add_argument("--proxy", type=str, default="", help="Optional proxy like http://user:pass@host:port")
    r.add_argument("--log", type=str, default="INFO", help="Logging level: DEBUG|INFO|WARNING|ERROR")
    return p.parse_args()


def load_categories(args) -> List[str]:
    cats: List[str] = []
    if args.categories_file and os.path.exists(args.categories_file):
        with open(args.categories_file, "r", encoding="utf-8") as f:
            cats = [ln.strip() for ln in f if ln.strip()]
    elif args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    return cats


def main():
    args = parse_args()
    level = getattr(logging, args.log.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.FileHandler("scraper.log", encoding="utf-8"), logging.StreamHandler(stream=sys.stdout)])
    categories = load_categories(args)
    if not categories:
        logging.error("No categories provided. Use --categories or --categories-file.")
        sys.exit(1)
    init_csv(args.output)
    seen = read_existing_profile_urls(args.output)
    logging.info("Loaded %d existing rows from %s", len(seen), args.output)
    driver = new_driver(headless=args.headless, proxy=args.proxy or None)
    total_all = 0
    try:
        for idx, cat in enumerate(categories, start=1):
            try:
                written = harvest_category(driver, cat, args.location, args.output, seen, args.max_places)
                total_all += written
            except (WebDriverException, ReadTimeoutError, NewConnectionError, MaxRetryError, TimeoutException) as e:
                logging.warning("Driver error while harvesting '%s': %s", cat, e)
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = new_driver(headless=args.headless, proxy=args.proxy or None)
                written = harvest_category(driver, cat, args.location, args.output, seen, args.max_places)
                total_all += written
            if idx % RESTART_EVERY_CATEGORIES == 0:
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = new_driver(headless=args.headless, proxy=args.proxy or None)
            else:
                try:
                    driver.execute_script("window.open('about:blank','_blank');")
                except Exception:
                    pass
            jitter(1.4, 2.8)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    logging.info("Done. Total rows written this run: %d", total_all)


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    return s.replace("\u00A0", " ").replace("\u202F", " ").strip()


if __name__ == "__main__":
    main()
