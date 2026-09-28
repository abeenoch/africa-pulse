# Africa Pulse extensions for the official Airflow image.
# Pinned so local Docker runs use exactly the version named in the compose file.
FROM apache/airflow:2.10.4

# ClickHouse + project library dependencies only. The repo itself is bind-mounted.
COPY requirements.txt /tmp/africa-pulse-requirements.txt
RUN pip install --no-cache-dir -r /tmp/africa-pulse-requirements.txt
