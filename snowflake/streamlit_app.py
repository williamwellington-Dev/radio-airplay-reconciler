# Radio Airplay Reconciler - Streamlit in Snowflake
# Runs inside Snowflake on the AIRPLAY database built by scripts 01-05.
import os
import streamlit as st

st.set_page_config(page_title="Radio Airplay Reconciler", layout="wide")

# Connect to Snowflake (Streamlit in Snowflake container runtime)
conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()


@st.cache_data
def q(sql):
    return session.sql(sql).to_pandas()


st.title("Radio Airplay Reconciler")
st.caption("Three stations' as-played logs, cleaned and matched to the label catalog in Snowflake.")

stations = q("SELECT DISTINCT STATION FROM AIRPLAY.REPORTING.MATCHED_PLAYS ORDER BY 1")["STATION"].tolist()
picked = st.multiselect("Stations", stations, default=stations)
if not picked:
    st.warning("Pick at least one station.")
    st.stop()
in_list = ", ".join(f"'{s}'" for s in picked)

# --- Headline numbers -------------------------------------------------------
kpi = q(f"""
    SELECT COUNT(*)                                   AS PLAYS,
           COUNT_IF(ITEM_TYPE = 'song')               AS SONGS,
           COUNT_IF(MATCH_METHOD IN ('isrc','name'))  AS MATCHED,
           COUNT_IF(MATCH_METHOD = 'unmatched')       AS UNMATCHED
    FROM AIRPLAY.REPORTING.MATCHED_PLAYS WHERE STATION IN ({in_list})
""").iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Log entries", f"{kpi.PLAYS:,}")
c2.metric("Songs", f"{kpi.SONGS:,}")
c3.metric("Matched to catalog", f"{kpi.MATCHED / kpi.SONGS:.1%}")
c4.metric("Unmatched songs", f"{kpi.UNMATCHED:,}")

# --- Compliance -------------------------------------------------------------
st.subheader("Compliance checks")
report = q(f"""
    SELECT STATION, CHECK_NAME, VALUE, STATUS, DETAIL
    FROM AIRPLAY.REPORTING.COMPLIANCE_REPORT
    WHERE STATION IN ({in_list}) ORDER BY STATION, CHECK_NAME
""")
fails = report[report.STATUS == "FAIL"]
if len(fails):
    st.error(f"{len(fails)} failed check(s): " + "; ".join(fails.STATION + " " + fails.CHECK_NAME))
else:
    st.success("All checks passed.")
st.dataframe(report, use_container_width=True, hide_index=True)

# --- CanCon by day ----------------------------------------------------------
st.subheader("CanCon share by day (minimum 35%)")
daily = q(f"""
    SELECT PLAYED_AT::DATE AS DAY, STATION,
           ROUND(AVG(IFF(IS_CANCON = TRUE, 1, 0)) * 100, 1) AS CANCON_PCT
    FROM AIRPLAY.REPORTING.MATCHED_PLAYS
    WHERE ITEM_TYPE = 'song' AND STATION IN ({in_list})
    GROUP BY 1, 2 ORDER BY 1
""")
st.line_chart(daily.pivot(index="DAY", columns="STATION", values="CANCON_PCT"))

# --- How songs were matched -------------------------------------------------
st.subheader("How songs were matched")
methods = q(f"""
    SELECT STATION, MATCH_METHOD, COUNT(*) AS PLAYS
    FROM AIRPLAY.REPORTING.MATCHED_PLAYS
    WHERE ITEM_TYPE = 'song' AND STATION IN ({in_list})
    GROUP BY 1, 2
""")
st.bar_chart(methods.pivot(index="STATION", columns="MATCH_METHOD", values="PLAYS"))

# --- Review queue -----------------------------------------------------------
st.subheader("Review queue: unmatched songs")
st.caption("Closest catalog track by fuzzy similarity (0-100). 90+ = likely the same recording.")
st.dataframe(q("SELECT * FROM AIRPLAY.REPORTING.MATCH_SUGGESTIONS ORDER BY SIMILARITY DESC, PLAYS DESC"),
             use_container_width=True, hide_index=True)
