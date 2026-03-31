"""
Pipeline execution module.
"""

# Lazy import to avoid circular import issues
# Import PipelineExecutor only when needed
def __getattr__(name: str):
    if name == "PipelineExecutor":
        from backend.pipeline.executor import PipelineExecutor
        return PipelineExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["PipelineExecutor"]