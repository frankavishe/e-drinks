import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import public

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


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
