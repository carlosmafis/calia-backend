from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

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


# ==========================
# LISTAR PROFESSORES
# ==========================

@router.get("/")
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
def create_teacher(data: TeacherCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    password = "12345678"

    try:
        auth = supabase.auth.admin.create_user({
            "email": data.email,
            "password": password,
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
        "full_name": data.full_name
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
        "email": data.email,
        "password": password
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
