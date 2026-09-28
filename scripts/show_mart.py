"""Quick look at the environment mart."""
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

print(client.command("""
SELECT city_name, date, temp_max_c, temp_min_c, total_precip_mm,
       rain_hours, pm25_max, pm25_mean
FROM urbanpulse.mart_environment_daily
ORDER BY city_name
FORMAT PrettyCompact
"""))
