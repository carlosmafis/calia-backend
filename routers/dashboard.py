from fastapi import APIRouter, Depends
from core.config import supabase
from core.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ==========================
# PROGRESSO DE UM ALUNO
# ==========================

@router.get("/student-progress/{student_id}")
def student_progress(student_id: str, user=Depends(get_current_user)):
    # Validar se o aluno pertence à mesma escola
    student = supabase.table("students") \
        .select("school_id") \
        .eq("id", student_id) \
        .single() \
        .execute()
    
    if not student.data or student.data.get("school_id") != user["school_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para acessar este aluno")

    data = supabase.table("student_submissions") \
        .select("score,created_at,assessment_id") \
        .eq("student_id", student_id) \
        .eq("school_id", user["school_id"]) \
        .order("created_at") \
        .execute()

    return data.data


# ==========================
# ESTATÍSTICAS GERAIS DA ESCOLA
# ==========================

@router.get("/stats")
def school_stats(user=Depends(get_current_user)):

    school_id = user.get("school_id")

    if not school_id:
        return {"students": 0, "classes": 0, "assessments": 0, "teachers": 0}

    students = supabase.table("students") \
        .select("id", count="exact") \
        .eq("school_id", school_id) \
        .execute()

    classes = supabase.table("classes") \
        .select("id", count="exact") \
        .eq("school_id", school_id) \
        .execute()

    assessments = supabase.table("assessments") \
        .select("id", count="exact") \
        .eq("school_id", school_id) \
        .execute()

    teachers = supabase.table("profiles") \
        .select("id", count="exact") \
        .eq("school_id", school_id) \
        .eq("role", "professor") \
        .execute()

    return {
        "students": students.count or 0,
        "classes": classes.count or 0,
        "assessments": assessments.count or 0,
        "teachers": teachers.count or 0
    }


# ==========================
# ESTATÍSTICAS DO SUPER ADMIN
# ==========================

@router.get("/super-stats")
def super_admin_stats(user=Depends(get_current_user)):

    if user["role"] != "super_admin":
        return {"error": "Sem permissão"}

    schools = supabase.table("schools") \
        .select("id", count="exact") \
        .execute()

    users = supabase.table("profiles") \
        .select("id", count="exact") \
        .execute()

    assessments = supabase.table("assessments") \
        .select("id", count="exact") \
        .execute()

    submissions = supabase.table("student_submissions") \
        .select("id", count="exact") \
        .execute()

    return {
        "schools": schools.count or 0,
        "users": users.count or 0,
        "assessments": assessments.count or 0,
        "submissions": submissions.count or 0
    }


# ==========================
# RESULTADOS DO ALUNO LOGADO
# ==========================

@router.get("/student-results")
def student_results(user=Depends(get_current_user)):
    """Retorna apenas os resultados do aluno logado"""
    
    if user["role"] != "aluno":
        raise HTTPException(status_code=403, detail="Apenas alunos podem acessar seus resultados")
    
    # Buscar o ID do aluno baseado no user_id
    student = supabase.table("students") \
        .select("id") \
        .eq("user_id", user["id"]) \
        .single() \
        .execute()
    
    if not student.data:
        return []
    
    student_id = student.data["id"]
    
    # Buscar submissões do aluno com informações da avaliação
    data = supabase.table("student_submissions") \
        .select("id, score, created_at, assessment_id, status, extracted_answers, assessments(id, title, subject_id, questions, subjects(name))") \
        .eq("student_id", student_id) \
        .eq("school_id", user["school_id"]) \
        .order("created_at", desc=True) \
        .execute()
    
    if not data.data:
        return []
    
    # Formatar dados para o frontend
    results = []
    for submission in data.data:
        assessment = submission.get("assessments", {})
        subject = assessment.get("subjects", {}) if isinstance(assessment.get("subjects"), dict) else {}
        
        # Calcular acertos e erros
        extracted_answers = submission.get("extracted_answers", {})
        questions = assessment.get("questions", [])
        
        correct_count = 0
        wrong_count = 0
        total_questions = len(questions) if questions else 0
        
        if extracted_answers and questions:
            for q in questions:
                q_id = str(q.get("id", ""))
                answer = extracted_answers.get(q_id)
                correct_answer = q.get("correct_answer")
                
                if answer and correct_answer:
                    if answer == correct_answer:
                        correct_count += 1
                    else:
                        wrong_count += 1
        
        results.append({
            "id": submission["id"],
            "score": submission["score"],
            "assessment_title": assessment.get("title", "Avaliação"),
            "subject_name": subject.get("name", "") if subject else "",
            "date": submission["created_at"],
            "assessment_id": submission["assessment_id"],
            "status": submission.get("status", "pending"),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "total_questions": total_questions
        })
    
    return results


# ==========================
# SUBMISSÕES RECENTES
# ==========================

@router.get("/recent-submissions")
def recent_submissions(user=Depends(get_current_user)):

    query = supabase.table("student_submissions") \
        .select("*, students(name), assessments(title)") \
        .eq("school_id", user["school_id"]) \
        .order("created_at", desc=True) \
        .limit(20)

    data = query.execute()

    return data.data or []
