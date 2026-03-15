from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/schools", tags=["Schools"])


class SchoolCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"


class SchoolAdminCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None


# ==========================
# LISTAR ESCOLAS
# ==========================

@router.get("/")
def list_schools(user=Depends(get_current_user)):

    if user["role"] == "super_admin":
        return supabase.table("schools").select("*").execute().data

    return supabase.table("schools") \
        .select("*") \
        .eq("id", user["school_id"]) \
        .execute().data


# ==========================
# DETALHES DE UMA ESCOLA
# ==========================

@router.get("/{school_id}")
def get_school(school_id: str, user=Depends(get_current_user)):

    if user["role"] != "super_admin" and user.get("school_id") != school_id:
        raise HTTPException(status_code=403)

    school = supabase.table("schools") \
        .select("*") \
        .eq("id", school_id) \
        .single() \
        .execute()

    if not school.data:
        raise HTTPException(status_code=404, detail="Escola não encontrada")

    return school.data


# ==========================
# CRIAR ESCOLA
# ==========================

@router.post("/")
def create_school(data: SchoolCreate, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    school = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute().data[0]

    return school


# ==========================
# CRIAR ESCOLA + ADMIN
# ==========================

@router.post("/with-admin")
def create_school_with_admin(data: SchoolAdminCreate, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    # 1. Criar escola
    school = supabase.table("schools").insert({
        "name": data.name,
        "slug": data.slug,
        "plan": data.plan
    }).execute().data[0]

    # 2. Criar admin da escola (se email fornecido)
    if data.admin_email:
        password = "12345678"

        try:
            auth = supabase.auth.admin.create_user({
                "email": data.admin_email,
                "password": password,
                "email_confirm": True
            })

            if auth.user:
                supabase.table("profiles").insert({
                    "id": auth.user.id,
                    "school_id": school["id"],
                    "role": "admin",
                    "full_name": data.admin_name or "Administrador"
                }).execute()

                return {
                    "school": school,
                    "admin_email": data.admin_email,
                    "admin_password": password
                }
        except Exception as e:
            # Escola foi criada mas admin falhou
            return {
                "school": school,
                "admin_error": str(e)
            }

    return {"school": school}


# ==========================
# ATUALIZAR ESCOLA
# ==========================

@router.put("/{school_id}")
def update_school(school_id: str, data: SchoolCreate, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    supabase.table("schools") \
        .update({
            "name": data.name,
            "slug": data.slug,
            "plan": data.plan
        }) \
        .eq("id", school_id) \
        .execute()

    return {"message": "Escola atualizada"}


# ==========================
# DELETAR ESCOLA
# ==========================

@router.delete("/{school_id}")
def delete_school(school_id: str, user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        raise HTTPException(status_code=403)

    supabase.table("schools") \
        .delete() \
        .eq("id", school_id) \
        .execute()

    return {"message": "Escola removida"}
