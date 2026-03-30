"""
Data fetching step.

Fetches time series data from TSDB (Prometheus/TimescaleDB).
"""

import time
from datetime import datetime
from typing import Any

import pandas as pd

from smart_threshold.datasource.prometheus_client import create_datasource
from smart_threshold.datasource.models import TimeRange, DataSourceType


def fetch_data(
    datasource_config: dict[str, Any],
    metric_id: str,
    train_start: datetime,
    train_end: datetime,
    step: str = "1m",
    endpoint: str | None = None,
    labels: dict[str, str] | None = None,
) -> tuple[pd.Series | None, str | None]:
    """
    Fetch time series data from TSDB.

    Args:
        datasource_config: Data source configuration dict
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
        # Create data source client
        source_type = datasource_config.get("source_type", "mock")

        # Build config
        from smart_threshold.datasource.models import DataSourceConfig
        config = DataSourceConfig(
            name=datasource_config.get("name", "default"),
            source_type=DataSourceType(source_type),
            url=datasource_config.get("url", ""),
            enabled=True,
            db_host=datasource_config.get("db_host", "localhost"),
            db_port=datasource_config.get("db_port", 5432),
            db_name=datasource_config.get("db_name", "postgres"),
            db_user=datasource_config.get("db_user", "postgres"),
            db_password=datasource_config.get("db_password", ""),
        )

        client = create_datasource(config)

        # Build query
        query = metric_id

        # Create time range
        time_range = TimeRange(
            start=train_start,
            end=train_end,
            step=step
        )

        # Query data
        start_time = time.time()

        if source_type == "timescaledb":
            result = client.query_range(query, time_range, labels=labels, endpoint=endpoint)
        else:
            result = client.query_range(query, time_range)

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