# The Streamlit frontend and the only program running live during the showcase.
# 1. Calls build_db.py at startup to load the latest snapshot.
# 2. Uses analyze.py to display tables and multi-month trend charts of FBS records.
# 3. Reads and displays data/summary.md.
# 4. Hosts the live LLM chat interface strictly for answering user questions