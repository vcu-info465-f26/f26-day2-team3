# Runs on a schedule after fetch.py finishes.
# Passes current database state to the LLM (Gemini/Groq) to write a text overview of the FBS.
# Outputs to data/summary.md.
import os
from pathlib import Path

from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")
secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
if not api_key and secrets_path.is_file():
	api_key = st.secrets.get("GROQ_API_KEY")

if not api_key:
	raise SystemExit(
		"GROQ_API_KEY is missing. Set it in the environment, .env, "
		"or .streamlit/secrets.toml."
	)

client = OpenAI(
	base_url="https://api.groq.com/openai/v1",
	api_key=api_key,
)
MODEL = "openai/gpt-oss-120b"
response = client.chat.completions.create(
model=MODEL,
messages=[{"role": "user", "content": "Say hello in five words."}],
reasoning_effort="low",
)
print(response.choices[0].message.content)