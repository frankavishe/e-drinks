import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import admin, public
from app.services.booking_flow import StageRefused

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="e-drinks API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(admin.router)


@app.exception_handler(StageRefused)
async def stage_refused(_: Request, exc: StageRefused) -> JSONResponse:
    """A business rule said no: the code is what the UI translates and shows."""
    return JSONResponse(status_code=409, content={"detail": {"code": exc.code}})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
