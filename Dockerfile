# Use an official, lightweight Python 3.10 image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (Required for OpenCV to run headless in Docker)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the working directory
COPY requirements.txt .

# Optimize Docker Image Size: 
# Install the CPU-only version of PyTorch first. 
# This prevents ultralytics from downloading the massive 3GB CUDA version, keeping deployment fast and free.
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install the rest of your requirements + gunicorn (the production web server)
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the rest of your project into the container
COPY . .

# Specify a default port. 
# Hugging Face Spaces defaults to 7860. Render/Railway will override $PORT dynamically.
ENV PORT=7860
EXPOSE $PORT

# Start the application!
# Note: We specifically limit this to 1 worker process and use threads instead. 
# Machine Learning models consume a lot of RAM. Spawning multiple workers copies the model into RAM multiple times, which crashes free/small instances.
CMD gunicorn -b 0.0.0.0:$PORT --workers=1 --threads=8 --timeout=120 app:app
