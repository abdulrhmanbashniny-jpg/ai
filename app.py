import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="HR Enterprise System", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تحسينات التصميم */
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; cursor: pointer;
    }
    .service-card:hover { transform: translateY(-5px); border-color: #2ecc71; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: 600; }
    
    /* تنسيق نموذج الطباعة */
    @media print {
        .no-print { display: none; }
        .print-only { display: block; }
    }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بـ Supabase ---
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# --- 3. دوال البيانات (Database Functions) ---

def get_employees_list():
    """جلب قائمة الموظفين لاختيار البديل"""
    res = supabase.table("employees").select("emp_id, name, job_title").execute()
    return pd.DataFrame(res.data)

def get_user_data(uid):
    """جلب بيانات الموظف عند الدخول"""
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def submit_request_db(data):
    """حفظ الطلب في Supabase"""
    try:
        res = supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ قاعدة البيانات: {e}")
        return False

def get_requests_for_role(role, uid, dept):
    """جلب الطلبات حسب الصلاحية"""
    # 1. الموظف يرى طلباته
    if role == "Employee":
        return supabase.table("requests").select("*").eq("emp_id", uid).execute().data
    
    # 2. البديل يرى الطلبات الموجهة له
    # (سنضيف منطقاً لدمجها، هنا مثال للمدير والـ HR)
    
    if role == "Manager":
        # المدير يرى طلبات قسمه التي تنتظر موافقته
        return supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
    
    if role == "HR":
        # الـ HR يرى ما وافق عليه المدير
        return supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        
    return []

def update_status_db(req_id, field, status, note, user_name):
    """تحديث الحالة"""
    data = {
        field: status,
        f"{field.replace('status_', '')}_note": note,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat()
    }
    # إذا وافق الـ HR، يصبح الطلب مقبولاً نهائياً
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
            uid = st.text_input("رقم الموظف (جرب 1011 أو 1001)")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user_data(uid)
                if user and user['password'] == pwd:
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else:
                    st.error("بيانات خاطئة (جرب 1011 / 123456)")

# --- 5. الصفحات ---

def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 مرحباً، {u['name']}")
    
    # إشعارات المهام
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
    
    # نموذج الإجازة المتطور
    if svc == 'leave':
        st.header("🌴 نموذج طلب إجازة")
        
        # جلب الموظفين للبديل
        emps_df = get_employees_list()
        # قائمة البدلاء (نستثني الموظف نفسه)
        subs_list = emps_df[emps_df['emp_id'] != u['emp_id']]
        sub_options = {f"{r['name']} ({r['job_title']})": r['emp_id'] for i, r in subs_list.iterrows()}
        
        with st.form("leave_form"):
            # 1. البيانات الشخصية (للعرض فقط)
            c1, c2, c3 = st.columns(3)
            c1.text_input("الاسم", u['name'], disabled=True)
            c2.text_input("القسم", u['dept'], disabled=True)
            c3.text_input("الجوال", u['phone'], disabled=True)
            
            st.divider()
            
            # 2. تفاصيل الإجازة
            col_type, col_sub = st.columns(2)
            l_type = col_type.selectbox("نوع الإجازة", ["سنوية (Yearly)", "مرضية (Sick)", "اضطرارية (Emergency)"])
            
            d1, d2 = st.columns(2)
            start_d = d1.date_input("تاريخ البداية")
            end_d = d2.date_input("تاريخ النهاية")
            
            # حساب المدة تلقائياً
            days_diff = (end_d - start_d).days + 1
            st.info(f"📅 مدة الإجازة: {days_diff} أيام")
            
            # الموظف البديل
            sub_name = st.selectbox("الموظف البديل (اختياري)", ["-- لا يوجد --"] + list(sub_options.keys()))
            sub_id = sub_options[sub_name] if sub_name != "-- لا يوجد --" else None
            
            reason = st.text_area("سبب الإجازة")
            
            # 3. الإقرار
            st.warning("""
            **(( إقــرار ))**
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال فاكس لتمديد الإجازة والموافقة عليها من قبل رئيسي...
            """)
            agree = st.checkbox("أوافق وألتزم بما ورد في الإقرار أعلاه")
            
            if st.form_submit_button("🚀 إرسال الطلب"):
                if not agree:
                    st.error("يجب الموافقة على الإقرار لإرسال الطلب.")
                elif days_diff <= 0:
                    st.error("تاريخ النهاية يجب أن يكون بعد البداية.")
                else:
                    data = {
                        "emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'],
                        "job_title": u['job_title'], "phone": u['phone'], "nationality": u['nationality'],
                        "service_type": "إجازة", "sub_type": l_type, "details": reason,
                        "start_date": str(start_d), "end_date": str(end_d), "days": days_diff,
                        "substitute_id": sub_id, "substitute_name": sub_name if sub_id else None,
                        "status_substitute": "Pending" if sub_id else "Not Required",
                        "declaration_agreed": True
                    }
                    if submit_request_db(data):
                        st.success("تم إرسال الطلب بنجاح!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ اعتماد الطلبات")
    
    reqs = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if not reqs: st.success("لا توجد مهام معلقة."); return
    
    for r in reqs:
        with st.expander(f"{r['service_type']} | {r['emp_name']} ({r['days']} أيام)", expanded=True):
            c1, c2 = st.columns([2,1])
            with c1:
                st.write(f"**النوع:** {r['sub_type']}")
                st.write(f"**التاريخ:** من {r['start_date']} إلى {r['end_date']}")
                if r['substitute_name']: st.info(f"👤 بديل: {r['substitute_name']}")
                st.caption(f"السبب: {r['details']}")
            with c2:
                note = st.text_input("ملاحظة", key=f"n_{r['id']}")
                if st.button("موافقة", key=f"ok_{r['id']}"):
                    field = "status_manager" if u['role']=="Manager" else "status_hr"
                    update_status_db(r['id'], field, "Approved", note, u['name'])
                    st.rerun()

def my_requests_page():
    st.title("📂 طلباتي وسجل الطباعة")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    
    u = st.session_state['user']
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs: st.info("لا توجد طلبات."); return
    
    for r in reqs:
        with st.container():
            col_stat, col_info, col_print = st.columns([1, 3, 1])
            
            # الحالة
            status = r['final_status']
            color = "green" if status=="Approved" else "orange" if status=="Under Review" else "red"
            col_stat.markdown(f"<h3 style='color:{color}'>{status}</h3>", unsafe_allow_html=True)
            
            # المعلومات
            with col_info:
                st.write(f"**{r['service_type']} ({r['sub_type']})** - {r['days']} أيام")
                st.caption(f"بتاريخ: {r['created_at'][:10]}")
            
            # زر الطباعة (يظهر فقط عند الموافقة النهائية)
            with col_print:
                if status == "Approved":
                    if st.button("🖨️ طباعة النموذج", key=f"pr_{r['id']}"):
                        print_view(r)

def print_view(r):
    # صفحة الطباعة بتصميم HTML يشبه الورقي
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
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد... (تمت الموافقة الإلكترونية بتاريخ {r['created_at'][:10]})
        </div>
        <br><br>
        <table style="width:100%; text-align:center;">
            <tr>
                <td><strong>توقيع الموظف</strong><br>تم إلكترونياً</td>
                <td><strong>المدير المباشر</strong><br>{r.get('manager_note','-')}<br>موافق ✅</td>
                <td><strong>الموارد البشرية</strong><br>{r.get('hr_note','-')}<br>موافق ✅</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)
    st.button("إغلاق العرض", key="close_print")

# --- 6. التوجيه ---
if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        if st.session_state['user']['role'] in ['Manager', 'HR']:
             if st.button("✅ الموافقات"): st.session_state['page']='approvals'; st.rerun()
        if st.button("خروج"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
