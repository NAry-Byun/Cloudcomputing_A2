FROM python:3.11-slim

WORKDIR /app

COPY app.py .
COPY lamda_handler.py .

RUN pip install flask boto3

EXPOSE 80

CMD ["python", "app.py"]
