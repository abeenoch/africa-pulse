"""Show Day-3 marts/facts: FX, news intensity, economic indicators."""
import os

import clickhouse_connect
from dotenv import load_dotenv

load_dotenv()
c = clickhouse_connect.get_client(
    host=os.environ["CLICKHOUSE_HOST"],
    port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
    username=os.environ.get("CLICKHOUSE_USER", "default"),
    password=os.environ["CLICKHOUSE_PASSWORD"],
    secure=True,
)

print("== mart_fx_daily ==")
print(c.command("SELECT * FROM urbanpulse.mart_fx_daily FINAL ORDER BY currency, rate_date FORMAT PrettyCompact"))

print("== mart_news_daily ==")
print(c.command("SELECT * FROM urbanpulse.mart_news_daily FINAL ORDER BY date DESC, city_id LIMIT 12 FORMAT PrettyCompact"))

print("== fact_economic_indicator (latest years) ==")
print(c.command("""
SELECT country_code, indicator, year, value FROM urbanpulse.fact_economic_indicator FINAL
WHERE year >= 2022 ORDER BY country_code, indicator, year FORMAT PrettyCompact"""))

print("== fact_news_intensity row counts per city ==")
print(c.command("""
SELECT city_id, count() AS buckets, round(max(mention_intensity),3) AS peak
FROM urbanpulse.fact_news_intensity FINAL GROUP BY city_id ORDER BY city_id FORMAT PrettyCompact"""))
