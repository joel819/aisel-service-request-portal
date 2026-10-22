import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import assistant, auth, requests

logger = logging.getLogger("app")


def configure_logging() -> None:
    """uvicorn only configures its own loggers; without this the app's INFO logs are dropped."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Service Request & Project Intake Portal")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(requests.router)
    app.include_router(assistant.router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            {"detail": "Internal server error"}, status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return app


app = create_app()
