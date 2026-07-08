from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router
from db.models import create_tables
import os

load_dotenv()

app = FastAPI(
    title       = "CP Coach API",
    description = "AI-powered Codeforces coaching system",
    version     = "1.0.0"
)

# Allow Streamlit frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"]
)

# Include all routes
app.include_router(router, prefix="/api")

# Create DB tables on startup
@app.on_event("startup")
def startup():
    create_tables()
    print("CP Coach API started successfully")


@app.get("/")
def root():
    return {
        "message": "CP Coach API is running",
        "docs":    "/docs",
        "status":  "healthy"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}