from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import supabase

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):

    token = credentials.credentials

    try:
        user_response = supabase.auth.get_user(token)
        user_data = user_response.user
    except:
        raise HTTPException(status_code=401, detail="Token inválido")

    if not user_data:
        raise HTTPException(status_code=401, detail="Token inválido")

    profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_data.id) \
        .execute()

    if not profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    return profile.data[0]