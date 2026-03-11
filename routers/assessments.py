from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/assessments", tags=["Assessments"])

class AssessmentCreate(BaseModel):
    class_id: str
    title: str
    total_questions: int

@router.post("/")
def create_assessment(data: AssessmentCreate, user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    new_assessment = supabase.table("assessments").insert({
        "school_id": user["school_id"],
        "class_id": data.class_id,
        "created_by": user["id"],
        "title": data.title,
        "total_questions": data.total_questions
    }).execute()

    return new_assessment.data
