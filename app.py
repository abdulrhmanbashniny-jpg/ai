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
        l_type = st.selectbox("نوع الإجازة", ["سنوية (Yearly)", "مرضية (Sick)", "اضطرارية (Emergency)"])
        
        # 3. التواريخ (تفاعلية)
        col_d1, col_d2 = st.columns(2)
        start_d = col_d1.date_input("تاريخ البداية", datetime.today())
        end_d = col_d2.date_input("تاريخ النهاية", datetime.today())
        
        # حساب تلقائي للأيام (يتحدث فوراً عند تغيير التاريخ)
        if end_d >= start_d:
            days_diff = (end_d - start_d).days + 1
            st.success(f"📅 **مدة الإجازة: {days_diff} يوم**")
        else:
            days_diff = 0
            st.error("⚠️ تاريخ النهاية يجب أن يكون بعد البداية أو يساويها.")
        
        # 4. الموظف البديل (إدخال يدوي لرقم الموظف)
        st.write("### الموظف البديل (اختياري)")
        sub_id = st.text_input("أدخل رقم الموظف الوظيفي للبديل (مثال: 1012)")
        sub_name = None
        
        if sub_id and sub_id.strip():
            # التحقق من وجود الموظف
            sub_user = get_user_data(sub_id.strip())
            if sub_user:
                st.info(f"✅ الموظف البديل: **{sub_user['name']}** ({sub_user['job_title']})")
                sub_name = sub_user['name']
            else:
                st.warning("⚠️ رقم الموظف غير موجود في النظام.")
                sub_id = None
        
        # 5. السبب
        reason = st.text_area("سبب الإجازة")
        
        # 6. الإقرار (المحدث)
        st.warning("""
        **(( إقــرار ))**
        
أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال **خطاب** لتمديد الإجازة والموافقة عليها من قبل رئيسي كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة من نظام العمل والعمال وذلك دون الحاجه لإنذاري على عنواني في بلدي وأنني سأقوم بإجازتي في التاريخ المبين أعلاه وبذلك سألتزم وعلى ذلك أوقع.
        """)
        agree = st.checkbox("✅ أوافق وألتزم بما ورد في الإقرار أعلاه")
        
        # 7. زر الإرسال
        if st.button("🚀 إرسال الطلب", type="primary"):
            if not agree:
                st.error("❌ يجب الموافقة على الإقرار لإرسال الطلب.")
            elif days_diff <= 0:
                st.error("❌ تاريخ النهاية يجب أن يكون صحيحاً.")
            else:
                data = {
                    "emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'],
                    "job_title": u['job_title'], "phone": u['phone'], "nationality": u['nationality'],
                    "service_type": "إجازة", "sub_type": l_type, "details": reason,
                    "start_date": str(start_d), "end_date": str(end_d), "days": days_diff,
                    "substitute_id": sub_id if sub_id else None,
                    "substitute_name": sub_name,
                    "status_substitute": "Pending" if sub_id else "Not Required",
                    "declaration_agreed": True
                }
                if submit_request_db(data):
                    st.balloons()
                    st.success("✅ تم إرسال الطلب بنجاح!")
                    time.sleep(2)
                    st.session_state['page']='dashboard'
                    st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ اعتماد الطلبات")
    
    reqs = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if not reqs:
        st.success("🎉 لا توجد مهام معلقة.")
        return
    
    for r in reqs:
        with st.expander(f"{r['service_type']} | {r['emp_name']} ({r['days']} أيام)", expanded=True):
            c1, c2 = st.columns([2,1])
            with c1:
                st.write(f"**النوع:** {r['sub_type']}")
                st.write(f"**التاريخ:** من {r['start_date']} إلى {r['end_date']}")
                if r['substitute_name']:
                    st.info(f"👤 بديل: {r['substitute_name']} (رقم: {r['substitute_id']})")
                st.caption(f"السبب: {r['details']}")
            with c2:
                note = st.text_input("ملاحظة", key=f"n_{r['id']}")
                if st.button("✅ موافقة", key=f"ok_{r['id']}"):
                    field = "status_manager" if u['role']=="Manager" else "status_hr"
                    update_status_db(r['id'], field, "Approved", note, u['name'])
                    st.rerun()
                if st.button("❌ رفض", key=f"no_{r['id']}"):
                    field = "status_manager" if u['role']=="Manager" else "status_hr"
                    update_status_db(r['id'], field, "Rejected", note, u['name'])
                    st.rerun()

def my_requests_page():
    st.title("📂 طلباتي وسجل الطباعة")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    
    u = st.session_state['user']
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs:
        st.info("لا توجد طلبات.")
        return
    
    for r in reqs:
        with st.container():
            col_stat, col_info, col_print = st.columns([1, 3, 1])
            
            status = r['final_status']
            color = "green" if status=="Approved" else "orange" if status=="Under Review" else "red"
            col_stat.markdown(f"<h3 style='color:{color}'>{status}</h3>", unsafe_allow_html=True)
            
            with col_info:
                st.write(f"**{r['service_type']} ({r['sub_type']})** - {r['days']} أيام")
                st.caption(f"بتاريخ: {r['created_at'][:10]}")
            
            with col_print:
                if status == "Approved":
                    if st.button("🖨️ طباعة", key=f"pr_{r['id']}"):
                        print_view(r)

def print_view(r):
    st.markdown(f"""
    <div style="background:white; padding:40px; border:2px solid black; color:black; font-family:Times New Roman;">
        <h2 style="text-align:center; text-decoration:underline;">نموذج طلب إجازة</h2>
        <table style="width:100%; text-align:right; direction:rtl; border-collapse:collapse;" border="1">
            <tr><td style="padding:10px; background:#eee;">اسم الموظف</td><td style="padding:10px;">{r['emp_name']}</td></tr>
            <tr><td style="padding:10px; background:#eee;">الرقم الوظيفي</td><td style="padding:10px;">{r['emp_id']}</td></tr>
            <tr><td style="padding:10px; background:#eee;">القسم</td><td style="padding:10px;">{r['dept']}</td></tr>
            <tr><td style="padding:10px; background:#eee;">الوظيفة</td><td style="padding:10px;">{r['job_title']}</td></tr>
        </table>
        <br>
        <h3>تفاصيل الإجازة:</h3>
        <p><strong>النوع:</strong> {r['sub_type']}</p>
        <p><strong>المدة:</strong> {r['days']} أيام (من {r['start_date']} إلى {r['end_date']})</p>
        <p><strong>الموظف البديل:</strong> {r['substitute_name'] or 'لا يوجد'}</p>
        <br>
        <div style="border:1px dashed black; padding:15px;">
            <strong>إقــرار:</strong><br>
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب لتمديد الإجازة والموافقة عليها من قبل رئيسي...
        </div>
        <br><br>
        <p style="text-align:center;"><strong>تمت الموافقة الإلكترونية ✅</strong></p>
    </div>
    """, unsafe_allow_html=True)

# --- 6. التوجيه ---
if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.rerun()
        if st.session_state['user']['role'] in ['Manager', 'HR']:
            if st.button("✅ الموافقات"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪 خروج"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
