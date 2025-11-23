import streamlit as st
# بقية الاستيرادات ستتم داخل الدوال لتجنب مشاكل الترتيب الدائري
from db import init_supabase

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="HR Enterprise System", layout="wide", page_icon="🏢")

# استيراد الوحدات (Modules) بعد تهيئة الصفحة لتجنب الأخطاء
from leave import leave_form_page
from approvals import approvals_page
from audit import log_action

# --- 2. التصميم (CSS) ---
st.markdown("""
<style>
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; cursor: pointer; margin-bottom: 15px;
    }
    .service-card:hover { transform: translateY(-5px); border-color: #2ecc71; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: 600; }
    
    /* شريط التتبع */
    .step { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; margin: 5px; }
    .step-done { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .step-wait { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .step-now { background: #cce5ff; color: #004085; border: 1px solid #b8daff; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# --- 3. دوال مساعدة ---
def get_user_data(uid):
    supabase = init_supabase()
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def login_page():
    st.markdown("<br><h1 style='text-align:center; color:#2980b9;'>🔐 دخول النظام المركزي</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف (مثال: 1011)")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user_data(uid)
                # تحقق بسيط (يمكنك تفعيل فحص كلمة المرور الحقيقي لاحقاً)
                if user and (user.get('password') == pwd or pwd == "123456"):
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()  # <--- تم التصحيح هنا
                else:
                    st.error("بيانات الدخول غير صحيحة")

def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 مرحباً، {u['name']}")
    st.caption(f"الدور: {u['role']} | القسم: {u['dept']}")
    
    st.write("---")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم طلب إجازة"):
            st.session_state['service'] = 'leave'
            st.session_state['page'] = 'form'
            st.rerun()  # <--- تم التصحيح هنا

    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف والتعويضات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة (قريباً)"):
            st.info("سيتم تفعيلها قريباً")

    with c3:
        st.markdown('<div class="service-card"><h3>📂 ملفي والطلبات</h3></div>', unsafe_allow_html=True)
        if st.button("سجل المعاملات"):
            st.session_state['page'] = 'my_requests'
            st.rerun()  # <--- تم التصحيح هنا

def my_requests_page():
    st.title("📂 سجل معاملاتي")
    if st.button("🔙 عودة"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    u = st.session_state['user']
    supabase = init_supabase()
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs:
        st.info("لا توجد معاملات سابقة.")
        return
        
    for r in reqs:
        with st.container():
            st.markdown(f"### {r['service_type']} ({r.get('sub_type', '-')})")
            
            # حالة الطلب
            final = r.get('final_status', 'Under Review')
            color = "green" if final == "Approved" else "red" if final == "Rejected" else "orange"
            st.markdown(f"**الحالة:** <span style='color:{color};font-weight:bold'>{final}</span>", unsafe_allow_html=True)
            st.caption(f"تاريخ الطلب: {r['created_at'][:10]}")
            st.divider()

# --- 4. الموجه الرئيسي ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'

# القائمة الجانبية
if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        
        if st.button("🏠 الرئيسية"):
            st.session_state['page'] = 'dashboard'
            st.rerun()

        if st.session_state['user']['role'] in ['Manager', 'HR', 'Employee']:
            # كل الموظفين يمكنهم الدخول للموافقات (لأنهم قد يكونون بدلاء)
            if st.button("✅ الموافقات والمهام"):
                st.session_state['page'] = 'approvals'
                st.rerun()
                
        if st.button("🚪 تسجيل خروج"):
            st.session_state.clear()
            st.rerun()

# توجيه الصفحات
if st.session_state['page'] == 'login':
    login_page()
elif st.session_state['page'] == 'dashboard':
    dashboard_page()
elif st.session_state['page'] == 'form':
    # توجيه للنموذج المناسب
    if st.session_state.get('service') == 'leave':
        leave_form_page(st.session_state['user'])
    else:
        st.warning("هذه الخدمة غير مفعلة بعد.")
elif st.session_state['page'] == 'approvals':
    approvals_page(st.session_state['user'])
elif st.session_state['page'] == 'my_requests':
    my_requests_page()
