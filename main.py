from fastapi import UploadFile, File
import shutil
import uuid
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

load_dotenv()

app = FastAPI()

# ----------------------------------------------------
# CORS
# ----------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://calia-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# SUPABASE
# ----------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
security = HTTPBearer()

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

class TeacherCreate(BaseModel):
    email: str
    full_name: str

# ----------------------------------------------------
# AUTENTICAÇÃO
# ----------------------------------------------------

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user
    except:
        raise HTTPException(status_code=401, detail="Token inválido")

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
# LOG
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

    school_response = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute()

    school = school_response.data[0]

    admin_email = f"admin@{data.slug}.com"
    admin_password = "12345678"

    auth_response = supabase.auth.admin.create_user({
        "email": admin_email,
        "password": admin_password,
        "email_confirm": True
    })

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

@app.get("/schools")
def get_schools(user=Depends(get_current_user)):
    if user["role"] == "super_admin":
        return supabase.table("schools").select("*").execute().data

    return supabase.table("schools") \
        .select("*") \
        .eq("id", user["school_id"]) \
        .execute().data

# ----------------------------------------------------
# PROFESSORES (ADMIN)
# ----------------------------------------------------

@app.post("/teachers")
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode criar professor")

    temp_password = "12345678"

    auth_response = supabase.auth.admin.create_user({
        "email": data.email,
        "password": temp_password,
        "email_confirm": True
    })

    if not auth_response.user:
        raise HTTPException(status_code=400, detail="Erro ao criar professor")

    supabase.table("profiles").insert({
        "id": auth_response.user.id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name
    }).execute()

    log_activity(user, "create", "teacher")

    return {
        "email": data.email,
        "temporary_password": temp_password
    }

@app.get("/teachers")
def list_teachers(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode listar professores")

    return supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute().data
@app.post("/ocr-upload")
async def ocr_upload(file: UploadFile = File(...), user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403, detail="Apenas professor pode usar OCR")

    # 1️⃣ Salvar arquivo temporariamente
    file_id = str(uuid.uuid4())
    file_path = f"/tmp/{file_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2️⃣ Aqui você coloca seu módulo OCR antigo
    # Por enquanto vamos simular OCR
    extracted_text = f"Texto extraído simulado do arquivo {file.filename}"

    # 3️⃣ Salvar no banco
    supabase.table("ocr_uploads").insert({
        "school_id": user["school_id"],
        "uploaded_by": user["id"],
        "file_url": file.filename,
        "extracted_text": extracted_text,
        "status": "completed"
    }).execute()

    log_activity(user, "create", "ocr_upload")

    return {
        "message": "OCR processado com sucesso",
        "extracted_text": extracted_text
    }

@app.get("/ocr-history")
def ocr_history(user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403, detail="Apenas professor pode acessar histórico")

    history = supabase.table("ocr_uploads") \
        .select("*") \
        .eq("uploaded_by", user["id"]) \
        .order("created_at", desc=True) \
        .execute()

    return history.data
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
    return supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute().data
