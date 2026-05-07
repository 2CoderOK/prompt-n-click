FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY frontend/ /app
COPY shared/ /app/shared

ENV PYTHONPATH="/app"
# Expose Streamlit port
EXPOSE 8501
# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]