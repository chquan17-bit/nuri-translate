FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements-cloud.txt \
    && useradd --uid 10001 --create-home nuri
COPY nuri ./nuri
USER 10001
CMD ["python", "-m", "nuri.cloud_http"]
