"""Kenjutsu FastAPI application entry point."""

from fastapi import FastAPI

from kenjutsu.server.webhook import router as webhook_router

app = FastAPI(
    title="Kenjutsu",
    description="AI-powered PR review",
    version="0.1.0",
)

app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint for container orchestration."""
    return {"status": "ok"}
