import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="HR Enterprise System", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; cursor: pointer;
    }
    .service-card:hover { transform: translateY(-5px); border-color: #2ecc71; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بـ Supabase ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- 3. دوال البيانات ---
def get_user_data(uid):
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def submit_request_db(data):
    try:
        res = supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ: {e}")
        return False

def get_requests_for_role(role, uid, dept):
    if role == "Employee":
        return supabase.table("requests").select("*").eq("emp_id", uid).execute().data
    if role == "Manager":
        return supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
    if role == "HR":
        return supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
    return []

def update_status_db(req_id, field, status, note, user_name):
    data = {
        field: status,
        f"{field.replace('status_', '')}_note": note,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat()
    }
    if field == "status_hr" and status == "Approved":
        data["final_status"] = "Approved"
    elif status == "Rejected":
        data["final_status"] = "Rejected"
    supabase.table("requests").update(data).eq("id", req_id).execute()

# --- 4. إدارة الجلسة ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'

def login_page():
    st.markdown("<br><h1 style='text-align:center; color:#2980b9;'>🔐 دخول النظام المركزي</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف (جرب 1011)")
            pwd = st.text_input("كلمة المرور", type="password", value="123456")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user_data(uid)
                if user and user['password'] == pwd:
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else:
                    st.error("بيانات خاطئة")

# --- 5. الصفحات ---
def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 مرحباً، {u['name']}")
    
    if u['role'] in ['Manager', 'HR']:
        count = len(get_requests_for_role(u['role'], u['emp_id'], u['dept']))
        if count > 0:
            st.info(f"🔔 لديك ({count}) طلبات بانتظار الاعتماد!")

    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 طلب إجازة</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم إجازة"): nav("leave")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 سلفة مالية</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم سلفة"): nav("loan")
    with c3:
        st.markdown('<div class="service-card"><h3>📂 متابعة طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("السجل والطباعة"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def form_page():
    u = st.session_state['user']
    svc = st.session_state['service']
    if st.button("🔙 إلغاء"): st.session_state['page']='dashboard'; st.rerun()
    
    st.write("---")
    
    if svc == 'leave':
        st.header("🌴 نموذج طلب إجازة")
        
        # 1. البيانات الشخصية
        c1, c2, c3 = st.columns(3)
        c1.text_input("الاسم", u['name'], disabled=True)
        c2.text_input("القسم", u['dept'], disabled=True)
        c3.text_input("الجوال", u['phone'], disabled=True)
        
        st.divider()
        
        # 2. نوع الإجازة
        l_type = st.selectbox("ن
