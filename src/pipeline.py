import pandas as pd
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

COLUMNS = ["station", "played_at", "item_type", "title", "artist", "isrc", "duration_sec"]

CATEGORY_MAP = {"music": "song", "commercial": "spot", "imaging": "liner"}  # NEW


def mmss_to_sec(s):
    """'3:40' -> 220"""
    minutes, seconds = s.split(":")
    return int(minutes) * 60 + int(seconds)


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


if __name__ == "__main__":
    b = load_station_b()  # Station B
    print(b.head())
    print(b.dtypes)