import os
from fastapi import FastAPI, Depends, HTTPException, Header
from jose import jwt
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ----------------------------------------------------
# VALIDAR TOKEN DO SUPABASE
# ----------------------------------------------------

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token ausente")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

    user_id = payload.get("sub")

    user_profile = supabase.table("profiles") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    if not user_profile.data:
        raise HTTPException(status_code=403, detail="Perfil não encontrado")

    return user_profile.data[0]


# ----------------------------------------------------
# ROTAS
# ----------------------------------------------------

@app.get("/")
def root():
    return {"status": "CALIA 2.0 Backend Online 🚀"}


@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user


@app.get("/schools")
def get_schools(user=Depends(get_current_user)):
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="Acesso negado")

    schools = supabase.table("schools").select("*").execute()
    return schools.data
