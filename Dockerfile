FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .

# CPU-only torch — avoids pulling CUDA torch (~2GB) via sentence-transformers
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
RUN pip install --no-cache-dir -r requirements.txt

# Bake reranker weights into image — avoids cold-start HF Hub download
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2')"

COPY server/ server/
COPY config.yaml .
COPY data/ground_truth/ data/ground_truth/

RUN mkdir -p data/raw logs chroma_db

# HF Spaces requires non-root user UID 1000
RUN useradd -m -u 1000 user && chown -R user /app
USER user

# Prevent runtime HF Hub network calls — model is baked into image
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

EXPOSE 7860

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "7860"]
