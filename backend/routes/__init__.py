# Routes package
# Import and include the chart router
from .chart import router as chart_router

# Make the chart router available for export
__all__ = ["chart_router"]