import httpx
from openai import OpenAI

http_client = httpx.Client(verify=False) # Désactive la vérification du certificat TLS/SSL

client = OpenAI(
    api_key="YOUR_API_KEY", # sk-e94c1284c96146beb589473f40488764
    base_url="https://tokenfactory.esprit.tn/api",
    http_client=http_client
)

response = client.chat.completions.create(
    model="hosted_vllm/Llama-3.1-70B-Instruct",
    messages=[
        {"role": "system", "content": "Tu es un assistant utile et concis."},
        {"role": "user", "content": "Explique-moi simplement pourquoi le ciel est bleu."}
    ],
    temperature=0.7,
    max_tokens=300,
    top_p=0.9,
    frequency_penalty=0.0,
    presence_penalty=0.0
)

print(response.choices[0].message.content)