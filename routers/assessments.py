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
    
from pydantic import BaseModel
from typing import List

class AnswerItem(BaseModel):
    question_number:int
    correct_answer:str

class AnswerKey(BaseModel):
    assessment_id:str
    answers:List[AnswerItem]


@router.post("/answer-key")
def save_answer_key(data:AnswerKey,user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    supabase.table("assessment_questions")\
    .delete()\
    .eq("assessment_id",data.assessment_id)\
    .execute()

    rows=[]

    for q in data.answers:

        rows.append({
            "assessment_id":data.assessment_id,
            "question_number":q.question_number,
            "correct_answer":q.correct_answer,
            "weight":1
        })

    supabase.table("assessment_questions").insert(rows).execute()

    return {"message":"gabarito salvo"}
    
@router.get("/answer-key/{assessment_id}")
def get_answer_key(assessment_id:str,user=Depends(get_current_user)):

    data = supabase.table("assessment_questions")\
    .select("*")\
    .eq("assessment_id",assessment_id)\
    .order("question_number")\
    .execute()

    return data.data
