# src/modules/approvals.py
# Approvals page logic (manager/HR/substitute)

import streamlit as st
from src.utils.db import init_supabase, now_iso
from src.utils.audit import audit_log

supabase = init_supabase()

def get_tasks_for(user):
    tasks = []
    try:
        # substitute tasks
        if user:
            sub = supabase.table("requests").select("*").eq("substitute_id", user['emp_id']).eq("status_substitute", "Pending").execute().data or []
            for r in sub: r['task_type'] = 'Substitute'; tasks.append(r)
            if user['role'] in ('Supervisor','Manager'):
                mgr = supabase.table("requests").select("*").eq("dept", user['dept']).eq("status_manager", "Pending").execute().data or []
                for r in mgr:
                    if r['status_substitute'] in ('Approved','Not Required'):
                        r['task_type'] = 'Manager'; tasks.append(r)
            if user['role'] == 'HR':
                hr = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data or []
                for r in hr: r['task_type']='HR'; tasks.append(r)
    except Exception as e:
        st.error("خطأ في جلب المهام.")
    return tasks

def render_approvals(user):
    st.title("✅ مهام الاعتماد")
    tasks = get_tasks_for(user)
    if not tasks:
        st.info("لا توجد مهام.")
        return
    for r in tasks:
        with st.expander(f"{r['service_type']} - {r['emp_name']}", expanded=True):
            st.write(r.get('details'))
            note = st.text_input("ملاحظات", key=f"note_{r['id']}")
            c1,c2 = st.columns(2)
            if c1.button("قبول", key=f"ok_{r['id']}"):
                field = 'status_substitute' if r['task_type']=='Substitute' else 'status_manager' if r['task_type']=='Manager' else 'status_hr'
                supabase.table("requests").update({
                    field: "Approved",
                    f"{field.replace('status_','')}_note": note,
                    f"{field.replace('status_','')}_action_at": now_iso(),
                    "updated_at": now_iso()
                }).eq("id", r['id']).execute()
                audit_log(supabase, user, f"approve:{field}", target_request_id=r['id'], note=note)
                st.experimental_rerun()
            if c2.button("رفض", key=f"no_{r['id']}"):
                field = 'status_substitute' if r['task_type']=='Substitute' else 'status_manager' if r['task_type']=='Manager' else 'status_hr'
                supabase.table("requests").update({
                    field: "Rejected",
                    f"{field.replace('status_','')}_note": note,
                    f"{field.replace('status_','')}_action_at": now_iso(),
                    "final_status": "Rejected",
                    "updated_at": now_iso()
                }).eq("id", r['id']).execute()
                audit_log(supabase, user, f"reject:{field}", target_request_id=r['id'], note=note)
                st.experimental_rerun()