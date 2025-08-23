# champ/llm/provider.py
import os
import json
import time
import random
import requests
import certifi

class ProviderError(RuntimeError):
    pass

# Retry on rate limit / transient server errors
RETRY_STATUS = {429, 500, 502, 503, 504}

def _resolved_model(explicit_model: str | None) -> str:
    """
    Resolve the model to call in this order:
    1) explicit model parameter
    2) LLM_MODEL environment variable
    3) safe default "gemini-2.0-flash"
    """
    return (explicit_model or os.getenv("LLM_MODEL") or "gemini-2.0-flash").strip()

def _make_body(system_prompt: str, user_prompt: str):
    # Keep the payload small and JSON-safe
    return {
        "systemInstruction": {
            "parts": [{"text": str(system_prompt or "")}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": str(user_prompt or "")}]
            }
        ]
    }

def call_llm_text(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """
    Synchronous text call to Gemini API with robust retries and clear error messages.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ProviderError("Missing GEMINI_API_KEY")

    model_name = _resolved_model(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    body = _make_body(system_prompt, user_prompt)

    attempts = int(os.getenv("LLM_RETRIES", "4"))
    base = float(os.getenv("LLM_BACKOFF_BASE", "0.5"))

    last_err_text = None
    last_status = None

    for i in range(attempts):
        try:
            resp = requests.post(
                url,
                headers=headers,
                params=params,
                data=json.dumps(body, ensure_ascii=False),
                timeout=30,
                verify=certifi.where(),
            )
            last_status = resp.status_code

            # Retry on transient statuses
            if resp.status_code in RETRY_STATUS:
                last_err_text = resp.text
                if i < attempts - 1:
                    sleep = base * (2 ** i) * (0.8 + 0.4 * random.random())
                    time.sleep(sleep)
                    continue

            resp.raise_for_status()
            data = resp.json()

            # Defensive parsing
            candidates = data.get("candidates") or []
            if not candidates:
                raise ProviderError(f"Empty or malformed response (no candidates). status={last_status}, body={data}")

            parts = (candidates[0].get("content") or {}).get("parts") or []
            for p in parts:
                if isinstance(p, dict) and "text" in p:
                    return p["text"]

            # Fallback to raw JSON if no 'text' field found
            return json.dumps(data)

        except requests.exceptions.RequestException as e:
            # Network or HTTP error path
            # Retry if allowed; otherwise surface a clear provider error
            last_err_text = getattr(getattr(e, "response", None), "text", last_err_text)
            if i < attempts - 1:
                sleep = base * (2 ** i) * (0.8 + 0.4 * random.random())
                time.sleep(sleep)
                continue

            # Compose informative error with last known status/body
            msg = f"{e}"
            if last_status is not None:
                msg = f"HTTP {last_status}: {msg}"
            if last_err_text:
                msg += f" | body: {last_err_text}"
            raise ProviderError(f"LLM call failed: {msg}")

def safe_call_llm(system_prompt: str, user_prompt: str, model: str | None = None):
    """
    Wrapper that never raises; returns (text, unavailable_flag).
    When unavailable_flag is True, the caller should use a deterministic fallback.
    """
    try:
        txt = call_llm_text(system_prompt, user_prompt, model=model)
        return txt, False
    except ProviderError as e:
        # Optional: uncomment the print for temporary debugging
        print("LLM ProviderError:", e)
        return None, True
