FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .

# Install CPU-only torch before requirements.txt so sentence-transformers does not pull
# the default CUDA-enabled torch (~2GB). CUDA torch OOMs on Render's 512MB free tier.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download cross-encoder reranker at build time to avoid cold-start timeout
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2')"

COPY server/ server/
COPY config.yaml .
COPY data/ground_truth/ data/ground_truth/

RUN mkdir -p data/raw logs

# Prevent HuggingFace Hub network calls at runtime — model is baked into image
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
