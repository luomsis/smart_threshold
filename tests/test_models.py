"""
Tests for database models.
"""

import pytest
from datetime import datetime

from backend.models.pipeline import Pipeline
from backend.models.job import Job, JobStatus


class TestPipelineModel:
    """Test Pipeline model."""

    def test_create_pipeline(self):
        """Should create a Pipeline instance."""
        pipeline = Pipeline(
            id="test-pipeline-1",
            name="Test Pipeline",
            description="Test description",
            metric_id="cpu_usage",
            endpoint="/api/test",
            labels={"host": "localhost"},
            train_start=datetime(2024, 1, 1),
            train_end=datetime(2024, 1, 2),
            step="1m",
            algorithm="three_sigma",
            algorithm_params={"sigma_multiplier": 3.0},
            exclude_periods=[],
            enabled=True,
            schedule_type="manual",
        )

        assert pipeline.id == "test-pipeline-1"
        assert pipeline.name == "Test Pipeline"
        assert pipeline.algorithm == "three_sigma"
        assert pipeline.algorithm_params["sigma_multiplier"] == 3.0

    def test_pipeline_to_dict(self):
        """Should convert to dictionary."""
        pipeline = Pipeline(
            id="test-pipeline-1",
            name="Test Pipeline",
            description="Test",
            metric_id="cpu_usage",
            train_start=datetime(2024, 1, 1),
            train_end=datetime(2024, 1, 2),
            step="1m",
            algorithm="prophet",
            algorithm_params={},
            exclude_periods=[],
            labels={},
            enabled=True,
            schedule_type="manual",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        d = pipeline.to_dict()
        assert d["id"] == "test-pipeline-1"
        assert d["algorithm"] == "prophet"


class TestJobModel:
    """Test Job model."""

    def test_create_job(self):
        """Should create a Job instance."""
        job = Job(
            id="test-job-1",
            pipeline_id="pipeline-1",
            status=JobStatus.PENDING.value,
            progress=0,
        )

        assert job.id == "test-job-1"
        assert job.status == "pending"
        assert job.progress == 0

    def test_job_duration(self):
        """Should calculate job duration."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 5, 0)

        job = Job(
            id="test-job-1",
            pipeline_id="pipeline-1",
            status=JobStatus.SUCCESS.value,
            progress=100,
            started_at=start,
            finished_at=end,
            created_at=start,
        )

        assert job.duration_seconds == 300.0  # 5 minutes

    def test_job_duration_none_if_not_finished(self):
        """Duration should be None if not finished."""
        job = Job(
            id="test-job-1",
            pipeline_id="pipeline-1",
            status=JobStatus.RUNNING.value,
            progress=50,
            started_at=datetime.utcnow(),
        )

        assert job.duration_seconds is None

    def test_job_to_dict(self):
        """Should convert to dictionary."""
        job = Job(
            id="test-job-1",
            pipeline_id="pipeline-1",
            status=JobStatus.SUCCESS.value,
            progress=100,
            rmse=1.5,
            mae=1.2,
            coverage=0.95,
            false_alerts=10,
            upper_bounds=[100.0] * 1440,
            lower_bounds=[50.0] * 1440,
            created_at=datetime(2024, 1, 1),
        )

        d = job.to_dict()
        assert d["id"] == "test-job-1"
        assert d["rmse"] == 1.5
        assert d["coverage"] == 0.95
        assert len(d["upper_bounds"]) == 1440


class TestJobStatus:
    """Test JobStatus enum."""

    def test_status_values(self):
        """Should have expected status values."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"