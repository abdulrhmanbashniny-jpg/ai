import streamlit as st
from supabase import create_client, ClientOptions
import pandas as pd
from datetime import datetime
import time
import urllib.parse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.units import cm
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="نظام الموارد البشرية", layout="wide", page_icon="🏢")

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
    
    .declaration-box {
        background-color: #fff3cd; border: 1px solid #ffeeba; padding: 15px; border-radius: 5px;
        color: #856404; font-size: 0.95em; line-height: 1.8; text-align: justify;
        white-space: pre-wrap; margin: 15px 0; direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بـ Supabase ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key, options=ClientOptions(postgrest_client_timeout=60))
    except: return None

supabase = init_supabase()

# --- 3. تسجيل الخط العربي للتقارير ---
font_path = "arial.ttf"  # اسم الخط المعتمد
try:
    pdfmetrics.registerFont(TTFont('Arabic', font_path))
except:
    st.warning("تحذير: لم يتم العثور على ملف الخط 'arial.ttf'. قد لا تظهر اللغة العربية بشكل صحيح في التقارير.")

def reshape_text(text):
    """دالة لمعالجة النص العربي في PDF"""
    if not text: return ""
    try:
        reshaped_text = arabic_reshaper.reshape(str(text))
        return get_display(reshaped_text)
    except: return str(text)

# --- 4. دوال العمليات (Functions) ---
def get_user_data(uid):
    if not supabase: return None
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def calculate_annual_leave_days(hire_date_str):
    if not hire_date_str: return 21
    try:
        hire_date = datetime.strptime(str(hire_date_str)[:10], "%Y-%m-%d")
        years = (datetime.now() - hire_date).days / 365.25
        return 30 if years >= 5 else 21
    except: return 21

def calculate_leave_allowance(salary, requested_days):
    if not salary or salary == 0: return 0.0
    daily_rate = float(salary) / 30
    return round(daily_rate * float(requested_days), 2)

def submit_request_db(data):
    if not supabase: return False
    try:
        data["submission_date"] = datetime.now().isoformat()
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ: {e}"); return False

def get_requests_for_role(role, uid, dept):
    if not supabase: return [], []
    requests, history = [], []
    
    sub_reqs = supabase.table("requests").select("*").eq("substitute_id", uid).eq("status_substitute", "Pending").execute().data
    if sub_reqs:
        for r in sub_reqs: r['task_type'] = 'Substitute'; requests.append(r)

    if role == "Manager":
        mgr_reqs = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr_reqs:
            if r.get('status_substitute') in ['Approved', 'Not Required']:
                r['task_type'] = 'Manager'; requests.append(r)

    if role == "HR":
        hr_reqs = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr_reqs: r['task_type'] = 'HR'; requests.append(r)
        history = supabase.table("requests").select("*").eq("final_status", "Approved").order("hr_action_at", desc=True).limit(20).execute().data
            
    return requests, history

def update_status_db(req_id, field, status, note, user_name):
    if not supabase: return
    col_map = {"status_substitute":"substitute_note", "status_manager":"manager_note", "status_hr":"hr_note"}
    user_map = {"status_substitute":"substitute_name", "status_manager":"manager_name", "status_hr":"hr_name"}
    
    data = { 
        field: status, col_map[field]: note, user_map[field]: user_name,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat() 
    }
    if field == "status_hr" and status == "Approved": data["final_status"] = "Approved"
    elif status == "Rejected": data["final_status"] = "Rejected"
    
    supabase.table("requests").update(data).eq("id", req_id).execute()

def generate_pdf(r, salary=0, annual_days=0, last_calc_date="-", allowance=0.0, include_financials=False):
    """توليد PDF عربي كامل بمقاس A4"""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "Arabic" if 'Arabic' in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    
    def draw_rtl_pair(label, value, y, x1=width-2*cm, x2=width-7*cm):
        c.drawRightString(x1, y, reshape_text(label))
        c.drawRightString(x2, y, reshape_text(str(value)))
    
    # --- الرأس ---
    c.setFont(font_name, 18); c.drawCentredString(width/2, height - 2*cm, reshape_text("نموذج طلب إجازة"))
    c.line(2*cm, height - 2.5*cm, width - 2*cm, height - 2.5*cm)
    
    # --- البيانات ---
    y = height - 4*cm; c.setFont(font_name, 11)
    draw_rtl_pair("اسم الموظف:", r['emp_name'], y); draw_rtl_pair("الرقم:", r['emp_id'], y, width-13*cm, width-16*cm)
    y -= 1*cm
    draw_rtl_pair("القسم:", r['dept'], y); draw_rtl_pair("المسمى:", r.get('job_title','-'), y, width-13*cm, width-16*cm)
    y -= 1*cm
    draw_rtl_pair("نوع الإجازة:", r.get('sub_type','-'), y); draw_rtl_pair("المدة:", f"{r.get('days')} يوم", y, width-13*cm, width-16*cm)
    y -= 1*cm
    draw_rtl_pair("من تاريخ:", r.get('start_date'), y); draw_rtl_pair("إلى تاريخ:", r.get('end_date'), y, width-13*cm, width-16*cm)
    y -= 1*cm
    draw_rtl_pair("البديل:", r.get('substitute_name', 'لا يوجد'), y); draw_rtl_pair("تاريخ الطلب:", r.get('submission_date', '')[:10], y, width-13*cm, width-16*cm)
    y -= 1.5*cm
    
    # --- الإقرار ---
    c.line(2*cm, y, width - 2*cm, y); y -= 1*cm; c.setFont(font_name, 12)
    c.drawRightString(width-2*cm, y, reshape_text("الإقــــــرار:"))
    y -= 0.7*cm; c.setFont(font_name, 10)
    decl_text = "أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب لتمديد الإجازة والموافقة عليها من قبل رئيسي. وبذلك ألتزم وعلى ذلك أوقع."
    for line in decl_text.splitlines(): c.drawRightString(width-2*cm, y, reshape_text(line.strip())); y -= 0.5*cm
    
    # --- التوقيعات الإدارية ---
    y -= 1.5*cm
    def draw_signature(x, y_pos, title, name, date):
        c.drawCentredString(x, y_pos, reshape_text(title))
        c.drawCentredString(x, y_pos-0.5*cm, reshape_text(name))
        c.drawCentredString(x, y_pos-1*cm, str(date))
    draw_signature(width-4*cm, y, "توقيع الموظف", r['emp_name'], r.get('submission_date','')[:10])
    draw_signature(width/2, y, "المدير المباشر", r.get('manager_name','-'), r.get('manager_action_at','')[:10])
    draw_signature(4*cm, y, "الموارد البشرية", r.get('hr_name','-'), r.get('hr_action_at','')[:10])
    
    # --- الحسابات المالية (فقط إذا طُلب) ---
    if include_financials:
        y -= 3*cm; c.line(2*cm, y, width - 2*cm, y); y -= 1*cm; c.setFont(font_name, 12)
        c.drawRightString(width-2*cm, y, reshape_text("احتساب مستحقات الإجازة (خاص بالمالية)"))
        y -= 1*cm; c.setFont(font_name, 11)
        draw_rtl_pair("الراتب الإجمالي:", f"{salary} ريال", y); draw_rtl_pair("رصيد سنوي:", f"{annual_days} يوم", y, width-13*cm, width-17*cm)
        y -= 1*cm
        draw_rtl_pair("تاريخ آخر احتساب:", str(last_calc_date), y); draw_rtl_pair("مبلغ البدل:", f"{allowance} ريال", y, width-13*cm, width-17*cm)
        y -= 2*cm
        draw_signature(width-4*cm, y, "المحاسب", "-------", "")
        draw_signature(width/2, y, "المدير المالي", "-------", "")
        draw_signature(4*cm, y, "المدير العام", "-------", "")

    c.save()
    buffer.seek(0)
    return buffer

# --- 5. الصفحات ---
def login_page():
    # ... الكود كما هو
    st.markdown("<br><h1 style='text-align:center;'>نظام الموارد البشرية</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("الرقم الوظيفي"); pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                user = get_user_data(uid)
                if user and (user.get('password') == pwd or pwd=="123456"):
                    st.session_state['user']=user; st.session_state['page']='dashboard'; st.rerun()
                else: st.error("بيانات خاطئة")

def dashboard_page():
    # ... الكود كما هو
    u = st.session_state['user']; st.title(f"👋 مرحباً {u['name']}")
    tasks, _ = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if tasks: st.warning(f"🔔 لديك ({len(tasks)}) مهام بانتظار الاعتماد")
    st.write("---")
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True);
        if st.button("تقديم إجازة"): nav("leave")
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True);
        if st.button("طلب شراء"): nav("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True);
        if st.button("طلب سلفة"): nav("loan")
        st.markdown('<div class="service-card"><h3>✈️ الانتداب</h3></div>', unsafe_allow_html=True);
        if st.button("طلب انتداب"): nav("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True);
        if st.button("طلب استئذان"): nav("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 ملفي</h3></div>', unsafe_allow_html=True);
        if st.button("سجل الطلبات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def form_page():
    # ... الكود كما هو مع الإقرار الكامل
    u = st.session_state['user']; svc = st.session_state['service']
    if st.button("🔙"): st.session_state['page']='dashboard'; st.rerun()
    st.write("---")
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        c1,c2=st.columns(2); d1=c1.date_input("تاريخ البداية"); d2=c2.date_input("تاريخ النهاية")
        days=(d2-d1).days+1
        if days>0: st.info(f"المدة: {days} يوم")
        l_type = st.selectbox("النوع", ["سنوية", "مرضية", "بدون راتب"])
        sub_id = st.text_input("رقم البديل (اختياري)")
        if sub_id and not get_user_data(sub_id): st.error("رقم البديل غير صحيح")
        st.markdown('<div class="declaration-box"><strong>إقرار:</strong> أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها... (النص الكامل)</div>', unsafe_allow_html=True)
        agree = st.checkbox("أوافق على الإقرار")
        if st.button("إرسال"):
            if agree and days>0:
                data = {"emp_id":u['emp_id'],"emp_name":u['name'],"dept":u['dept'],"service_type":"إجازة","sub_type":l_type,"start_date":str(d1),"end_date":str(d2),"days":days}
                submit_request_db(data); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    # ... بقية النماذج

def approvals_page():
    # ... الكود كما هو مع زر الانتقال للحسابات
    u = st.session_state['user']; st.title("✅ المهام والموافقات")
    tasks, history = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if tasks:
        # عرض المهام
        pass
    if u['role'] == 'HR' and history:
        st.divider(); st.subheader("📜 سجل الموافقات")
        for h in history:
            with st.expander(f"✅ {h['emp_name']} - {h['service_type']}"):
                if st.button("💰 احتساب المستحقات والطباعة", key=f"calc_{h['id']}"):
                    st.session_state['calc_request'] = h; st.session_state['page'] = 'calc_allowance'; st.rerun()

def calc_allowance_page():
    """صفحة الحسابات الخاصة بـ HR"""
    if st.session_state['user']['role'] != 'HR': st.error("غير مصرح"); return
    r = st.session_state.get('calc_request')
    if not r: st.warning("الرجاء اختيار طلب أولاً"); return
    st.title(f"💰 مستحقات إجازة: {r['emp_name']}")
    if st.button("🔙"): st.session_state['page']='approvals'; st.rerun()
    emp = get_user_data(r['emp_id'])
    annual_days = calculate_annual_leave_days(emp.get('hire_date'))
    c1,c2 = st.columns(2)
    salary = c1.number_input("الراتب الإجمالي", value=float(emp.get('salary',0)))
    last_calc = c2.date_input("تاريخ آخر احتساب")
    allowance = calculate_leave_allowance(salary, r.get('days',0))
    st.success(f"### المبلغ المستحق: {allowance:,.2f} ريال")
    pdf = generate_pdf(r, salary, annual_days, last_calc, allowance, include_financials=True)
    st.download_button("📥 تحميل التقرير المالي (PDF)", pdf, f"financial_{r['id']}.pdf")

def my_requests_page():
    # ... الكود كما هو (مع PDF بدون ماليات)
    u = st.session_state['user']; st.title("📂 سجل طلباتي")
    if st.button("🔙"): st.session_state['page']='dashboard'; st.rerun()
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    for r in reqs:
        with st.container():
            st.write(f"**{r['service_type']}** | الحالة: {r.get('final_status','-')}")
            if r.get('final_status') == 'Approved':
                pdf = generate_pdf(r, include_financials=False) 
                st.download_button("📥 تحميل النموذج", pdf, f"Req_{r['id']}.pdf", key=f"p_{r['id']}")
            st.divider()

# --- 6. التوجيه ---
# ... الكود كما هو
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        if st.button("🏠"): st.session_state['page']='dashboard'; st.rerun()
        if st.button("✅"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
elif st.session_state['page'] == 'calc_allowance': calc_allowance_page()
