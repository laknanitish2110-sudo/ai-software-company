FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN curl -L -o workflows.db https://github.com/laknanitish2110-sudo/ai-software-company/releases/download/v1.4.0/workflows.db \
    && echo "workflows.db downloaded: $(du -h workflows.db | cut -f1)"

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
