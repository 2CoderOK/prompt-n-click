import threading
import traceback
from fastapi import FastAPI, HTTPException

from worker import process_jobs

app = FastAPI(title="VoxCPM Audio Worker API")

_lock = threading.Lock()
_is_running = False


def _run_in_background(project_id: str) -> None:
    global _is_running
    try:
        process_jobs(project_id)
    except SystemExit:
        # process_jobs calls sys.exit() on missing/invalid jobs — safe to swallow in thread
        pass
    except Exception:
        traceback.print_exc()
    finally:
        with _lock:
            _is_running = False


@app.post("/run/{project_id}")
def run(project_id: str):
    global _is_running
    with _lock:
        if _is_running:
            raise HTTPException(
                status_code=409, detail="Voiceover generation already running"
            )
        _is_running = True

    thread = threading.Thread(
        target=_run_in_background, args=(project_id,), daemon=True
    )
    thread.start()
    return {"status": "started", "project_id": project_id}


@app.get("/status")
def status():
    return {"running": _is_running}
