"""Row counts per raw table + sample of latest FX/GDELT payloads."""
import os

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

for t in ["open_meteo_weather", "open_meteo_air_quality", "fx_rates",
          "fx_frankfurter", "gdelt_news", "world_bank", "osm_infrastructure"]:
    n = client.command(f"SELECT count() FROM raw.{t}")
    print(f"raw.{t:24s} {n} rows")
