from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


class PasswordResetRequest(BaseModel):
    email: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# ==========================
# ENDPOINT: /me (Get current user profile)
# ==========================

@router.get("/me")
def get_current_user_profile(user=Depends(get_current_user)):
    """
    Retorna o perfil do usuario logado.
    """
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "name": user.get("name") or user.get("full_name"),
        "role": user.get("role"),
        "school_id": user.get("school_id"),
    }


# ==========================
# ENDPOINT: /me/change-password
# ==========================

@router.put("/me/change-password")
def change_password(data: PasswordChangeRequest, user=Depends(get_current_user)):
    """
    Permite que o usuário logado altere sua senha.
    Requer a senha atual para validação.
    """
    
    if not data.current_password or not data.new_password:
        raise HTTPException(status_code=400, detail="Senha atual e nova senha são obrigatórias")
    
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Nova senha deve ter pelo menos 6 caracteres")
    
    try:
        # Tentar fazer login com a senha atual para validar
        # Isso é feito via Supabase REST API
        SUPABASE_URL = "https://lhydfllckxuzotondmla.supabase.co"
        SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoeWRmbGxja3h1em90b25kbWxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIzOTYxNTQsImV4cCI6MjA4Nzk3MjE1NH0.PvwKkuSX8tJXHmoztSodHqMoFCsbJyslhDHnxeAGHjs"
        
        import requests
        
        # Validar senha atual
        login_response = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            json={"email": user["email"], "password": data.current_password},
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_ANON_KEY,
            }
        )
        
        if not login_response.ok:
            raise HTTPException(status_code=401, detail="Senha atual incorreta")
        
        # Alterar senha usando o endpoint do Supabase
        # Nota: Isso requer que o usuário tenha um token válido
        # Vamos usar o método de update do Supabase
        update_response = requests.put(
            f"{SUPABASE_URL}/auth/v1/user",
            json={"password": data.new_password},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {login_response.json()['access_token']}",
                "apikey": SUPABASE_ANON_KEY,
            }
        )
        
        if not update_response.ok:
            raise HTTPException(status_code=500, detail="Erro ao alterar senha")
        
        return {"message": "Senha alterada com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao alterar senha: {str(e)}")


# ==========================
# ENDPOINT: /me/update
# ==========================

@router.put("/me/update")
def update_profile(data: dict, user=Depends(get_current_user)):
    """
    Permite que o usuário logado atualize seu perfil.
    """
    
    if not data:
        raise HTTPException(status_code=400, detail="Dados para atualizar são obrigatórios")
    
    try:
        # Atualizar apenas campos permitidos
        allowed_fields = ["full_name", "name", "avatar_url", "phone"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="Nenhum campo válido para atualizar")
        
        # Atualizar na tabela profiles
        result = supabase.table("profiles") \
            .update(update_data) \
            .eq("id", user["id"]) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Erro ao atualizar perfil")
        
        return {"message": "Perfil atualizado com sucesso", "data": result.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar perfil: {str(e)}")


# ==========================
# ENDPOINT: /reset-password (Super Admin)
# ==========================

@router.post("/reset-password")
def reset_user_password(data: PasswordResetRequest, user=Depends(get_current_user)):
    """
    Super Admin pode resetar a senha de qualquer usuário.
    Envia um email com link de reset.
    """
    
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Apenas super admin pode resetar senhas de outros usuários")
    
    if not data.email:
        raise HTTPException(status_code=400, detail="Email é obrigatório")
    
    try:
        # Usar o método de reset de senha do Supabase
        SUPABASE_URL = "https://lhydfllckxuzotondmla.supabase.co"
        SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxoeWRmbGxja3h1em90b25kbWxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIzOTYxNTQsImV4cCI6MjA4Nzk3MjE1NH0.PvwKkuSX8tJXHmoztSodHqMoFCsbJyslhDHnxeAGHjs"
        
        import requests
        
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            json={"email": data.email},
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_ANON_KEY,
            }
        )
        
        if not response.ok:
            raise HTTPException(status_code=400, detail="Email não encontrado ou erro ao enviar")
        
        return {"message": f"Email de reset enviado para {data.email}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao resetar senha: {str(e)}")


# ==========================
# ENDPOINT: /admin/unlock (Super Admin)
# ==========================

@router.post("/admin/unlock")
def unlock_user_account(email: str, user=Depends(get_current_user)):
    """
    Super Admin pode desbloquear uma conta de usuário.
    """
    
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Apenas super admin pode desbloquear contas")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email é obrigatório")
    
    try:
        # Buscar o usuário na tabela profiles
        profile = supabase.table("profiles") \
            .select("*") \
            .eq("email", email) \
            .execute()
        
        if not profile.data:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        user_profile = profile.data[0]
        
        # Ativar o usuário
        result = supabase.table("profiles") \
            .update({"is_active": True}) \
            .eq("id", user_profile["id"]) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Erro ao desbloquear conta")
        
        return {"message": f"Conta de {email} desbloqueada com sucesso"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao desbloquear conta: {str(e)}")
