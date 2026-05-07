# Use a newer PyTorch image that supports the custom_op API (Torch 2.4+)
FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    git \
    wget \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8188

# The Magic Command: It checks the mapped volume, installs the Manager if needed, then boots ComfyUI.
CMD sh -c "if [ ! -d '/app/custom_nodes/ComfyUI-Manager' ]; then git clone https://github.com/ltdrdata/ComfyUI-Manager.git /app/custom_nodes/ComfyUI-Manager; fi && python main.py --listen 0.0.0.0 --lowvram --force-fp16 --fp16-vae --bf16-unet --disable-pinned-memory"