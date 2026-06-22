FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .

# CPU-only torch — avoids pulling CUDA torch (~2GB) via sentence-transformers
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY config.yaml .
COPY data/ground_truth/ data/ground_truth/

RUN mkdir -p data/raw logs chroma_db

# HF Spaces requires non-root user UID 1000
RUN useradd -m -u 1000 user && chown -R user /app
USER user

# Cache under /app so user 1000 owns it at both build and runtime
ENV HF_HOME=/app/.cache/huggingface

# Download reranker as user 1000 — offline flags NOT set yet so download works
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2')"

# Block runtime network calls — model already in HF_HOME cache
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 7860

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "7860"]
