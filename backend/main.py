import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, cleanup_old_schedules
from routers import employees, job_types, requests, requirements, schedules, nlp_modify, reports, export, holidays

app = FastAPI(title="Shift Scheduler API", version="1.0.0")

# CORS: allow frontend origins (local + Vercel + FRONTEND_URL)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3003",
]
if os.getenv("FRONTEND_URL"):
    furl = os.getenv("FRONTEND_URL", "").rstrip("/")
    allowed_origins.append(furl)
    # Allow both http and https for the same domain
    if furl.startswith("https://"):
        allowed_origins.append(furl.replace("https://", "http://"))
    elif furl.startswith("http://"):
        allowed_origins.append(furl.replace("http://", "https://"))

# Regex for Vercel deployments (*.vercel.app)
allow_origin_regex = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees.router)
app.include_router(job_types.router)
app.include_router(requests.router)
app.include_router(requirements.router)
app.include_router(schedules.router)
app.include_router(nlp_modify.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(holidays.router)


@app.on_event("startup")
def on_startup():
    init_db()
    cleanup_old_schedules()


@app.get("/api/health")
def health():
    return {"status": "ok"}
