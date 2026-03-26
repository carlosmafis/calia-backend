from fastapi import APIRouter, Depends, HTTPException
from core.auth import get_current_user
from core.config import supabase
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ==========================
# GERAR ALERTAS AUTOMÁTICOS
# ==========================

@router.post("/generate")
def generate_alerts(user=Depends(get_current_user)):
    """Gera alertas automáticos baseado em regras de risco"""
    
    try:
        school_id = user["school_id"]
        alerts = []
        
        # Regra 1: Alunos com score < 5 (Risco Alto)
        submissions = supabase.table("student_submissions") \
            .select("student_id, score, status, students(name, registration_number)") \
            .eq("school_id", school_id) \
            .execute()
        
        subs_data = submissions.data or []
        
        for sub in subs_data:
            if sub.get("status") == "corrected" and sub.get("score", 0) < 5:
                student_name = sub.get("students", {}).get("name", "Aluno") if isinstance(sub.get("students"), dict) else "Aluno"
                student_id = sub.get("student_id")
                
                # Verificar se já existe alerta similar
                existing = supabase.table("alerts") \
                    .select("id") \
                    .eq("student_id", student_id) \
                    .eq("alert_type", "low_score") \
                    .gte("created_at", (datetime.now() - timedelta(hours=24)).isoformat()) \
                    .execute()
                
                if not existing.data:
                    alert_data = {
                        "school_id": school_id,
                        "student_id": student_id,
                        "alert_type": "low_score",
                        "severity": "high",
                        "title": f"Aluno em Risco: {student_name}",
                        "message": f"Nota baixa detectada: {sub.get('score', 0)}/10",
                        "is_read": False,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    result = supabase.table("alerts").insert(alert_data).execute()
                    if result.data:
                        alerts.append(result.data[0])
        
        # Regra 2: Alunos ausentes
        absent_subs = [s for s in subs_data if s.get("status") == "ausente"]
        if len(absent_subs) > 5:
            alert_data = {
                "school_id": school_id,
                "alert_type": "high_absence",
                "severity": "medium",
                "title": "Taxa Alta de Ausências",
                "message": f"{len(absent_subs)} alunos marcados como ausentes",
                "is_read": False,
                "created_at": datetime.now().isoformat()
            }
            
            existing = supabase.table("alerts") \
                .select("id") \
                .eq("alert_type", "high_absence") \
                .eq("school_id", school_id) \
                .gte("created_at", (datetime.now() - timedelta(hours=24)).isoformat()) \
                .execute()
            
            if not existing.data:
                result = supabase.table("alerts").insert(alert_data).execute()
                if result.data:
                    alerts.append(result.data[0])
        
        # Regra 3: Turmas com taxa de aprovação < 50%
        classes = supabase.table("classes") \
            .select("id, name") \
            .eq("school_id", school_id) \
            .execute()
        
        for cls in (classes.data or []):
            class_subs = [s for s in subs_data if s.get("class_id") == cls["id"]]
            
            if class_subs:
                approved = sum(1 for s in class_subs if s.get("status") == "corrected" and s.get("score", 0) >= 6)
                total = sum(1 for s in class_subs if s.get("status") == "corrected")
                
                if total > 0:
                    approval_rate = (approved / total) * 100
                    
                    if approval_rate < 50:
                        alert_data = {
                            "school_id": school_id,
                            "alert_type": "low_approval_rate",
                            "severity": "high",
                            "title": f"Turma com Baixa Aprovação: {cls['name']}",
                            "message": f"Taxa de aprovação: {approval_rate:.1f}%",
                            "is_read": False,
                            "created_at": datetime.now().isoformat()
                        }
                        
                        existing = supabase.table("alerts") \
                            .select("id") \
                            .eq("alert_type", "low_approval_rate") \
                            .eq("school_id", school_id) \
                            .gte("created_at", (datetime.now() - timedelta(hours=24)).isoformat()) \
                            .execute()
                        
                        if not existing.data:
                            result = supabase.table("alerts").insert(alert_data).execute()
                            if result.data:
                                alerts.append(result.data[0])
        
        return {
            "generated": len(alerts),
            "alerts": alerts
        }
    
    except Exception as e:
        logger.error(f"Erro ao gerar alertas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar alertas: {str(e)}")


# ==========================
# LISTAR ALERTAS
# ==========================

@router.get("/")
def list_alerts(
    user=Depends(get_current_user),
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0
):
    """Lista alertas do usuário/escola"""
    
    try:
        school_id = user["school_id"]
        
        query = supabase.table("alerts") \
            .select("*") \
            .eq("school_id", school_id)
        
        if unread_only:
            query = query.eq("is_read", False)
        
        result = query \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        return {
            "total": len(result.data or []),
            "limit": limit,
            "offset": offset,
            "alerts": result.data or []
        }
    
    except Exception as e:
        logger.error(f"Erro ao listar alertas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar alertas: {str(e)}")


# ==========================
# MARCAR ALERTA COMO LIDO
# ==========================

@router.put("/{alert_id}/read")
def mark_alert_as_read(alert_id: str, user=Depends(get_current_user)):
    """Marca um alerta como lido"""
    
    try:
        result = supabase.table("alerts") \
            .update({"is_read": True}) \
            .eq("id", alert_id) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Alerta não encontrado")
        
        return result.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao marcar alerta como lido: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# MARCAR TODOS COMO LIDOS
# ==========================

@router.put("/read-all")
def mark_all_alerts_as_read(user=Depends(get_current_user)):
    """Marca todos os alertas como lidos"""
    
    try:
        school_id = user["school_id"]
        
        result = supabase.table("alerts") \
            .update({"is_read": True}) \
            .eq("school_id", school_id) \
            .eq("is_read", False) \
            .execute()
        
        return {
            "message": "Alertas marcados como lidos",
            "count": len(result.data or [])
        }
    
    except Exception as e:
        logger.error(f"Erro ao marcar alertas como lidos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# DELETAR ALERTA
# ==========================

@router.delete("/{alert_id}")
def delete_alert(alert_id: str, user=Depends(get_current_user)):
    """Deleta um alerta"""
    
    try:
        result = supabase.table("alerts") \
            .delete() \
            .eq("id", alert_id) \
            .execute()
        
        return {"message": "Alerta deletado com sucesso"}
    
    except Exception as e:
        logger.error(f"Erro ao deletar alerta: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")


# ==========================
# CONTAR ALERTAS NÃO LIDOS
# ==========================

@router.get("/count/unread")
def count_unread_alerts(user=Depends(get_current_user)):
    """Retorna número de alertas não lidos"""
    
    try:
        school_id = user["school_id"]
        
        result = supabase.table("alerts") \
            .select("id") \
            .eq("school_id", school_id) \
            .eq("is_read", False) \
            .execute()
        
        return {
            "unread_count": len(result.data or [])
        }
    
    except Exception as e:
        logger.error(f"Erro ao contar alertas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")
