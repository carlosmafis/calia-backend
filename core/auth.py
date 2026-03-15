from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import supabase

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):

    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    if not user_data:
        raise HTTPException(status_code=401, detail="Token inválido")

    # Buscar perfil na tabela profiles
    profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_data.id) \
        .execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    user_profile = profile.data[0]

    # Garantir que o email está presente no perfil
    if not user_profile.get("email"):
        user_profile["email"] = user_data.email

    return user_profile
