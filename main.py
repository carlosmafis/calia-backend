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

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token ausente")

    token = authorization.split(" ")[1]

    user_response = supabase.auth.get_user(token)

    if not user_response.user:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_id = user_response.user.id

    user_profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_id) \
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

    school = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute()

    log_activity(user, "create", "school")

    return school.data


@app.get("/schools")
def get_schools(user=Depends(get_current_user)):
    if user["role"] == "super_admin":
        schools = supabase.table("schools").select("*").execute()
        return schools.data

    school = supabase.table("schools") \
        .select("*") \
        .eq("id", user["school_id"]) \
        .execute()

    return school.data


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
