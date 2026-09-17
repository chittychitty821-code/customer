"""
Main entry point for OmniDesk AI Backend.
Supports Railway, Render, Docker, and direct Uvicorn deployments.
"""
import os
import uvicorn
from server import app

# Export app instance for ASGI servers (uvicorn main:app)
__all__ = ["app"]

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port)
