FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK data so entity extraction works on cold starts
# (NLTK 3.8.2+ renamed punkt -> punkt_tab, averaged_perceptron_tagger ->
# averaged_perceptron_tagger_eng, maxent_ne_chunker -> maxent_ne_chunker_tab).
RUN python -m nltk.downloader -d /usr/local/share/nltk_data \
        punkt_tab \
        averaged_perceptron_tagger_eng \
        maxent_ne_chunker_tab \
        words \
    && python -c "import nltk; nltk.data.path.insert(0, '/usr/local/share/nltk_data'); \
        import os; os.environ['NLTK_DATA']='/usr/local/share/nltk_data'; \
        print('nltk data installed at', nltk.data.path)"

# Copy app
COPY config/ ./config/
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY ui/ ./ui/

RUN mkdir -p /app/data

# Use startup script
CMD ["./scripts/startup.sh", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
