import docker
import os
import shlex
from shared.constants import ALL_WORKERS, WORKER_LLAMACPP

LLAMACPP_PORT = int(os.getenv("LLAMACPP_LLM_PORT", 8090))
LLAMACPP_MODEL_PATH_SRC = os.getenv(
    "LLAMACPP_LLM_MODEL_PATH_SRC", "/usr/local/ai/models"
)
LLAMACPP_MODEL_PATH_DEST = os.getenv(
    "LLAMACPP_LLM_MODEL_PATH_DEST", "/usr/local/ai/models"
)
PROJECT_NAME = os.getenv("DOCKER_PROJECT_NAME", "ai_game_studio")
LLAMACPP_LABEL_PROFILE_ID = "com.ggclaw.llm_profile_id"

try:
    client = docker.from_env()
    client.ping()
    print("Docker socket connected successfully.")
except Exception as e:
    print(f"ERROR: Could not connect to Docker socket: {e}")
    client = None


class ContainerManager:
    @staticmethod
    def start_worker(target_name: str) -> None:
        """Start target worker container, stopping all others to free VRAM."""
        if not client:
            print("Docker client not initialized. Cannot manage workers.")
            return

        if target_name not in ALL_WORKERS or target_name == WORKER_LLAMACPP:
            print(f"Invalid worker name '{target_name}' for start_worker.")
            return

        # Ensure the custom LLM worker isn't hogging VRAM
        ContainerManager.stop_llamacpp_worker()

        for name in ALL_WORKERS:
            try:
                container = client.containers.get(name)
                if name == target_name:
                    print(f"Starting {name}...")
                    if container.status == "running":
                        print(f"{name} is already running.")
                    else:
                        container.start()
                else:
                    if container.status == "running":
                        print(f"Stopping {name} to free memory...")
                        container.stop()
            except docker.errors.NotFound:
                continue

    @staticmethod
    def stop_workers() -> None:
        """Stop all worker containers."""
        if not client:
            print("Docker client not initialized. Cannot manage workers.")
            return

        ContainerManager.stop_llamacpp_worker()

        for name in ALL_WORKERS:
            if name == WORKER_LLAMACPP:
                continue  # Skip stopping the custom worker here
            try:
                container = client.containers.get(name)
                if container.status == "running":
                    print(f"Stopping {name}...")
                    container.stop()
            except docker.errors.NotFound:
                continue

    # ==========================================
    # NEW CUSTOM WORKER LOGIC
    # ==========================================

    @staticmethod
    def stop_llamacpp_worker() -> None:
        """Stop and completely remove the custom worker container."""
        if not client:
            return

        try:
            container = client.containers.get(WORKER_LLAMACPP)
            print(f"Stopping and removing custom worker {WORKER_LLAMACPP}...")
            container.remove(force=True)  # force=True handles both stop and remove
        except docker.errors.NotFound:
            pass  # Container doesn't exist, which is fine

    @staticmethod
    def start_llamacpp_worker(command_str: str, profile_id: int | None = None) -> None:
        """
        Starts the llamacpp worker with the given command string.

        If a container is already running with the same profile_id (tracked via a
        Docker label), it is reused and no restart occurs.  Otherwise, all standard
        workers are stopped to free VRAM, the old container is removed, and a fresh
        one is spawned.
        """
        if not client:
            print("Docker client not initialized. Cannot manage custom worker.")
            return

        # 1. Check if the currently-running container already uses this profile.
        if profile_id is not None:
            try:
                container = client.containers.get(WORKER_LLAMACPP)
                if container.status == "running":
                    active_profile = container.labels.get(LLAMACPP_LABEL_PROFILE_ID)
                    if active_profile == str(profile_id):
                        print(
                            f"[llamacpp] Reusing running container — profile {profile_id} already loaded."
                        )
                        return
            except docker.errors.NotFound:
                pass  # No container running; proceed to spawn one

        # 2. Stop all standard workers to free VRAM
        ContainerManager.stop_workers()

        # 3. Clean up any previous instance of the custom worker
        ContainerManager.stop_llamacpp_worker()

        # 4. Parse the command string safely
        # shlex.split correctly parses quotes and spaces just like a bash terminal
        parsed_command = shlex.split(command_str)

        # 5. Get the network name (from your updated docker-compose)
        network_name = os.getenv("DOCKER_NETWORK", "game_studio_network")

        # 6. Spawn the custom container, stamping the active profile id as a label
        print(
            f"Spawning custom worker '{WORKER_LLAMACPP}' (src:{LLAMACPP_MODEL_PATH_SRC}, dst:{LLAMACPP_MODEL_PATH_DEST}) on port {LLAMACPP_PORT}..."
        )
        labels = {
            "com.docker.compose.project": PROJECT_NAME,
            "com.docker.compose.service": "llamacpp",
        }
        if profile_id is not None:
            labels[LLAMACPP_LABEL_PROFILE_ID] = str(profile_id)

        client.containers.run(
            image="snowgoons/llamacpp:llamacpp-b8864-cuda75",
            name=WORKER_LLAMACPP,
            command=parsed_command,
            detach=True,
            network=network_name,
            ports={f"{LLAMACPP_PORT}/tcp": LLAMACPP_PORT},
            volumes={
                LLAMACPP_MODEL_PATH_SRC: {
                    "bind": LLAMACPP_MODEL_PATH_DEST,
                    "mode": "ro",
                }
            },
            device_requests=[
                docker.types.DeviceRequest(count=1, capabilities=[["gpu"]])
            ],
            labels=labels,
        )
        print(f"{WORKER_LLAMACPP} spawned successfully.")
