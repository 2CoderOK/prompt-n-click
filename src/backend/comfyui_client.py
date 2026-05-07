import json
import time

import requests


def comfyui_wait_until_loaded(base_url: str, timeout: int = 120):
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # We hit the prompt endpoint
            response = requests.get(f"{base_url}/prompt", timeout=10)

            if response.status_code == 200:
                # we should get {"exec_info": {"queue_remaining": ...}}
                result = response.json()
                if "exec_info" in result:
                    print("ComfyUI is loaded and ready to generate.")
                    return True

            print("ComfyUI still loading...")

        except requests.exceptions.ConnectionError:
            # Server binary hasn't even opened the port yet
            pass

        time.sleep(10)  # Wait 10 seconds between polls

    raise TimeoutError(
        f"ComfyUI at {base_url} failed to load within {timeout} seconds."
    )


def queue_prompt(base_url: str, prompt_workflow: str) -> str:
    """Sends the workflow to ComfyUI and returns the Prompt ID."""
    p = {"prompt": prompt_workflow}
    try:
        data = json.dumps(p).encode("utf-8")

        response = requests.post(
            f"{base_url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return response.json()["prompt_id"]
    except Exception as e:
        print(f"Error connecting to ComfyUI: {e}")
        return None


def wait_for_image(base_url: str, prompt_id: str, timeout: int = 180) -> str | None:
    """Polls ComfyUI until the generation is complete."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/history/{prompt_id}")

            history = response.json()

            if prompt_id in history:
                # Generation finished! Extract the filename.
                outputs = history[prompt_id]["outputs"]
                for node_id in outputs:
                    if "images" in outputs[node_id]:
                        # Assuming one image per generation
                        return outputs[node_id]["images"][0]["filename"]
        except Exception as e:
            print(f"Error checking ComfyUI history: {e}")
        time.sleep(5)  # Wait 5 seconds before checking again

    raise TimeoutError(
        f"ComfyUI at {base_url} failed to generate image for prompt {prompt_id} within {timeout} seconds."
    )


def download_image(base_url: str, filename: str) -> bytes:
    url = f"{base_url}/view?filename={filename}&type=output"
    response = requests.get(url)
    response.raise_for_status()
    return response.content
