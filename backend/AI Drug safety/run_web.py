try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import uvicorn

if __name__ == "__main__":
    uvicorn.run("ai_drug_safety.web:app", host="127.0.0.1", port=8000, reload=False)
