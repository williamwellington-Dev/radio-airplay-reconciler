"""Data-quality and CanCon compliance checks on the matched airplay table."""
import pandas as pd

from pipeline import RAW, add_clean_columns, load_all, match_catalog

CANCON_MIN = 0.35        # CRTC minimum share of Canadian popular music
GAP_LIMIT_MIN = 2        # dead air / missing log longer than this gets flagged


def row(station, check, value, status, detail=""):
    return {"station": station, "check": check, "value": value, "status": status, "detail": detail}


def check_cancon(result):
    """CanCon share of songs: whole week, and Mon-Fri 6am-6pm. Unmatched songs count as non-Canadian."""
    rows = []
    songs = result[result["item_type"] == "song"].copy()
    songs["cancon"] = songs["is_cancon"].eq(True)
    daytime = songs[(songs["played_at"].dt.dayofweek < 5) & (songs["played_at"].dt.hour.between(6, 17))]

    for label, data in [("CanCon - full week", songs), ("CanCon - weekday 6am-6pm", daytime)]:
        for station, g in data.groupby("station"):
            share = g["cancon"].mean()
            status = "PASS" if share >= CANCON_MIN else "FAIL"
            rows.append(row(station, label, f"{share:.1%}", status,
                            f"{g['cancon'].sum()} of {len(g)} songs (min {CANCON_MIN:.0%})"))
    return rows


def check_log_gaps(result):
    """Gaps between one item ending and the next starting, ignoring the overnight break."""
    rows = []
    for station, g in result.groupby("station"):
        g = g.sort_values("played_at")
        ends = g["played_at"] + pd.to_timedelta(g["duration_sec"], unit="s")
        nxt = g["played_at"].shift(-1)
        gap_min = (nxt - ends).dt.total_seconds() / 60
        same_day = nxt.dt.date == g["played_at"].dt.date
        gaps = g.loc[(gap_min > GAP_LIMIT_MIN) & same_day, "played_at"]
        if len(gaps) == 0:
            rows.append(row(station, "Log gaps", 0, "PASS"))
        else:
            detail = "; ".join(f"{t:%a %b %d %H:%M} ({gap_min[i]:.0f} min)" for i, t in gaps.items())
            rows.append(row(station, "Log gaps", len(gaps), "FAIL", detail))
    return rows


def check_unmatched(result):
    """Song plays that couldn't be tied to a catalog track."""
    rows = []
    for station, g in result[result["item_type"] == "song"].groupby("station"):
        un = g[g["match_method"] == "unmatched"]
        status = "PASS" if len(un) == 0 else "WARN"
        titles = ", ".join(sorted(un["title_clean"].str.title().unique()))
        rows.append(row(station, "Unmatched songs", len(un), status, titles))
    return rows


def check_missing_isrc(result):
    """Share of song plays logged without an ISRC (forces weaker name matching)."""
    rows = []
    for station, g in result[result["item_type"] == "song"].groupby("station"):
        missing = g["isrc"].isna().mean()
        status = "PASS" if missing < 0.10 else "WARN"
        rows.append(row(station, "Songs missing ISRC", f"{missing:.1%}", status))
    return rows


def run_all_checks():
    df = add_clean_columns(load_all())
    catalog = add_clean_columns(pd.read_csv(RAW / "catalog.csv"))
    result = match_catalog(df, catalog)
    rows = check_cancon(result) + check_log_gaps(result) + check_unmatched(result) + check_missing_isrc(result)
    return pd.DataFrame(rows).sort_values(["station", "check"]).reset_index(drop=True)


if __name__ == "__main__":
    report = run_all_checks()
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 70)
    print(report.to_string(index=False))
    print()
    print(report["status"].value_counts())
