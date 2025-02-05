from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json

from api.database import SessionLocal, engine  # Update this import
from api import models, schemas  # Update this import

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/ping")
def ping():
    return {"status": "ok"}