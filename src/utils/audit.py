# src/utils/audit.py
# Audit logging helpers

def audit_log(supabase, actor, action, target_request_id=None, note=None):
    try:
        supabase.table("audit_logs").insert({
            "actor_emp_id": actor.get("emp_id"),
            "actor_name": actor.get("name"),
            "action": action,
            "target_request_id": target_request_id,
            "note": note,
            "created_at": __import__("datetime").datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print("audit_log error:", e)