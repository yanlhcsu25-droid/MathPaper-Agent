from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from calculus_agent.api import router
from calculus_agent.config import get_settings


app = FastAPI(title=get_settings().app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
