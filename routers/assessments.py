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
    weight: float = 1.0


class AssessmentCreate(BaseModel):
    class_id: str
    subject_id: str
    title: str
    questions: List[QuestionItem]


# ==========================
# LISTAR AVALIAÇÕES
# ==========================

@router.get("/")
@router.get("")
def list_assessments(user=Depends(get_current_user)):

    if user["role"] == "professor":
        # Professor vê apenas avaliações das suas turmas
        teacher_classes = supabase.table("teacher_classes") \
            .select("class_id") \
            .eq("teacher_id", user["id"]) \
            .execute()

        class_ids = [tc["class_id"] for tc in (teacher_classes.data or [])]

        if not class_ids:
            return []

        data = supabase.table("assessments") \
            .select("*") \
            .eq("school_id", user["school_id"]) \
            .in_("class_id", class_ids) \
            .execute()

        return data.data

    # Admin e super_admin veem tudo da escola
    data = supabase.table("assessments") \
        .select("*") \
        .eq("school_id", user["school_id"]) \
        .execute()

    return data.data


# ==========================
# DETALHES DE UMA AVALIAÇÃO
# ==========================

@router.get("/{assessment_id}")
def get_assessment(assessment_id: str, user=Depends(get_current_user)):

    assessment = supabase.table("assessments") \
        .select("*") \
        .eq("id", assessment_id) \
        .single() \
        .execute()

    if not assessment.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")

    # Buscar questões
    questions = supabase.table("assessment_questions") \
        .select("*") \
        .eq("assessment_id", assessment_id) \
        .order("question_number") \
        .execute()

    result = assessment.data
    result["questions"] = questions.data or []

    return result


# ==========================
# CRIAR AVALIAÇÃO + GABARITO
# ==========================

@router.post("/create-full")
@router.post("/")
@router.post("")
def create_assessment(data: AssessmentCreate, user=Depends(get_current_user)):

    # Permitir professor e admin criarem avaliações
    if user["role"] not in ("professor", "admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão para criar avaliação")

    # Validar dados
    if not data.class_id:
        raise HTTPException(status_code=400, detail="class_id é obrigatório")
    if not data.subject_id:
        raise HTTPException(status_code=400, detail="subject_id é obrigatório")
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="title é obrigatório")
    if not data.questions or len(data.questions) == 0:
        raise HTTPException(status_code=400, detail="questions não pode estar vazio")

    try:
        assessment = supabase.table("assessments").insert({
            "school_id": user["school_id"],
            "class_id": data.class_id,
            "subject_id": data.subject_id,
            "created_by": user["id"],
            "title": data.title.strip(),
            "total_questions": len(data.questions)
        }).execute().data[0]

        rows = []
        for q in data.questions:
            rows.append({
                "assessment_id": assessment["id"],
                "question_number": q.question_number,
                "correct_answer": q.correct_answer,
                "weight": q.weight
            })

        if rows:
            supabase.table("assessment_questions").insert(rows).execute()

        return {"message": "Avaliação criada com sucesso", "data": assessment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar avaliação: {str(e)}")


# ==========================
# RESULTADOS DE UMA AVALIAÇÃO
# ==========================

@router.get("/{assessment_id}/results")
@router.get("/{assessment_id}/results/")
def get_assessment_results(assessment_id: str, user=Depends(get_current_user)):

    try:
        submissions = supabase.table("student_submissions") \
            .select("*, students(name)") \
            .eq("assessment_id", assessment_id) \
            .execute()

        return submissions.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar resultados: {str(e)}")
