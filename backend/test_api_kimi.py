import os
import requests

invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
stream = False

api_key = "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"

headers = {
  "Authorization": f"Bearer {api_key}",
  "Accept": "text/event-stream" if stream else "application/json"
}

payload = {
  "model": "moonshotai/kimi-k2.6",
  "messages": [{"role":"user","content":"Hello!"}],
  "max_tokens": 100,
  "temperature": 1.00,
  "top_p": 1.00,
  "stream": stream,
  "chat_template_kwargs": {"thinking": True},
}

try:
    response = requests.post(invoke_url, headers=headers, json=payload, stream=stream, timeout=60)
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(response.text)
    else:
        print(response.json())
except Exception as e:
    print(f"Error: {e}")
