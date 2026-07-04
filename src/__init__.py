from fastapi import FastAPI
from src.router.User import user_router
from src.database import engine
import src.database as database
import src.models

version = "v1"


app = FastAPI(
  title="Edupath",
  description="A REST API for RAG",
  version= version
)
database.Base.metadata.create_all(bind=engine)

app.include_router(user_router, prefix=f"/api/{version}/users", tags=["users"])