import os
from openai import OpenAI
client = OpenAI(
base_url="https://api.groq.com/openai/v1",
api_key=os.environ["GROQ_API_KEY"],
)
MODEL = "openai/gpt-oss-120b"
response = client.chat.completions.create(
model=MODEL,
messages=[{"role": "user", "content": "Say hello in five words."}],
reasoning_effort="low",
)
print(response.choices[0].message.content)