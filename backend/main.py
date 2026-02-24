from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import employees, job_types, requests, requirements, schedules, nlp_modify, reports, export, holidays

app = FastAPI(title="Shift Scheduler API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
