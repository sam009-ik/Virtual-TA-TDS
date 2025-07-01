# Dockerfile

# 1. Base image with a known-good Python version
FROM python:3.10-slim

# 2. Set working dir
WORKDIR /app

# 3. Copy requirements and install build tools + deps
COPY requirements.txt .
RUN pip install --no-cache-dir setuptools>=65.0.0 wheel \
    && pip install --no-cache-dir -r requirements.txt

# 4. Copy your app code
COPY . .

# 5. Expose the port and set the start command
EXPOSE 8000
CMD ["uvicorn", "vta_api2:app", "--host", "0.0.0.0", "--port", "8000"]
