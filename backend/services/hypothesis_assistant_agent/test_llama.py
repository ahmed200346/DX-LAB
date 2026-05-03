import requests

url = "http://localhost:11434/api/generate"

payload = {
    "model": "llama3.2:latest",
    "prompt": "Explain KRAS inhibitor resistance in simple terms.",
    "stream": False
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    data = response.json()
    print("\n🧠 Response:\n")
    print(data["response"])
else:
    print("❌ Error:", response.status_code, response.text)