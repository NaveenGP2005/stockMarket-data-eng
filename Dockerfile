# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python dependencies
COPY requirements-rag.txt .
RUN pip install --no-cache-dir -r requirements-rag.txt

# Copy the rest of the application files
COPY agent_brain.py app.py ./

# Create directory for ChromaDB local storage
RUN mkdir -p chroma_db

# Expose port
EXPOSE 8501

# Healthcheck to verify Streamlit container health
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start the Streamlit application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
