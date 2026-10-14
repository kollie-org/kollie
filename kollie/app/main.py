import pathlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from kollie.cluster.authentication import connect_to_cluster
from kollie.logging_config import configure_logger

from .api import endpoints
from .ui import views


def create_app():
    """Factory function to create the FastAPI app."""
    app = FastAPI()

    app.mount(
        "/static",
        StaticFiles(directory=f"{pathlib.Path(__file__).parent.resolve()}/static"),
        name="static",
    )

    app.include_router(endpoints.router)
    app.include_router(views.router)

    @app.get("/ping")
    async def ping():
        return {"message": "Pong..."}

    configure_logger()
    connect_to_cluster()

    return app
