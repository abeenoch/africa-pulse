

from datetime import datetime

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

PROJECT_DIR = Variable.get("AFRICA_PULSE_DIR", default_var="/opt/airflow/africa-pulse")
CLI_TIMEOUT_SECONDS = int(Variable.get("AFRICA_PULSE_CLI_TIMEOUT", default_var="600"))


def run_stage_python(stage_name: str, command: list):
    """Execute one platform stage with the worker's own Python interpreter."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, *command],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_SECONDS,
    )
    log_lines = (proc.stdout or "") + (proc.stderr or "")
    print(log_lines[-8000:])
    if proc.returncode != 0:
        raise RuntimeError(
            f"Africa Pulse stage '{stage_name}' failed with code {proc.returncode}"
        )


with DAG(
    dag_id="africa_pulse_pipeline",
    description="Africa Pulse: ingestion → raw sync → marts → quality gates",
    schedule="@daily",
    start_date=datetime(2026, 9, 25),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=None,
    tags=["africa-pulse", "clickhouse", "urban-intelligence"],
    default_args={
        "owner": "africa-pulse",
        "retries": 2,
        "depends_on_past": False,
    },
) as dag:
    acquisition = PythonOperator(
        task_id="acquisition",
        python_callable=run_stage_python,
        op_kwargs={
            "stage_name": "acquisition",
            "command": ["-m", "ingestion.run_ingestion"],
        },
    )

    raw_sync = PythonOperator(
        task_id="raw_sync",
        python_callable=run_stage_python,
        op_kwargs={
            "stage_name": "raw_sync",
            "command": ["-m", "ingestion.load_raw_to_clickhouse"],
        },
    )

    conformed_marts = PythonOperator(
        task_id="conformed_marts",
        python_callable=run_stage_python,
        op_kwargs={
            "stage_name": "conformed_marts",
            "command": ["-m", "warehouse.transform"],
        },
    )

    quality_gates = PythonOperator(
        task_id="quality_gates",
        python_callable=run_stage_python,
        op_kwargs={
            "stage_name": "quality_gates",
            "command": ["tests/test_data_quality.py"],
        },
    )

    # Explicit chain (not >> sugar) so the stage contract is visible in one place.
    acquisition.set_downstream(raw_sync)
    raw_sync.set_downstream(conformed_marts)
    conformed_marts.set_downstream(quality_gates)

    bash_probe = BashOperator(
        task_id="warehouse_probe",
        bash_command=(
            "cd \"$AFRICA_PULSE_DIR\" && "
            "python scripts/test_connection.py"
        ),
        env={"AFRICA_PULSE_DIR": PROJECT_DIR},
    )
    quality_gates.set_downstream(bash_probe)
