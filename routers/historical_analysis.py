from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/historical", tags=["Historical Analysis"])


# ==========================
# COMPARATIVO DE TURMAS
# ==========================

@router.get("/class/{class_id}/comparison")
def get_class_historical_comparison(
    class_id: str,
    user=Depends(get_current_user),
    months: int = 6,
    period: str = "monthly"  # monthly, weekly, all
):
    """Retorna comparativo histórico de uma turma ao longo do tempo"""
    
    try:
        # Buscar submissões da turma
        submissions = supabase.table("student_submissions") \
            .select("score, status, created_at") \
            .eq("class_id", class_id) \
            .order("created_at") \
            .execute()
        
        subs = submissions.data or []
        
        if not subs:
            return {
                "periods": [],
                "trend": "no_data",
                "improvement": 0
            }
        
        # Agrupar por período
        periods_data = {}
        
        for sub in subs:
            date = datetime.fromisoformat(sub["created_at"])
            
            if period == "monthly":
                key = date.strftime("%Y-%m")
                label = date.strftime("%b/%Y")
            elif period == "weekly":
                key = date.strftime("%Y-W%U")
                label = f"Semana {date.strftime('%U/%Y')}"
            else:
                key = date.strftime("%Y-%m-%d")
                label = date.strftime("%d/%m/%Y")
            
            if key not in periods_data:
                periods_data[key] = {
                    "label": label,
                    "scores": [],
                    "approved": 0,
                    "failed": 0,
                    "absent": 0
                }
            
            if sub.get("status") == "corrected":
                score = sub.get("score", 0)
                periods_data[key]["scores"].append(score)
                
                if score >= 6:
                    periods_data[key]["approved"] += 1
                else:
                    periods_data[key]["failed"] += 1
            elif sub.get("status") == "ausente":
                periods_data[key]["absent"] += 1
        
        # Calcular médias por período
        periods = []
        for key in sorted(periods_data.keys()):
            data = periods_data[key]
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            total = len(data["scores"]) + data["absent"]
            approval_rate = (data["approved"] / len(data["scores"]) * 100) if data["scores"] else 0
            
            periods.append({
                "period": data["label"],
                "average": round(avg, 2),
                "approval_rate": round(approval_rate, 1),
                "approved": data["approved"],
                "failed": data["failed"],
                "absent": data["absent"],
                "total": total
            })
        
        # Calcular tendência
        if len(periods) >= 2:
            first_avg = periods[0]["average"]
            last_avg = periods[-1]["average"]
            improvement = last_avg - first_avg
            
            if improvement > 0.5:
                trend = "improving"
            elif improvement < -0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            improvement = 0
            trend = "insufficient_data"
        
        return {
            "periods": periods[-months:] if len(periods) > months else periods,
            "trend": trend,
            "improvement": round(improvement, 2),
            "total_periods": len(periods)
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar comparativo de turma: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# COMPARATIVO DE ALUNOS
# ==========================

@router.get("/student/{student_id}/comparison")
def get_student_historical_comparison(
    student_id: str,
    user=Depends(get_current_user),
    months: int = 12
):
    """Retorna comparativo histórico de um aluno ao longo do tempo"""
    
    try:
        # Buscar submissões do aluno
        submissions = supabase.table("student_submissions") \
            .select("score, status, created_at, assessment_id") \
            .eq("student_id", student_id) \
            .order("created_at") \
            .execute()
        
        subs = submissions.data or []
        
        if not subs:
            return {
                "submissions": [],
                "trend": "no_data",
                "improvement": 0,
                "average": 0
            }
        
        # Agrupar por mês
        months_data = {}
        
        for sub in subs:
            if sub.get("status") != "corrected":
                continue
            
            date = datetime.fromisoformat(sub["created_at"])
            key = date.strftime("%Y-%m")
            label = date.strftime("%b/%Y")
            
            if key not in months_data:
                months_data[key] = {
                    "label": label,
                    "scores": [],
                    "count": 0
                }
            
            score = sub.get("score", 0)
            months_data[key]["scores"].append(score)
            months_data[key]["count"] += 1
        
        # Calcular médias por mês
        submissions_data = []
        for key in sorted(months_data.keys()):
            data = months_data[key]
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            
            submissions_data.append({
                "month": data["label"],
                "average": round(avg, 2),
                "count": data["count"],
                "scores": data["scores"]
            })
        
        # Calcular tendência geral
        all_scores = [s.get("score", 0) for s in subs if s.get("status") == "corrected"]
        overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
        
        if len(submissions_data) >= 2:
            first_avg = submissions_data[0]["average"]
            last_avg = submissions_data[-1]["average"]
            improvement = last_avg - first_avg
            
            if improvement > 0.5:
                trend = "improving"
            elif improvement < -0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            improvement = 0
            trend = "insufficient_data"
        
        return {
            "submissions": submissions_data[-months:] if len(submissions_data) > months else submissions_data,
            "trend": trend,
            "improvement": round(improvement, 2),
            "average": round(overall_avg, 2),
            "total_submissions": len(all_scores)
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar comparativo de aluno: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# COMPARATIVO DE PROFESSORES
# ==========================

@router.get("/teacher/{teacher_id}/comparison")
def get_teacher_historical_comparison(
    teacher_id: str,
    user=Depends(get_current_user),
    months: int = 6
):
    """Retorna comparativo histórico de um professor ao longo do tempo"""
    
    try:
        # Buscar turmas do professor
        teacher_classes = supabase.table("teacher_classes") \
            .select("class_id") \
            .eq("teacher_id", teacher_id) \
            .execute()
        
        class_ids = [tc["class_id"] for tc in (teacher_classes.data or [])]
        
        if not class_ids:
            return {
                "periods": [],
                "trend": "no_data",
                "improvement": 0
            }
        
        # Buscar submissões das turmas
        submissions = supabase.table("student_submissions") \
            .select("score, status, created_at") \
            .in_("class_id", class_ids) \
            .order("created_at") \
            .execute()
        
        subs = submissions.data or []
        
        # Agrupar por mês
        periods_data = {}
        
        for sub in subs:
            date = datetime.fromisoformat(sub["created_at"])
            key = date.strftime("%Y-%m")
            label = date.strftime("%b/%Y")
            
            if key not in periods_data:
                periods_data[key] = {
                    "label": label,
                    "scores": [],
                    "approved": 0,
                    "failed": 0
                }
            
            if sub.get("status") == "corrected":
                score = sub.get("score", 0)
                periods_data[key]["scores"].append(score)
                
                if score >= 6:
                    periods_data[key]["approved"] += 1
                else:
                    periods_data[key]["failed"] += 1
        
        # Calcular médias por período
        periods = []
        for key in sorted(periods_data.keys()):
            data = periods_data[key]
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            approval_rate = (data["approved"] / len(data["scores"]) * 100) if data["scores"] else 0
            
            periods.append({
                "period": data["label"],
                "average": round(avg, 2),
                "approval_rate": round(approval_rate, 1),
                "approved": data["approved"],
                "failed": data["failed"],
                "total": len(data["scores"])
            })
        
        # Calcular tendência
        if len(periods) >= 2:
            first_avg = periods[0]["average"]
            last_avg = periods[-1]["average"]
            improvement = last_avg - first_avg
            
            if improvement > 0.5:
                trend = "improving"
            elif improvement < -0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            improvement = 0
            trend = "insufficient_data"
        
        return {
            "periods": periods[-months:] if len(periods) > months else periods,
            "trend": trend,
            "improvement": round(improvement, 2),
            "total_periods": len(periods)
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar comparativo de professor: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# COMPARATIVO ENTRE TURMAS
# ==========================

@router.get("/classes/comparison")
def compare_classes(
    user=Depends(get_current_user),
    school_id: Optional[str] = None,
    months: int = 6
):
    """Compara desempenho de todas as turmas ao longo do tempo"""
    
    try:
        if not school_id:
            school_id = user["school_id"]
        
        # Buscar turmas
        classes = supabase.table("classes") \
            .select("id, name") \
            .eq("school_id", school_id) \
            .execute()
        
        classes_data = classes.data or []
        result = []
        
        for cls in classes_data:
            # Buscar submissões da turma
            submissions = supabase.table("student_submissions") \
                .select("score, status, created_at") \
                .eq("class_id", cls["id"]) \
                .order("created_at") \
                .execute()
            
            subs = submissions.data or []
            
            # Agrupar por mês
            months_data = {}
            for sub in subs:
                if sub.get("status") != "corrected":
                    continue
                
                date = datetime.fromisoformat(sub["created_at"])
                key = date.strftime("%Y-%m")
                label = date.strftime("%b/%Y")
                
                if key not in months_data:
                    months_data[key] = {
                        "label": label,
                        "scores": []
                    }
                
                months_data[key]["scores"].append(sub.get("score", 0))
            
            # Calcular média por mês
            monthly_avg = []
            for key in sorted(months_data.keys()):
                scores = months_data[key]["scores"]
                avg = sum(scores) / len(scores) if scores else 0
                monthly_avg.append(round(avg, 2))
            
            if monthly_avg:
                overall_avg = sum(monthly_avg) / len(monthly_avg)
                trend = "improving" if len(monthly_avg) >= 2 and monthly_avg[-1] > monthly_avg[0] else "declining" if len(monthly_avg) >= 2 and monthly_avg[-1] < monthly_avg[0] else "stable"
            else:
                overall_avg = 0
                trend = "no_data"
            
            result.append({
                "class_id": cls["id"],
                "class_name": cls["name"],
                "average": round(overall_avg, 2),
                "trend": trend,
                "monthly_averages": monthly_avg[-months:] if len(monthly_avg) > months else monthly_avg
            })
        
        # Ordenar por média (descendente)
        result.sort(key=lambda x: x["average"], reverse=True)
        
        return result
    
    except Exception as e:
        logger.error(f"Erro ao comparar turmas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# EVOLUÇÃO GERAL DA ESCOLA
# ==========================

@router.get("/school/evolution")
def get_school_evolution(
    user=Depends(get_current_user),
    months: int = 12
):
    """Retorna evolução geral da escola ao longo do tempo"""
    
    try:
        school_id = user["school_id"]
        
        # Buscar submissões da escola
        submissions = supabase.table("student_submissions") \
            .select("score, status, created_at") \
            .eq("school_id", school_id) \
            .order("created_at") \
            .execute()
        
        subs = submissions.data or []
        
        # Agrupar por mês
        months_data = {}
        
        for sub in subs:
            date = datetime.fromisoformat(sub["created_at"])
            key = date.strftime("%Y-%m")
            label = date.strftime("%b/%Y")
            
            if key not in months_data:
                months_data[key] = {
                    "label": label,
                    "scores": [],
                    "approved": 0,
                    "failed": 0,
                    "absent": 0
                }
            
            if sub.get("status") == "corrected":
                score = sub.get("score", 0)
                months_data[key]["scores"].append(score)
                
                if score >= 6:
                    months_data[key]["approved"] += 1
                else:
                    months_data[key]["failed"] += 1
            elif sub.get("status") == "ausente":
                months_data[key]["absent"] += 1
        
        # Calcular médias por mês
        periods = []
        for key in sorted(months_data.keys()):
            data = months_data[key]
            avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            total = len(data["scores"]) + data["absent"]
            approval_rate = (data["approved"] / len(data["scores"]) * 100) if data["scores"] else 0
            
            periods.append({
                "month": data["label"],
                "average": round(avg, 2),
                "approval_rate": round(approval_rate, 1),
                "approved": data["approved"],
                "failed": data["failed"],
                "absent": data["absent"],
                "total": total
            })
        
        # Calcular tendência geral
        if len(periods) >= 2:
            first_avg = periods[0]["average"]
            last_avg = periods[-1]["average"]
            improvement = last_avg - first_avg
            
            if improvement > 0.5:
                trend = "improving"
            elif improvement < -0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            improvement = 0
            trend = "insufficient_data"
        
        return {
            "periods": periods[-months:] if len(periods) > months else periods,
            "trend": trend,
            "improvement": round(improvement, 2),
            "total_periods": len(periods)
        }
    
    except Exception as e:
        logger.error(f"Erro ao buscar evolução da escola: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
