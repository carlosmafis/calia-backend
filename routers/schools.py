from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import secrets
import string

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


def generate_temp_password(length: int = 12) -> str:
    """Gera uma senha temporária aleatória."""
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))


# ==========================
# LISTAR ESCOLAS
# ==========================

@router.get("/")
@router.get("")
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
@router.post("")
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
        temp_password = generate_temp_password()

        try:
            # Criar usuario no Supabase Auth
            auth = supabase.auth.admin.create_user({
                "email": data.admin_email,
                "password": temp_password,
                "email_confirm": True
            })

            if auth.user:
                # Criar profile na tabela profiles
                profile_data = {
                    "id": auth.user.id,
                    "school_id": school["id"],
                    "role": "admin",
                    "full_name": data.admin_name or "Administrador",
                    "email": data.admin_email
                }
                
                profile_result = supabase.table("profiles").insert(profile_data).execute()
                
                if not profile_result.data:
                    raise Exception(f"Falha ao criar profile: {profile_result}")

                return {
                    "school": school,
                    "admin": {
                        "id": auth.user.id,
                        "full_name": data.admin_name or "Administrador",
                        "email": data.admin_email
                    },
                    "credentials": {
                        "email": data.admin_email,
                        "temp_password": temp_password,
                        "message": "Credenciais temporarias. O admin deve trocar a senha no primeiro login."
                    }
                }
            else:
                raise Exception("Falha ao criar usuario no Supabase Auth")
        except Exception as e:
            # Escola foi criada mas admin falhou
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            return {
                "school": school,
                "admin_error": error_msg
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
