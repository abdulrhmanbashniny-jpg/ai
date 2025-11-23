# app.py (entry point)
# This file ties modules together. Place at repo root.

import streamlit as st
from src.utils.db import init_supabase
from src.modules.leave import render_leave_module
from src.modules.approvals import render_approvals

supabase = init_supabase()

if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'module' not in st.session_state: st.session_state['module'] = None

def login_page():
    st.header("🔐 بوابة الموظفين")
    with st.form("login"):
        uid = st.text_input("رقم الموظف")
        pwd = st.text_input("كلمة المرور", type="password")
        if st.form_submit_button("تسجيل الدخول"):
            res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
            user = res.data[0] if res.data else None
            if user and user.get('password') == pwd:
                st.session_state['user'] = user
                st.session_state['page'] = 'dashboard'
                st.experimental_rerun()
            else:
                st.error("بيانات غير صحيحة")

def sidebar_user_panel():
    with st.sidebar:
        if st.session_state['user']:
            st.write(f"👤 {st.session_state['user']['name']}")
            if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.experimental_rerun()
            if st.button("✅ المهام"): st.session_state['page']='approvals'; st.experimental_rerun()
            if st.button("📂 سجلي"): st.session_state['page']='my_requests'; st.experimental_rerun()
            if st.button("🚪 تسجيل خروج"):
                st.session_state.clear(); st.experimental_rerun()

def dashboard_page():
    st.title("لوحة الخدمات")
    if st.button("إدارة الإجازات"): st.session_state['module']='leave'; st.session_state['page']='module'; st.experimental_rerun()
    if st.button("الموافقات"): st.session_state['page']='approvals'; st.experimental_rerun()

def module_router():
    if st.session_state['module'] == 'leave':
        render_leave_module(st.session_state['user'])
    else:
        st.info("اختر وحدة من الشريط الجانبي")

if st.session_state['page'] == 'login':
    login_page()
else:
    sidebar_user_panel()
    if st.session_state['page'] == 'dashboard':
        dashboard_page()
    elif st.session_state['page'] == 'module':
        module_router()
    elif st.session_state['page'] == 'approvals':
        render_approvals(st.session_state['user'])
    else:
        st.info("صفحة غير معروفة")