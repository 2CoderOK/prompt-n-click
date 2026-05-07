import requests
import os
import time


def llamacpp_call(
    base_url: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    is_json: bool = False,
) -> str:

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    if is_json:
        payload["response_format"] = {"type": "json_object"}
    response = requests.post(f"{base_url}/v1/chat/completions", json=payload)
    response.raise_for_status()

    # Parse the JSON response
    result = response.json()
    print(f"LLM response:\n{result}\n{len(str(result))} chars")
    reply = result["choices"][0]["message"]["content"]
    if result["choices"][0]["finish_reason"] != "stop":
        print("Warning: LLM response may have been cut off due to max_tokens limit.")
        raise ValueError(
            f"LLM response is empty. finish reason != 'stop' {result['choices'][0]['finish_reason']}. Context size ({max_tokens}) is set too low for this step ..."
        )

    return reply


def llamacpp_wait_until_loaded(base_url: str, timeout: int = 180):
    """
    Polls the llama.cpp /health endpoint.
    Llama.cpp returns:
    - ConnectionError: If the server hasn't started the binary yet.
    - 503/Loading: If the server is up but weights are still moving to VRAM.
    - 200 OK: When the model is fully loaded and ready.
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # We hit the health endpoint
            response = requests.get(f"{base_url}/health", timeout=2)

            if response.status_code == 200:
                # we should get {"status":"ok"}
                result = response.json()
                if result.get("status") == "ok":
                    print("LLM is loaded and ready to generate.")
                    return True

            # If it's 503, it means the server is up but model is still loading
            if response.status_code == 503:
                print("Model still loading into GPU...")

        except requests.exceptions.ConnectionError:
            # Server binary hasn't even opened the port yet
            pass

        time.sleep(10)  # Wait 10 seconds between polls

    raise TimeoutError(f"LLM at {base_url} failed to load within {timeout} seconds.")
