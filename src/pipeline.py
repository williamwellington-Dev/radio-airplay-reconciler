import pandas as pd
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

COLUMNS = ["station", "played_at", "item_type", "title", "artist", "isrc", "duration_sec"]


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


if __name__ == "__main__":
    a = load_station_a()
    print(a.head())
    print(a.dtypes)