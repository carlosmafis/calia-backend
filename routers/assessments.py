from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from core.auth import get_current_user
from core.config import supabase

router = APIRouter()


# ==========================
# MODELOS
# ==========================

class QuestionItem(BaseModel):
    question_number: int
    correct_answer: str


class AssessmentCreate(BaseModel):
    class_id: str
    subject_id:str
    title: str
    questions: List[QuestionItem]


# ==========================
# LISTAR AVALIAÇÕES
# ==========================

@router.get("/")
def list_assessments(user=Depends(get_current_user)):

    data = supabase.table("assessments") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return data.data


# ==========================
# CRIAR AVALIAÇÃO + GABARITO
# ==========================

@router.post("/create-full")
def create_assessment(data: AssessmentCreate, user=Depends(get_current_user)):

    if user["role"] != "professor":
        raise HTTPException(status_code=403)

    assessment = supabase.table("assessments").insert({

        "school_id": user["school_id"],
        "class_id": data.class_id,
        "subject_id": data.subject_id,
        "created_by": user["id"],
        "title": data.title,
        "total_questions": len(data.questions)

    }).execute().data[0]

    rows = []

    for q in data.questions:

        rows.append({

            "assessment_id": assessment["id"],
            "question_number": q.question_number,
            "correct_answer": q.correct_answer,
            "weight": 1

        })

    supabase.table("assessment_questions").insert(rows).execute()

    return assessment