# Runs on a schedule after fetch.py finishes.
# Passes current database state to the LLM (Gemini/Groq) to write a text overview of the FBS.
# Outputs to data/summary.md.