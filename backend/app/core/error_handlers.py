import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import KhwarizmError


logger = logging.getLogger("khwarizm.api")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(KhwarizmError)
    async def handle_khwarizm_error(_: Request, exc: KhwarizmError):
        error_id = str(uuid4())
        logger.warning("Handled Khwarizm error", extra={"error_id": error_id}, exc_info=exc)
        return JSONResponse(
            status_code=400,
            content={
                "detail": str(exc),
                "error_id": error_id,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        error_id = str(uuid4())
        logger.exception("Unhandled application error", extra={"error_id": error_id})
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected server error occurred.",
                "error_id": error_id,
            },
        )
