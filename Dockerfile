FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
# pandoc: for document conversion
# git: for pip installs from git
# libgl1, libglib2.0-0: for opencv/vision libraries used by marker-pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    git \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH
RUN mkdir -p /run/sshd && \
    echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY input/ /app/input/

# Ensure output directory exists (optional, script handles it but good practice)
RUN mkdir -p /app/output

# Copy application code
COPY convert.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Expose SSH port
EXPOSE 22

ENTRYPOINT ["/app/entrypoint.sh"]

#   
CMD ["python", "convert.py", "/app/input", "--output", "/app/output"]
