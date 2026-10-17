FROM apache/airflow:3.3.2-python3.12
USER root
# lightgbm cần thư viện OpenMP của hệ thống (stage dự báo, 2026-10-15)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/pipeline && chown -R airflow:0 /opt/pipeline
USER airflow
COPY deploy/airflow/requirements-pipeline.txt /tmp/requirements-pipeline.txt
RUN /opt/pipeline/bin/pip install --no-cache-dir -r /tmp/requirements-pipeline.txt
COPY --chown=airflow:0 scripts /opt/retail/scripts
COPY --chown=airflow:0 retail_dbt /opt/retail/retail_dbt
COPY --chown=airflow:0 apps/retail_app /opt/retail/apps/retail_app
COPY --chown=airflow:0 deploy/airflow/dags /opt/airflow/dags
WORKDIR /opt/retail
