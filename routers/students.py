from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from pydantic import BaseModel
from typing import Optional
import secrets
import string

from core.config import supabase
from core.auth import get_current_user

import pandas as pd

router = APIRouter(tags=["Students"])


class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"
    registration_number: Optional[str] = None


def generate_temp_password(length: int = 12) -> str:
    """Gera uma senha temporária aleatória."""
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))


def create_supabase_user(email: str, password: str) -> dict:
    """Cria um usuário no Supabase Auth."""
    try:
        user = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })
        return {"success": True, "user_id": user.user.id, "email": email, "temp_password": password}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_school_domain(school_id: str) -> str:
    """Obtém o slug da escola para gerar o email do aluno."""
    try:
        school = supabase.table("schools").select("slug").eq("id", school_id).execute()
        if school.data:
            return school.data[0].get("slug", "escola")
    except:
        pass
    return "escola"

# ==========================
# LISTAR ALUNOS
# ==========================

@router.get("/")
def list_students(
    class_id: Optional[str] = Query(None),
    user=Depends(get_current_user)
):

    query = supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"])

    if class_id:
        query = query.eq("class_id", class_id)

    students = query.execute()

    return students.data


# ==========================
# CRIAR ALUNO
# ==========================

@router.post("/")
def create_student(data: StudentCreate, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    school_domain = get_school_domain(user["school_id"])

    # 🔥 NOVA REGRA: matrícula obrigatória
    if not data.registration_number:
        raise HTTPException(status_code=400, detail="Matrícula é obrigatória")

    registration = data.registration_number.strip()

    # 🔥 Verificar duplicidade de matrícula
    existing = supabase.table("students") \
        .select("id") \
        .eq("registration_number", registration) \
        .execute()

    if existing.data:
        raise HTTPException(status_code=400, detail="Matrícula já cadastrada")

    email = f"{registration}@{school_domain}.com"

    # 🔥 Verificar duplicidade de email
    existing_email = supabase.table("students") \
        .select("id") \
        .eq("email", email) \
        .execute()

    if existing_email.data:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # 🔥 senha = matrícula
    temp_password = registration

    auth_result = create_supabase_user(email, temp_password)
    
    # ✅ PRIMEIRO valida
    if not auth_result["success"]:
        raise HTTPException(status_code=400, detail=f"Erro ao criar usuario: {auth_result['error']}")
    
    # ✅ AGORA usa com segurança
    supabase.table("profiles").insert({
        "id": auth_result["user_id"],
        "school_id": user["school_id"],
        "role": "student",
        "full_name": data.name,
        "email": email
    }).execute()
    
    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "user_id": auth_result["user_id"],
        "name": data.name,
        "status": data.status,
        "email": email,
        "registration_number": registration
    }).execute()

    if not student.data:
        raise HTTPException(status_code=400, detail="Erro ao criar aluno")

    return {
        "student": student.data[0],
        "credentials": {
            "email": email,
            "temp_password": temp_password,
            "message": "Senha padrão: matrícula. O aluno deve trocar no primeiro acesso."
        }
    }


# ==========================
# IMPORTAR ALUNOS VIA CSV
# ==========================

@router.post("/upload")
async def upload_students(
    file: UploadFile = File(...),
    class_id: str = Form(...),
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
    school_domain = get_school_domain(user["school_id"])

    for idx, row in df.iterrows():
        try:
            name = row.get("Nome") or row.get("name")
            registration = row.get("Matricula") or row.get("registration_number")
            
            if not name:
                errors.append(f"Erro na linha {idx + 2}: Nome eh obrigatorio")
                continue

            if not registration:
                errors.append(f"Erro na linha {idx + 2}: Matricula eh obrigatoria")
                continue

            registration = str(registration).strip()
            email = f"{registration}@{school_domain}.com"
            temp_password = registration  # Senha é a matrícula do aluno
            
            # Criar usuario no Supabase Auth
            auth = supabase.auth.admin.create_user({
                "email": email,
                "password": temp_password,
                "email_confirm": True
            })

            if not auth.user:
                errors.append(f"Erro na linha {idx + 2}: Falha ao criar usuario no Supabase")
                continue

            supabase.table("students").insert({
                "school_id": user["school_id"],
                "class_id": class_id,
                "user_id": auth.user.id,
                "name": name,
                "status": row.get("Turma") or row.get("status") or "CURSANDO",
                "email": email,
                "registration_number": registration
            }).execute()

            credentials_list.append({
                "name": name,
                "email": email,
                "temp_password": temp_password
            })

            count += 1
        except Exception as e:
            errors.append(f"Erro na linha {idx + 2}: {str(e)}")

    return {
        "message": f"{count} alunos importados",
        "errors": errors,
        "credentials": credentials_list
    }


# ==========================
# ATUALIZAR ALUNO
# ==========================

@router.put("/{student_id}")
def update_student(
    student_id: str,
    data: StudentCreate,
    user=Depends(get_current_user)
):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students") \
        .update({
            "name": data.name,
            "status": data.status,
            "class_id": data.class_id
        }) \
        .eq("id", student_id) \
        .execute()

    return {"message": "Aluno atualizado"}


# ==========================
# MOVER ALUNO DE TURMA
# ==========================

@router.put("/move/{student_id}")
def move_student(student_id: str, class_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students").update({
        "class_id": class_id
    }).eq("id", student_id).execute()

    return {"message": "Aluno movido de turma"}


# ==========================
# DELETAR ALUNO
# ==========================

@router.delete("/{student_id}")
def delete_student(student_id: str, user=Depends(get_current_user)):

    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403)

    supabase.table("students") \
        .delete() \
        .eq("id", student_id) \
        .execute()

    return {"message": "Aluno removido"}