"""
Data fetching step.

Fetches time series data from TimescaleDB.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from smart_threshold.datasource.timescaledb_client import TimescaleDBDataSource
from smart_threshold.datasource.models import TimeRange, DataSourceConfig, DataSourceType


# Global TimescaleDB config path
CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
TIMESCALEDB_CONFIG_FILE = CONFIG_DIR / "timescaledb.json"


def get_global_timescaledb_config() -> dict[str, Any]:
    """
    Load global TimescaleDB configuration from config/timescaledb.json.

    Returns:
        Dictionary with TimescaleDB connection parameters.
    """
    if not TIMESCALEDB_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"TimescaleDB config file not found: {TIMESCALEDB_CONFIG_FILE}"
        )

    with open(TIMESCALEDB_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_timescaledb_client() -> TimescaleDBDataSource:
    """
    Create a TimescaleDB client using global configuration.

    Returns:
        TimescaleDBDataSource instance.
    """
    config = get_global_timescaledb_config()

    ds_config = DataSourceConfig(
        name="global_timescaledb",
        source_type=DataSourceType.TIMESCALEDB,
        url=f"postgresql://{config['host']}:{config['port']}/{config['database']}",
        enabled=True,
        db_host=config["host"],
        db_port=config["port"],
        db_name=config["database"],
        db_user=config["user"],
        db_password=config["password"],
    )

    return TimescaleDBDataSource(ds_config)


def fetch_data(
    metric_id: str,
    train_start: datetime,
    train_end: datetime,
    step: str = "1m",
    endpoint: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[pd.Series | None, str | None]:
    """
    Fetch time series data from TimescaleDB.

    Args:
        metric_id: Metric name/query
        train_start: Training data start time
        train_end: Training data end time
        step: Query step (e.g., "1m", "5m")
        endpoint: Optional endpoint filter
        labels: Optional label filters

    Returns:
        Tuple of (data_series, error_message)
    """
    try:
        # Create TimescaleDB client using global config
        client = get_timescaledb_client()

        # Create time range
        time_range = TimeRange(
            start=train_start,
            end=train_end,
            step=step
        )

        # Query data
        start_time = time.time()
        result = client.query_range(metric_id, time_range, labels=labels, endpoint=endpoint)
        execution_time = time.time() - start_time

        if not result.success:
            return None, f"Query failed: {result.error}"

        if not result.data:
            return None, "No data returned from query"

        # Convert to pandas Series
        metric_data = result.data[0]
        if not metric_data.values:
            return None, "Empty data series"

        series = pd.Series(
            metric_data.values,
            index=pd.DatetimeIndex(metric_data.timestamps),
            name=metric_id
        )

        return series, None

    except Exception as e:
        return None, f"Data fetch error: {str(e)}"