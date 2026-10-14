from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api import auth, me, solves, stats
from app.config import get_settings
from app.ratelimit import limiter, rate_limit_handler


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="algo-tracker",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    api.include_router(auth.router)
    api.include_router(me.router)
    api.include_router(solves.router)
    api.include_router(solves.tags_router)
    api.include_router(stats.router)
    app.include_router(api)
    return app


app = create_app()
