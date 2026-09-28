"""
Dashboard validation harness (Africa Pulse).

Runs `dashboard/app.py` headlessly through Streamlit's AppTest runtime and
navigates every analytical page. Any exception raised inside the page body —
bad SQL column, IndexError on `st.columns(...)`, broken Altair/vega spec —
is surfaced here, so the dashboard can be regression-checked from the CLI
without a browser session.

Usage:
    python scripts/validate_dashboard.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import streamlit
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "dashboard" / "app.py"

PAGES = [
    "🏆 City Intelligence Index",
    "🚌 Mobility & Infrastructure",
    "🌱 Climate & Environment",
    "💱 Economic & FX Stability",
    "🔬 Cross-Domain Insights",
    "🛡️ Quality & Provenance Audit",
]


def run_page(page: str):
    """Execute the app with `page` selected and return the finished AppTest."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=300)
    at.run()
    if at.exception:
        return at, [f"[initial render] {e.value}" for e in at.exception]

    if not at.radio:
        return at, ["[sidebar] navigation radio widget was not registered"]

    selected = at.radio[0].set_value(page)
    selected.run()
    return at, []


def audit_metric_cards(at) -> list:
    """
    Assert no rendered st.metric card displays a missing figure.

    `nan`, `None` or `inf` in a headline KPI means the underlying mart join
    produced no match — exactly the class of defect that silently discredited
    the FX cards on the Economic page. Matching is word-bounded so ordinary
    copy such as "Infrastructure" is not flagged.
    """
    missing_token = re.compile(r"(?i)\bnan\b|\bnone\b|\binf\b|^-+$")
    problems = []
    for card in at.metric:
        label = str(card.label)
        for field_name, raw in (("value", card.value), ("delta", card.delta)):
            text = "" if raw is None else str(raw).strip()
            if not text:
                problems.append(f"{label} [{field_name}] is empty")
            elif missing_token.search(text):
                problems.append(f"{label} [{field_name}] = '{text}'")
    return problems


def main() -> int:
    # Windows consoles default to cp1252, which cannot encode the emoji in the
    # page names. Reconfigure stdout so the report always prints.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print(f"Africa Pulse dashboard validation — streamlit {streamlit.__version__}")
    print(f"App under test: {APP_PATH}\n")

    if not APP_PATH.exists():
        print(f"FAIL: app not found at {APP_PATH}")
        return 1

    failures: list = []
    for page in PAGES:
        at, errors = run_page(page)
        failures.extend(errors)

        metric_problems = audit_metric_cards(at) if not errors else []
        failures.extend(f"{page}: {p}" for p in metric_problems)

        # Count rendered visuals so the chart inventory per page is explicit and
        # a heading can never silently end up without its chart.
        chart_count = len(at.get("arrow_vega_lite_chart")) + len(at.get("vega_lite_chart"))

        cards = [
            f"{c.label} = {c.value}" + (f" (delta {c.delta})" if c.delta else "")
            for c in at.metric
        ]

        if errors or metric_problems:
            print(f"FAIL: {page}")
            for err in errors:
                print(f"      ERROR  {err}")
            for problem in metric_problems:
                print(f"      KPI    {problem}")
        else:
            print(
                f"PASS: {page}  [{len(at.metric)} KPI cards, {chart_count} charts, "
                f"{len(at.dataframe)} tables]"
            )
            for card in cards:
                print(f"      · {card}")

    print()
    if failures:
        print(f"DASHBOARD VALIDATION FAILED — {len(failures)} error(s).")
        return 1

    print(f"ALL {len(PAGES)} DASHBOARD PAGES RENDERED WITHOUT EXCEPTION!")
    print("All rendered KPI cards contain concrete, non-NaN figures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
