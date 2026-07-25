FROM python:3.12-slim

WORKDIR /populate

RUN pip install --no-cache-dir requests

COPY populate_graph.py graph.json index_cache.jsonl ./

CMD ["python", "populate_graph.py"]
