import streamlit as st

import analyze
import build_db

st.set_page_config(page_title="ACC FBS Standings", layout="wide")
st.title("2026 ACC FBS Standings")

with st.spinner("Building database from the latest snapshot..."):
    build_db.main()

season = st.number_input("Season", min_value=2000, max_value=2100, value=2026, step=1)

standings = analyze.get_conference_standings(int(season))

if standings.empty:
    st.info(f"No ACC standings found for the {season} season yet.")
else:
    st.dataframe(standings, width="stretch")