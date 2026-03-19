from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import schools
from routers import classes
from routers import students
from routers import assessments
from routers import ocr
from routers import manual
from routers import teachers
from routers import dashboard
from routers import users
from routers.subjects import router as subjects_router
from core.auth import get_current_user
from fastapi import Depends

app = FastAPI(title="Calia Digital API", version="2.0.0")

# ==========================
# CORS — permitir frontend antigo, novo e localhost
# ==========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://calia-frontend.vercel.app",
        "https://calia-frontend-v2.vercel.app",
        "https://caliadigital.com.br",
        "https://www.caliadigital.com.br",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# ROUTERS
# ==========================

app.include_router(schools.router)  # já tem prefix="/schools" no router
app.include_router(classes.router, prefix="/classes")
app.include_router(students.router, prefix="/students")
app.include_router(assessments.router, prefix="/assessments")
app.include_router(ocr.router, prefix="/ocr")
app.include_router(manual.router)
app.include_router(teachers.router, prefix="/teachers")
app.include_router(users.router, prefix="/users")
app.include_router(subjects_router, prefix="/subjects")
app.include_router(dashboard.router)


# ==========================
# ENDPOINT /me — Retorna perfil completo do usuário logado
# ==========================

@app.get("/me")
def get_me(user=Depends(get_current_user)):
    """
    Retorna o perfil do usuário logado.
    O frontend usa isso para determinar o role e renderizar o dashboard correto.
    """
    return {
        "id": user.get("id"),
        "email": user.get("email", ""),
        "role": user.get("role", ""),
        "school_id": user.get("school_id"),
        "name": user.get("full_name") or user.get("name") or user.get("email", ""),
        "full_name": user.get("full_name", ""),
    }


# ==========================
# HEALTH CHECK
# ==========================

@app.get("/")
def root():
    return {"status": "CALIA backend online", "version": "2.0.0"}
