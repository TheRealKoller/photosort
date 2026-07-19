from fastapi import FastAPI

from photosort.api import opencloud, projects


def create_app() -> FastAPI:
    app = FastAPI(title="PhotoSort API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(opencloud.router)
    app.include_router(projects.router)

    return app


app = create_app()
