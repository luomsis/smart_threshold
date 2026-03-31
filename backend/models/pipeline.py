"""
Pipeline model for storing training pipeline configurations.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Pipeline(Base):
    """
    Training Pipeline configuration.

    A Pipeline defines how to train a threshold model for a specific metric.
    """

    __tablename__ = "pipelines"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # Data source configuration
    metric_id: Mapped[str] = mapped_column(String(255), nullable=False)
    datasource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)

    # Time configuration
    train_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    step: Mapped[str] = mapped_column(String(10), default="1m")

    # Algorithm configuration (old fields - deprecated but kept for backward compatibility)
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    algorithm_params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Model reference (new fields - preferred way to configure algorithm)
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    override_params: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Exclude periods (list of {start, end} dicts)
    exclude_periods: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)

    # Data cleaning configuration
    outlier_detection: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    smoothing: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Scheduling
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual, scheduled
    cron_expr: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="Job.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Pipeline(id={self.id}, name={self.name}, algorithm={self.algorithm})>"