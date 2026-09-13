FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock.txt requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY services services
RUN useradd -m app && mkdir -p /app/data && chown app:app /app/data
USER app
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "services.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
