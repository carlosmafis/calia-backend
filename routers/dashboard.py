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
