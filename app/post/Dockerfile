FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY post_service ./post_service

RUN mkdir -p /app/var

CMD ["python", "-m", "post_service.main", "run"]
