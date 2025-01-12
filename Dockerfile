FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY src/ .
COPY .env .

ENV PORT=8080

CMD exec gunicorn --bind :$PORT app:app
