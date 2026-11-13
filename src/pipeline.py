import re

import numpy as np
import pandas as pd
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

COLUMNS = ["station", "played_at", "item_type", "title", "artist", "isrc", "duration_sec"]

CATEGORY_MAP = {"music": "song", "commercial": "spot", "imaging": "liner"}


def mmss_to_sec(s):
    """'3:40' -> 220"""
    minutes, seconds = s.split(":")
    return int(minutes) * 60 + int(seconds)


# Station A
def load_station_a():
    df = pd.read_csv(RAW / "CXRA_asplayed.csv")
    out = pd.DataFrame({
        "station": "CXRA",
        "played_at": pd.to_datetime(df["Air Date"] + " " + df["Air Time"]),
        "item_type": df["Type"].str.lower(),
        "title": df["Title"],
        "artist": df["Artist"],
        "isrc": df["ISRC"],
        "duration_sec": df["Dur"].apply(mmss_to_sec),
    })
    return out[COLUMNS]


# Station B
def load_station_b():
    df = pd.read_csv(RAW / "station_b_log.csv")
    out = pd.DataFrame({
        "station": "CXRB",
        "played_at": pd.to_datetime(df["Timestamp"]).dt.tz_convert("America/Toronto").dt.tz_localize(None),
        "item_type": df["Category"].map(CATEGORY_MAP),
        "title": df["Song Title"],
        "artist": df["Performer"],
        "isrc": None,
        "duration_sec": df["Duration Sec"],
    })
    return out[COLUMNS]


# Station C
def load_station_c():
    df = pd.read_csv(RAW / "station_c_log.csv")
    out = pd.DataFrame({
        "station": "CXRC",
        "played_at": pd.to_datetime(df["Date"] + " " + df["Start"], format="%m/%d/%Y %I:%M:%S %p"),
        "item_type": np.where(df["Artist Name"].notna(), "song", "other"),
        "title": df["Cut Title"],
        "artist": df["Artist Name"],
        "isrc": df["ISRC"],
        "duration_sec": pd.to_timedelta(df["Length"]).dt.total_seconds().astype(int),
    })
    return out[COLUMNS]


# Combine all three stations into one table
def load_all():
    combined = pd.concat(
        [load_station_a(), load_station_b(), load_station_c()],
        ignore_index=True,
    )
    before = len(combined)
    combined = combined.drop_duplicates(subset=["station", "played_at", "title"])
    print(f"Removed {before - len(combined)} duplicate rows")
    return combined.sort_values(["station", "played_at"]).reset_index(drop=True)


# Cleaning: make messy names comparable
def clean_text(s):
    """'  Golden Rain (Radio Edit) ' -> 'golden rain'"""
    if pd.isna(s):
        return s
    s = str(s).strip().lower()
    s = re.sub(r"\s*\((radio edit|edit|clean)\)", "", s)      # drop version tags
    s = re.sub(r"^(.*), the$", r"the \1", s)                    # 'midnight relay, the' -> 'the midnight relay'
    s = re.sub(r"\s+(featuring|feat\.?|ft\.?)\s+", " feat. ", s)  # one spelling of 'feat.'
    s = re.sub(r"\s+", " ", s)                                   # squeeze extra spaces
    return s


def add_clean_columns(df):
    df = df.copy()
    df["title_clean"] = df["title"].apply(clean_text)
    df["artist_clean"] = df["artist"].apply(clean_text)
    return df


# Matching: tie each song play to a catalog track
def match_catalog(df, catalog):
    """ISRC first (exact ID), then cleaned title + artist as a fallback."""
    cat = catalog[["isrc", "title_clean", "artist_clean", "is_cancon", "label"]].rename(
        columns={"isrc": "catalog_isrc"})
    songs = df[df["item_type"] == "song"].copy()
    other = df[df["item_type"] != "song"].copy()

    # 1) ISRC match
    by_isrc = songs.merge(cat[["catalog_isrc", "is_cancon", "label"]],
                          left_on="isrc", right_on="catalog_isrc", how="left")
    hit = by_isrc["catalog_isrc"].notna()
    matched_isrc = by_isrc[hit].assign(match_method="isrc")

    # 2) Name match for everything ISRC couldn't find
    leftover = songs[~hit.values]
    by_name = leftover.merge(cat, on=["title_clean", "artist_clean"], how="left")
    by_name["match_method"] = np.where(by_name["catalog_isrc"].notna(), "name", "unmatched")

    other["match_method"] = "not_music"
    result = pd.concat([matched_isrc, by_name, other], ignore_index=True)
    return result.sort_values(["station", "played_at"]).reset_index(drop=True)


if __name__ == "__main__":
    df = add_clean_columns(load_all())
    catalog = add_clean_columns(pd.read_csv(RAW / "catalog.csv"))
    result = match_catalog(df, catalog)

    print(result.groupby(["station", "match_method"]).size().unstack(fill_value=0))
    print()
    print("Unmatched songs:")
    print(result[result["match_method"] == "unmatched"][["title_clean", "artist_clean"]].value_counts())
