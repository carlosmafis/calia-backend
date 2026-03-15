from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(tags=["Students"])

class StudentCreate(BaseModel):
    name: str
    class_id: str
    status: str = "CURSANDO"

@router.post("/")
def create_student(data: StudentCreate, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    student = supabase.table("students").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "name": data.name,
        "status": data.status
    }).execute()

    return student.data
    
import pandas as pd
from fastapi import UploadFile, File, Depends

@router.post("/upload")
async def upload_students(
    class_id:str,
    file:UploadFile = File(...),
    user=Depends(get_current_user)
):

    df = pd.read_csv(file.file)

    for _,row in df.iterrows():

        supabase.table("students").insert({

            "school_id":user["school_id"],
            "class_id":class_id,
            "name":row["name"],
            "status":row.get("status","CURSANDO")

        }).execute()

    return {"message":"Alunos importados"}

@router.get("/")
def list_students(user=Depends(get_current_user)):

    students = supabase.table("students") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return students.data

@router.put("/move/{student_id}")
def move_student(student_id: str, class_id: str, user=Depends(get_current_user)):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students").update({
        "class_id": class_id
    }).eq("id", student_id).execute()

    return {"message": "Aluno movido de turma"}
    
@router.put("/{student_id}")
def update_student(
    student_id:str,
    name:str,
    status:str,
    class_id:str,
    user=Depends(get_current_user)
):

    if user["role"] != "admin":
        raise HTTPException(status_code=403)

    supabase.table("students") \
        .update({
            "name":name,
            "status":status,
            "class_id":class_id
        }) \
        .eq("id",student_id) \
        .execute()

    return {"message":"Aluno atualizado"}
