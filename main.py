import os
from fastapi import FastAPI, Depends, HTTPException, Header
from jose import jwt
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

load_dotenv()

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://calia-frontend.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------------
# MODELOS
# ----------------------------------------------------

class SchoolCreate(BaseModel):
    name: str
    slug: str
    plan: Optional[str] = "free"


class StudentCreate(BaseModel):
    name: str
    class_id: Optional[str] = None
    birth_date: Optional[str] = None


# ----------------------------------------------------
# AUTENTICAÇÃO
# ----------------------------------------------------

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erro ao validar token: {str(e)}")

    if not user_data:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_data.id) \
        .execute()

    if not user_profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    return user_profile.data[0]


# ----------------------------------------------------
# LOG AUTOMÁTICO
# ----------------------------------------------------

def log_activity(user, action, entity):
    supabase.table("activity_logs").insert({
        "school_id": user.get("school_id"),
        "user_id": user.get("id"),
        "action": action,
        "entity": entity,
        "created_at": datetime.utcnow().isoformat()
    }).execute()


# ----------------------------------------------------
# ROTAS BÁSICAS
# ----------------------------------------------------

@app.get("/")
def root():
    return {"status": "CALIA 2.0 Backend Online 🚀"}


@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user


# ----------------------------------------------------
# ESCOLAS
# ----------------------------------------------------

@app.post("/schools")
def create_school(data: SchoolCreate, user=Depends(get_current_user)):
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Acesso negado")

    # 1️⃣ Criar escola
    school_response = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute()

    if not school_response.data:
        raise HTTPException(status_code=400, detail="Erro ao criar escola")

    school = school_response.data[0]

    # 2️⃣ Criar usuário admin automaticamente
    admin_email = f"admin@{data.slug}.com"
    admin_password = "12345678"

    auth_response = supabase.auth.admin.create_user({
        "email": admin_email,
        "password": admin_password,
        "email_confirm": True
    })

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário admin")

    # 3️⃣ Criar profile do admin
    supabase.table("profiles").insert({
        "id": auth_response.user.id,
        "school_id": school["id"],
        "role": "admin",
        "full_name": "Administrador"
    }).execute()

    log_activity(user, "create", "school_with_admin")

    return {
        "school": school,
        "admin_email": admin_email,
        "admin_password": admin_password
    }


# ----------------------------------------------------
# ALUNOS
# ----------------------------------------------------

@app.post("/students")
def create_student(data: StudentCreate, user=Depends(get_current_user)):
    if user["role"] not in ["admin", "professor"]:
        raise HTTPException(status_code=403, detail="Acesso negado")

    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "name": data.name,
        "birth_date": data.birth_date
    }).execute()

    log_activity(user, "create", "student")

    return student.data


@app.get("/students")
def list_students(user=Depends(get_current_user)):
    students = supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return students.data

@app.post("/debug-login")
def debug_login(email: str, password: str):
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    return response

@app.get("/debug-token")
def debug_token(authorization: str = Header(None)):
    return {"header_recebido": authorization}
