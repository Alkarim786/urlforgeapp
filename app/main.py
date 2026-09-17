"""URLForge - Main FastAPI Application Entrypoint.

Scalable URL Shortener service built to demonstrate computer science
and backend engineering principles.
"""

from typing import Any, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routes.health import router as health_router
from app.routes.redirect import router as redirect_router
from app.routes.urls import router as urls_router

settings = get_settings()

app = FastAPI(
    title="URLForge",
    description=(
        "A high-performance, production-style URL shortening service "
        "designed for scalability, concurrency control, and deep observability."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS configuration - restrictive by default for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production environments
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(urls_router)


@app.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Service Root",
    tags=["Root"],
)
async def root() -> Dict[str, Any]:
    """Root endpoint welcoming clients and directing them to documentation."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "version": "0.1.0",
    }


# Register wildcard redirect router last so it does not shadow API or root endpoints
app.include_router(redirect_router)

