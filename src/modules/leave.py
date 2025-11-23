# src/modules/leave.py
# Leave module: form + helpers

import streamlit as st
from src.utils.db import init_supabase, now_iso
from src.utils.audit import audit_log
import json
from datetime import date

supabase = init_supabase()

def get_user(emp_id):
    if not supabase: return None
    res = supabase.table("employees").select("*").eq("emp_id", emp_id).execute()
    return res.data[0] if res.data else None

def get_leave_balances(emp_id):
    user = get_user(emp_id)
    if not user: return {}
    lb = user.get("leave_balances") or {}
    if isinstance(lb, str):
        try: lb = json.loads(lb)
        except: lb = {}
    return lb

def render_leave_module(user):
    st.header("🌴 إدارة الإجازات")
    lb = get_leave_balances(user['emp_id'])
    if lb:
        st.write("رصيد الإجازات الحالي:")
        for k,v in lb.items(): st.write(f"- {k}: {v} أيام")
    else:
        st.info("لم يتم تسجيل أرصدة إجازات بعد.")
    with st.form("leave_form"):
        ltype = st.selectbox("نوع الإجازة", ["سنوية (Yearly)", "مرضية (Sick)", "بدون راتب (Unpaid)"])
        d1 = st.date_input("تاريخ البداية", date.today())
        d2 = st.date_input("تاريخ النهاية", date.today())
        reason = st.text_area("سبب/ملاحظات")
        sub_id = st.text_input("رقم الموظف البديل (اختياري)")
        submit = st.form_submit_button("إرسال")
        if submit:
            days = (d2 - d1).days + 1 if d2 >= d1 else -1
            if days <= 0:
                st.error("التحقق من التواريخ.")
                return
            payload = {
                "service_type": "إجازة",
                "sub_type": ltype,
                "details": reason,
                "start_date": str(d1),
                "end_date": str(d2),
                "days": days,
                "substitute_id": sub_id or None,
                "substitute_name": None,
                "created_at": now_iso(),
                "updated_at": now_iso()
            }
            if sub_id:
                su = get_user(sub_id)
                if su: payload["substitute_name"] = su.get("name")
            try:
                supabase.table("requests").insert(payload).execute()
                audit_log(supabase, user, "create:leave", note=f"{ltype} {days} days")
                st.success("تم إرسال طلب الإجازة.")
            except Exception as e:
                st.error(f"فشل إرسال الطلب: {e}")