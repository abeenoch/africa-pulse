"""Verify ClickHouse Cloud connectivity and apply raw-layer DDL.
Usage: python scripts/test_connection.py
"""
import os
import re
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()

client = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
    username=os.environ.get("CLICKHOUSE_USER", "default"),
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=True,
)
print("CONNECTED. Server version:", client.command("SELECT version()"))

# Apply raw DDL (statement-by-statement; clickhouse-connect runs one at a time)
ddl = Path("warehouse/ddl/00_raw.sql").read_text(encoding="utf-8")
ddl = re.sub(r"--.*", "", ddl)  # strip comments
for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
    client.command(stmt)
    print("applied:", stmt.split("\n")[0][:60], "...")

print("raw tables:", client.command("SHOW TABLES FROM raw"))
