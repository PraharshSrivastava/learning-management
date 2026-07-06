import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pipelines.routes import router
from pipelines.employee_routes import router as employee_router

app = FastAPI(title="LMS Document Management System Backend")

_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
_cors_origins = ["*"] if _cors_origins_env == "*" else [o.strip() for o in _cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=(_cors_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.include_router(router)
app.include_router(employee_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
