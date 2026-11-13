"""
generate_data.py - builds fake (synthetic) radio data for the project.

Creates four CSV files in data/raw/:
  catalog.csv          - a small label catalog (the "source of truth")
  CXRA_asplayed.csv    - Station A log (Eastern time, 24h clock, has a Type column)
  station_b_log.csv    - Station B log (UTC timestamps, different column names)
  station_c_log.csv    - Station C log (12h clock, no type column at all)

Each station log is deliberately messy so the pipeline has real work to do:
duplicates, spelling variants, ads mixed with songs, missing ISRCs,
songs that aren't in the catalog, and a gap in one station's log.

All names, call signs and ISRCs are made up.

Run from the project folder:   python src/generate_data.py
"""

import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

random.seed(42)  # same "random" data every run, so results are repeatable

ET = ZoneInfo("America/Toronto")
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

WEEK_START = datetime(2026, 10, 26, 6, 0, tzinfo=ET)  # Monday 6:00 AM ET
DAYS = 7
BROADCAST_HOURS = 18  # 6 AM to midnight each day

# ---------------------------------------------------------------------------
# 1. Catalog
# ---------------------------------------------------------------------------
FIRST = ["Nova", "Kairo", "Lena", "Marcus", "Juno", "Theo", "Aria", "Dante",
         "Selah", "Remy", "Isla", "Malik", "Cora", "Zane", "Talia"]
LAST = ["Vale", "Reyes", "Okafor", "Lindqvist", "Hart", "Moreau", "Banks",
        "Ashby", "Quinn", "Delacroix", "Wren", "Osei"]
BANDS = ["The Northern Static", "Paper Satellites", "The Low Frequencies",
         "Glass Harbour", "The Midnight Relay"]
WORDS = ["Neon", "Gravity", "Summer", "Echo", "Ghost", "Golden", "Highway",
         "Fever", "Signal", "Ocean", "Paper", "Velvet", "Wildfire", "Static",
         "Midnight", "Satellite", "Heartbeat", "Shadow", "Daylight", "Chrome"]
ENDINGS = ["Lights", "Dreams", "Love", "Hearts", "Nights", "Rain", "Drive",
           "Waves", "Skies", "Roads", ""]
LABELS = ["Northline Records", "Bluewater Music", "Summit Sound", "Redwood Audio"]


def make_artist():
    if random.random() < 0.2:
        return random.choice(BANDS)
    return f"{random.choice(FIRST)} {random.choice(LAST)}"


def make_title():
    return f"{random.choice(WORDS)} {random.choice(ENDINGS)}".strip()


catalog = []
used_titles = set()
for i in range(60):
    title = make_title()
    while title in used_titles:
        title = make_title()
    used_titles.add(title)
    artist = make_artist()
    if random.random() < 0.15:  # some collaborations
        artist = f"{artist} feat. {make_artist()}"
    country = "CA" if random.random() < 0.45 else random.choice(["US", "GB"])
    catalog.append({
        "isrc": f"{country}X{random.choice('ABCDEFG')}{random.randint(10, 99)}26{i + 1:05d}",
        "title": title,
        "artist": artist,
        "is_cancon": country == "CA",
        "label": random.choice(LABELS),
        "duration_sec": random.randint(170, 260),
    })

with open(OUT / "catalog.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["isrc", "title", "artist", "is_cancon", "label"])
    w.writeheader()
    for t in catalog:
        w.writerow({k: t[k] for k in w.fieldnames})

# Songs stations play that are NOT in the catalog (should end up "unmatched")
NOT_IN_CATALOG = [
    {"isrc": "", "title": "Borrowed Time", "artist": "Kaia Strand", "is_cancon": False, "duration_sec": 205},
    {"isrc": "", "title": "Lantern", "artist": "Okin Ruse", "is_cancon": True, "duration_sec": 231},
    {"isrc": "", "title": "Cold Coffee", "artist": "Mira Fenn", "is_cancon": False, "duration_sec": 198},
    {"isrc": "", "title": "Tidewater", "artist": "The Quiet Engines", "is_cancon": True, "duration_sec": 244},
]

# ---------------------------------------------------------------------------
# 2. Build a "true" playlist per station (what actually aired)
# ---------------------------------------------------------------------------
cancon = [t for t in catalog if t["is_cancon"]]
other = [t for t in catalog if not t["is_cancon"]]

SPOTS = ["Maple Auto Group - Fall Sale", "Harbour Dental", "City Furniture Clearance",
         "QuickLoan Canada", "Fresh Market Weekly Deals", "Lakeside Insurance"]


def build_station(call_sign, cancon_share, gap_at=None):
    """Return a list of items in air order. cancon_share = chance a song is Canadian."""
    items = []
    for day in range(DAYS):
        t = WEEK_START + timedelta(days=day)
        end = t + timedelta(hours=BROADCAST_HOURS)
        next_break = t + timedelta(minutes=15)
        next_id = t
        while t < end:
            if t >= next_id:  # top-of-hour station ID
                items.append({"type": "ID", "title": f"{call_sign} Legal ID", "artist": "",
                              "isrc": "", "duration_sec": 10, "aired_at": t})
                t += timedelta(seconds=10)
                next_id += timedelta(hours=1)
                continue
            if t >= next_break:  # commercial break: 3 spots + a liner
                for _ in range(3):
                    items.append({"type": "SPOT", "title": random.choice(SPOTS), "artist": "",
                                  "isrc": "", "duration_sec": 30, "aired_at": t})
                    t += timedelta(seconds=30)
                items.append({"type": "LINER", "title": f"{call_sign} - More Music Variety",
                              "artist": "", "isrc": "", "duration_sec": 8, "aired_at": t})
                t += timedelta(seconds=8)
                next_break += timedelta(minutes=15)
                continue
            if random.random() < 0.02:
                song = random.choice(NOT_IN_CATALOG)
            elif random.random() < cancon_share:
                song = random.choice(cancon)
            else:
                song = random.choice(other)
            items.append({"type": "SONG", "title": song["title"], "artist": song["artist"],
                          "isrc": song["isrc"], "duration_sec": song["duration_sec"], "aired_at": t})
            t += timedelta(seconds=song["duration_sec"])

    if gap_at:  # remove ~20 minutes of log entries (a logging outage)
        gap_end = gap_at + timedelta(minutes=20)
        items = [x for x in items if not (gap_at <= x["aired_at"] < gap_end)]
    return items


# ---------------------------------------------------------------------------
# 3. Mess helpers
# ---------------------------------------------------------------------------
def messy_artist(name):
    r = random.random()
    if r < 0.08:
        return name.upper()
    if r < 0.12:
        return name + " "  # trailing space
    if r < 0.16 and name.startswith("The "):
        return name[4:] + ", The"
    if r < 0.22 and " feat. " in name:
        return name.replace(" feat. ", random.choice([" ft. ", " Feat ", " featuring "]))
    return name


def messy_title(title):
    r = random.random()
    if r < 0.07:
        return title + " (Radio Edit)"
    if r < 0.10:
        return title.lower()
    return title


def add_duplicates(rows, share=0.03):
    out = []
    for row in rows:
        out.append(row)
        if random.random() < share:
            out.append(dict(row))
    return out


def mmss(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def hhmmss(sec):
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------------------
# 4. Station A - CXRA: Eastern time, 24h, Type column, file name holds call sign
# ---------------------------------------------------------------------------
rows = []
for x in build_station("CXRA", cancon_share=0.38):
    rows.append({
        "Air Date": x["aired_at"].strftime("%Y-%m-%d"),
        "Air Time": x["aired_at"].strftime("%H:%M:%S"),
        "Type": x["type"],
        "Title": messy_title(x["title"]) if x["type"] == "SONG" else x["title"],
        "Artist": messy_artist(x["artist"]) if x["artist"] else "",
        "ISRC": "" if (x["type"] != "SONG" or random.random() < 0.05) else x["isrc"],
        "Dur": mmss(x["duration_sec"]),
    })
rows = add_duplicates(rows)
with open(OUT / "CXRA_asplayed.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"CXRA_asplayed.csv  {len(rows):>6} rows")

# ---------------------------------------------------------------------------
# 5. Station B - CXRB: UTC timestamps, different categories, no ISRC column,
#    and a 20-minute logging gap on Wednesday afternoon
# ---------------------------------------------------------------------------
CATEGORY = {"SONG": "music", "SPOT": "commercial", "ID": "imaging", "LINER": "imaging"}
gap = datetime(2026, 10, 28, 14, 0, tzinfo=ET)
rows = []
for x in build_station("CXRB", cancon_share=0.36, gap_at=gap):
    rows.append({
        "Station": "CXRB-FM",
        "Timestamp": x["aired_at"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Category": CATEGORY[x["type"]],
        "Song Title": messy_title(x["title"]) if x["type"] == "SONG" else x["title"],
        "Performer": messy_artist(x["artist"]) if x["artist"] else "",
        "Duration Sec": x["duration_sec"],
    })
rows = add_duplicates(rows)
with open(OUT / "station_b_log.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"station_b_log.csv  {len(rows):>6} rows")

# ---------------------------------------------------------------------------
# 6. Station C - CXRC: 12h clock, NO type column (ads just have a blank artist),
#    and a lower Canadian content share (should fail the 35% check)
# ---------------------------------------------------------------------------
rows = []
for x in build_station("CXRC", cancon_share=0.29):
    rows.append({
        "Call Sign": "CXRC",
        "Date": x["aired_at"].strftime("%m/%d/%Y"),
        "Start": x["aired_at"].strftime("%I:%M:%S %p").lstrip("0"),
        "Cut Title": messy_title(x["title"]) if x["type"] == "SONG" else x["title"],
        "Artist Name": messy_artist(x["artist"]) if x["artist"] else "",
        "ISRC": "" if (x["type"] != "SONG" or random.random() < 0.05) else x["isrc"],
        "Length": hhmmss(x["duration_sec"]),
    })
rows = add_duplicates(rows)
with open(OUT / "station_c_log.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print(f"station_c_log.csv  {len(rows):>6} rows")
print(f"catalog.csv        {len(catalog):>6} tracks")
print(f"Files written to {OUT}")
