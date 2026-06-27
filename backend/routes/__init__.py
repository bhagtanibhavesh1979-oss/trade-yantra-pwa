from .alerts import router as alerts_router
from .astro import router as astro_router
from .auth import router as auth_router
from .chart import router as chart_router
from .indices import router as indices_router
from .live import router as live_router
from .paper import router as paper_router
from .stream import router as stream_router
from .watchlist import router as watchlist_router
from .telegram_signals import router as telegram_signals_router

__all__ = [
    "alerts_router",
    "astro_router",
    "auth_router",
    "chart_router",
    "indices_router",
    "live_router",
    "paper_router",
    "stream_router",
    "watchlist_router",
    "telegram_signals_router",
]

