"""
Job model for tracking training pipeline executions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """
    Training Job execution record.

    A Job tracks the execution of a Pipeline, including progress and results.
    """

    __tablename__ = "jobs"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Foreign key to Pipeline
    pipeline_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False
    )

    # Execution status
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    current_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Validation metrics
    rmse: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mae: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mape: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    false_alerts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Preview data for frontend (ECharts format)
    preview_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Threshold results (1440 minutes = 24 hours)
    upper_bounds: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)
    lower_bounds: Mapped[Optional[list[float]]] = mapped_column(JSON, nullable=True)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retry management
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    parent_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship
    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="jobs")

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, pipeline_id={self.pipeline_id}, status={self.status})>"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = super().to_dict()
        result["duration_seconds"] = self.duration_seconds
        return result