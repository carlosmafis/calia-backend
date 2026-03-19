from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from typing import List
import secrets
import string
import pandas as pd

from core.auth import get_current_user
from core.config import supabase

router = APIRouter()


# ==========================
# MODELO
# ==========================

class TeacherCreate(BaseModel):
    full_name: str
    email: str
    subject_ids: List[str] = []
    class_ids: List[str] = []


def generate_temp_password(length: int = 12) -> str:
    """Gera uma senha temporária aleatória."""
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))


# ==========================
# LISTAR PROFESSORES
# ==========================

@router.get("/")
@router.get("")
def list_teachers(user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    data = supabase.table("profiles") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .eq("role", "professor") \
        .execute()

    return data.data


# ==========================
# DISCIPLINAS DO PROFESSOR LOGADO
# ==========================

@router.get("/my-subjects")
def my_subjects(user=Depends(get_current_user)):

    data = supabase.table("teacher_subjects") \
        .select("subjects(*)") \
        .eq("teacher_id", user["id"]) \
        .execute()

    if not data.data:
        return []

    return [x["subjects"] for x in data.data if x["subjects"]]


# ==========================
# TURMAS DO PROFESSOR LOGADO
# ==========================

@router.get("/my-classes")
def my_classes(user=Depends(get_current_user)):

    data = supabase.table("teacher_classes") \
        .select("classes(*)") \
        .eq("teacher_id", user["id"]) \
        .execute()

    if not data.data:
        return []

    return [x["classes"] for x in data.data if x["classes"]]


# ==========================
# CRIAR PROFESSOR
# ==========================

@router.post("/")
@router.post("")
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    temp_password = generate_temp_password()

    try:
        auth = supabase.auth.admin.create_user({
            "email": data.email,
            "password": temp_password,
            "email_confirm": True
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao criar usuário: {str(e)}")

    if not auth.user:
        raise HTTPException(status_code=400, detail="Erro ao criar usuário")

    teacher_id = auth.user.id

    supabase.table("profiles").insert({
        "id": teacher_id,
        "school_id": user["school_id"],
        "role": "professor",
        "full_name": data.full_name,
        "email": data.email
    }).execute()


    # ----------------------
    # VINCULAR DISCIPLINAS
    # ----------------------

    for subject in data.subject_ids:

        supabase.table("teacher_subjects").insert({
            "teacher_id": teacher_id,
            "subject_id": subject
        }).execute()


    # ----------------------
    # VINCULAR TURMAS
    # ----------------------

    for cls in data.class_ids:

        supabase.table("teacher_classes").insert({
            "teacher_id": teacher_id,
            "class_id": cls
        }).execute()


    return {
        "teacher": {
            "id": teacher_id,
            "full_name": data.full_name,
            "email": data.email
        },
        "credentials": {
            "email": data.email,
            "temp_password": temp_password,
            "message": "Credenciais temporarias. O professor deve trocar a senha no primeiro login."
        }
    }


# ==========================
# EDITAR PROFESSOR
# ==========================

@router.put("/{teacher_id}")
def update_teacher(
    teacher_id: str,
    data: TeacherCreate,
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    # Atualizar nome
    supabase.table("profiles") \
        .update({"full_name": data.full_name}) \
        .eq("id", teacher_id) \
        .execute()

    # Remover disciplinas antigas
    supabase.table("teacher_subjects") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    for subject in data.subject_ids:
        supabase.table("teacher_subjects").insert({
            "teacher_id": teacher_id,
            "subject_id": subject
        }).execute()

    # Remover turmas antigas
    supabase.table("teacher_classes") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    for cls in data.class_ids:
        supabase.table("teacher_classes").insert({
            "teacher_id": teacher_id,
            "class_id": cls
        }).execute()

    return {"message": "Professor atualizado"}


# ==========================
# DELETAR PROFESSOR
# ==========================

@router.delete("/{teacher_id}")
def delete_teacher(teacher_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    # Remover vínculos
    supabase.table("teacher_subjects") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    supabase.table("teacher_classes") \
        .delete() \
        .eq("teacher_id", teacher_id) \
        .execute()

    # Remover perfil
    supabase.table("profiles") \
        .delete() \
        .eq("id", teacher_id) \
        .execute()

    return {"message": "Professor removido"}


# ==========================
# IMPORTAR PROFESSORES VIA CSV
# ==========================

@router.post("/upload")
async def upload_teachers(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    try:
        df = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao ler CSV: {str(e)}")

    count = 0
    errors = []
    credentials_list = []

    for idx, row in df.iterrows():
        try:
            full_name = row.get("Nome Completo") or row.get("name")
            email = row.get("Email") or row.get("email")
            
            if not full_name or not email:
                errors.append(f"Erro na linha {idx + 2}: Nome Completo e Email são obrigatórios")
                continue
            
            temp_password = generate_temp_password()
            
            # Criar usuário no Supabase Auth
            auth = supabase.auth.admin.create_user({
                "email": email,
                "password": temp_password,
                "email_confirm": True
            })
            
            if not auth.user:
                errors.append(f"Erro na linha {idx + 2}: Falha ao criar usuário no Supabase")
                continue
            
            # Criar profile
            supabase.table("profiles").insert({
                "id": auth.user.id,
                "school_id": user["school_id"],
                "role": "professor",
                "full_name": full_name,
                "email": email
            }).execute()
            
            credentials_list.append({
                "full_name": full_name,
                "email": email,
                "temp_password": temp_password
            })
            
            count += 1
        except Exception as e:
            errors.append(f"Erro na linha {idx + 2}: {str(e)}")

    return {
        "message": f"{count} professores importados",
        "errors": errors,
        "credentials": credentials_list
    }
