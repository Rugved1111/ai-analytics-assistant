import os
from dotenv import load_dotenv
from google import genai

load_dotenv()  # reads .env and turns each line into an environment variable

api_key = os.getenv("GEMINI_API_KEY")  # ask for the value by name
if not api_key:
    raise SystemExit("GEMINI_API_KEY not found. Check your .env file.")

print(f"Key loaded ({len(api_key)} characters). Calling Gemini...")

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-flash-latest",
    contents="Reply with exactly: Hello from Gemini!",
)
print(response.text)