# Use a slim Python image for a smaller footprint
FROM python:3.12-slim

# Install system dependencies
# ffmpeg is required for audio processing
# build-essential and others might be needed for some python packages like PyNaCl
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["python", "bot.py"]
