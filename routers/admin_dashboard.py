from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ==========================
# KPIs GERAIS DA ESCOLA
# ==========================

@router.get("/dashboard/overview")
def get_dashboard_overview(user=Depends(get_current_user)):
    """Retorna KPIs gerais da escola para o admin"""
    
    # Verificar se é admin
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        # Buscar todas as submissões da escola
        submissions = supabase.table("student_submissions") \
            .select("id, score, status, student_id, assessment_id") \
            .eq("school_id", school_id) \
            .execute()
        
        subs_data = submissions.data or []
        
        # Buscar todas as avaliações
        assessments = supabase.table("assessments") \
            .select("id, class_id") \
            .eq("school_id", school_id) \
            .execute()
        
        # Buscar todos os alunos
        students = supabase.table("students") \
            .select("id") \
            .eq("school_id", school_id) \
            .execute()
        
        # Calcular KPIs
        total_students = len(students.data or [])
        total_submissions = len(subs_data)
        
        # Contar por status
        approved = sum(1 for s in subs_data if s.get("status") == "corrected" and s.get("score", 0) >= 6)
        failed = sum(1 for s in subs_data if s.get("status") == "corrected" and s.get("score", 0) < 6)
        absent = sum(1 for s in subs_data if s.get("status") == "ausente")
        
        # Calcular média
        scores = [s.get("score", 0) for s in subs_data if s.get("status") == "corrected" and s.get("score") is not None]
        average = sum(scores) / len(scores) if scores else 0
        
        # Calcular taxa de aprovação
        approval_rate = (approved / (approved + failed) * 100) if (approved + failed) > 0 else 0
        
        # Alunos em risco (score < 5)
        at_risk = sum(1 for s in subs_data if s.get("status") == "corrected" and s.get("score", 0) < 5)
        
        return {
            "total_students": total_students,
            "total_submissions": total_submissions,
            "approved": approved,
            "failed": failed,
            "absent": absent,
            "average": round(average, 2),
            "approval_rate": round(approval_rate, 1),
            "at_risk": at_risk,
            "assessments_count": len(assessments.data or [])
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# MONITORAMENTO POR TURMA
# ==========================

@router.get("/dashboard/classes")
def get_classes_monitoring(user=Depends(get_current_user)):
    """Retorna monitoramento de todas as turmas com ranking"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        # Buscar todas as turmas
        classes = supabase.table("classes") \
            .select("id, name") \
            .eq("school_id", school_id) \
            .execute()
        
        classes_data = classes.data or []
        result = []
        
        for cls in classes_data:
            # Buscar submissões da turma
            submissions = supabase.table("student_submissions") \
                .select("score, status") \
                .eq("class_id", cls["id"]) \
                .execute()
            
            subs = submissions.data or []
            
            # Calcular estatísticas
            scores = [s.get("score", 0) for s in subs if s.get("status") == "corrected" and s.get("score") is not None]
            average = sum(scores) / len(scores) if scores else 0
            
            approved = sum(1 for s in subs if s.get("status") == "corrected" and s.get("score", 0) >= 6)
            failed = sum(1 for s in subs if s.get("status") == "corrected" and s.get("score", 0) < 6)
            
            approval_rate = (approved / (approved + failed) * 100) if (approved + failed) > 0 else 0
            
            result.append({
                "class_id": cls["id"],
                "class_name": cls["name"],
                "average": round(average, 2),
                "approval_rate": round(approval_rate, 1),
                "total_submissions": len(subs),
                "approved": approved,
                "failed": failed
            })
        
        # Ordenar por média (descendente)
        result.sort(key=lambda x: x["average"], reverse=True)
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao buscar turmas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# MONITORAMENTO DE ALUNOS
# ==========================

@router.get("/dashboard/students")
def get_students_monitoring(
    user=Depends(get_current_user),
    status: str = None,
    class_id: str = None,
    limit: int = 100,
    offset: int = 0
):
    """Retorna lista de alunos com filtros e status"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        # Buscar alunos
        query = supabase.table("students") \
            .select("id, name, registration_number, class_id") \
            .eq("school_id", school_id)
        
        if class_id:
            query = query.eq("class_id", class_id)
        
        students_result = query.execute()
        students_data = students_result.data or []
        
        result = []
        
        for student in students_data:
            # Buscar submissões do aluno
            submissions = supabase.table("student_submissions") \
                .select("score, status") \
                .eq("student_id", student["id"]) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            latest_sub = submissions.data[0] if submissions.data else None
            
            if latest_sub:
                score = latest_sub.get("score", 0)
                sub_status = latest_sub.get("status")
                
                # Determinar status do aluno
                if sub_status == "ausente":
                    student_status = "absent"
                elif score >= 6:
                    student_status = "approved"
                elif score >= 5:
                    student_status = "at_risk"
                else:
                    student_status = "failed"
                
                # Filtrar por status se especificado
                if status and student_status != status:
                    continue
                
                result.append({
                    "student_id": student["id"],
                    "name": student["name"],
                    "registration": student["registration_number"],
                    "class_id": student["class_id"],
                    "latest_score": score,
                    "status": student_status
                })
        
        # Aplicar paginação
        total = len(result)
        result = result[offset:offset + limit]
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "students": result
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar alunos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# MONITORAMENTO DE PROFESSORES
# ==========================

@router.get("/dashboard/teachers")
def get_teachers_monitoring(user=Depends(get_current_user)):
    """Retorna desempenho de professores"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        # Buscar professores
        teachers = supabase.table("v_teachers") \
            .select("id, full_name") \
            .eq("school_id", school_id) \
            .execute()
        
        teachers_data = teachers.data or []
        result = []
        
        for teacher in teachers_data:
            # Buscar turmas do professor
            teacher_classes = supabase.table("teacher_classes") \
                .select("class_id") \
                .eq("teacher_id", teacher["id"]) \
                .execute()
            
            class_ids = [tc["class_id"] for tc in (teacher_classes.data or [])]
            
            if not class_ids:
                continue
            
            # Buscar submissões das turmas do professor
            submissions = supabase.table("student_submissions") \
                .select("score, status") \
                .in_("class_id", class_ids) \
                .execute()
            
            subs = submissions.data or []
            
            # Calcular estatísticas
            scores = [s.get("score", 0) for s in subs if s.get("status") == "corrected" and s.get("score") is not None]
            average = sum(scores) / len(scores) if scores else 0
            
            # Calcular desvio padrão (consistência)
            if len(scores) > 1:
                variance = sum((x - average) ** 2 for x in scores) / len(scores)
                std_dev = variance ** 0.5
            else:
                std_dev = 0
            
            approved = sum(1 for s in subs if s.get("status") == "corrected" and s.get("score", 0) >= 6)
            total = sum(1 for s in subs if s.get("status") == "corrected")
            
            approval_rate = (approved / total * 100) if total > 0 else 0
            
            result.append({
                "teacher_id": teacher["id"],
                "name": teacher["name"],
                "average": round(average, 2),
                "std_dev": round(std_dev, 2),
                "approval_rate": round(approval_rate, 1),
                "total_submissions": len(subs),
                "classes_count": len(class_ids)
            })
        
        # Ordenar por média
        result.sort(key=lambda x: x["average"], reverse=True)
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao buscar professores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# ALERTAS DE RISCO
# ==========================

@router.get("/dashboard/alerts")
def get_alerts(user=Depends(get_current_user)):
    """Retorna alertas de risco (alunos em risco, frequência baixa, etc)"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        alerts = []
        
        # Buscar alunos com score < 5
        submissions = supabase.table("student_submissions") \
            .select("student_id, score, status, students(name, registration_number)") \
            .eq("school_id", school_id) \
            .execute()
        
        subs_data = submissions.data or []
        
        for sub in subs_data:
            if sub.get("status") == "corrected" and sub.get("score", 0) < 5:
                student_name = sub.get("students", {}).get("name", "Aluno") if isinstance(sub.get("students"), dict) else "Aluno"
                student_reg = sub.get("students", {}).get("registration_number", "—") if isinstance(sub.get("students"), dict) else "—"
                
                alerts.append({
                    "type": "low_score",
                    "severity": "high",
                    "message": f"Aluno {student_name} ({student_reg}) com nota baixa: {sub.get('score', 0)}/10",
                    "student_id": sub.get("student_id")
                })
        
        # Buscar alunos ausentes
        absent_subs = [s for s in subs_data if s.get("status") == "ausente"]
        if absent_subs:
            alerts.append({
                "type": "absent_students",
                "severity": "medium",
                "message": f"{len(absent_subs)} alunos marcados como ausentes",
                "count": len(absent_subs)
            })
        
        return alerts[:20]  # Limitar a 20 alertas
    
    except Exception as e:
        logger.error(f"Erro ao buscar alertas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


# ==========================
# ENDPOINTS SIMPLES PARA SELETORES
# ==========================

@router.get("/classes")
def get_classes_list(user=Depends(get_current_user)):
    """Retorna lista simples de turmas para seletor"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        classes = supabase.table("classes") \
            .select("id, name") \
            .eq("school_id", school_id) \
            .execute()
        
        return classes.data or []
    
    except Exception as e:
        logger.error(f"Erro ao buscar turmas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


@router.get("/students")
def get_students_list(user=Depends(get_current_user)):
    """Retorna lista simples de alunos para seletor"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        students = supabase.table("students") \
            .select("id, name") \
            .eq("school_id", school_id) \
            .execute()
        
        return students.data or []
    
    except Exception as e:
        logger.error(f"Erro ao buscar alunos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")


@router.get("/teachers")
def get_teachers_list(user=Depends(get_current_user)):
    """Retorna lista simples de professores para seletor"""
    
    if user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    try:
        school_id = user["school_id"]
        
        teachers = supabase.table("v_teachers") \
            .select("id, full_name") \
            .eq("school_id", school_id) \
            .execute()
        
        return teachers.data or []
    
    except Exception as e:
        logger.error(f"Erro ao buscar professores: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")
