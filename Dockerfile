FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for building procgen
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    qt5-qmake \
    qtbase5-dev \
    libqt5opengl5-dev \
    libglib2.0-0 \
    libgl1-mesa-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (without procgen since we'll build it locally)
COPY tutorial_requirements.txt .

# Install Python dependencies except procgen
# Also install gym (old OpenAI gym), gym3, and filelock which procgen requires
RUN grep -v "procgen" tutorial_requirements.txt > temp_requirements.txt && \
    pip install --no-cache-dir -r temp_requirements.txt && \
    pip install --no-cache-dir gym==0.26.2 gym3==0.3.0 filelock && \
    rm temp_requirements.txt

# Copy procgen source code first
COPY procgen/ ./procgen/
COPY procgen-build/ ./procgen-build/

# Clean any existing build artifacts from Windows
RUN rm -rf ./procgen/.build

# Install procgen-build helper (provides cmake and gym3)
WORKDIR /app/procgen-build
RUN pip install --no-cache-dir -e .

# Build the procgen C++ library
WORKDIR /app/procgen
RUN python -c "from builder import build; build()"

# Return to app directory
WORKDIR /app

# Copy the rest of the application
COPY . .

# Expose the port the app runs on
# EXPOSE 8001
EXPOSE 8002

# Command to run the application
CMD ["python", "_app.py"] 
# CMD ["python", "tutorial_app.py"]