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


if __name__ == "__main__":
    df = load_all()
    print(df.head())
    print(df.dtypes)
    print(df.groupby(["station", "item_type"]).size())
