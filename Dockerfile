FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/app/.cache
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
COPY backend/ .
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
