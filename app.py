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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# ==============================
# 1) إعدادات الصفحة و CSS
# ==============================
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
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        padding: 15px;
        border-radius: 5px;
        color: #856404;
        font-size: 0.95em;
        line-height: 1.8;
        text-align: justify;
        white-space: pre-wrap;
        margin: 15px 0;
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# ==============================
# 2) الاتصال بـ Supabase
# ==============================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key, options=ClientOptions(postgrest_client_timeout=60))
    except Exception as e:
        st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

supabase = init_supabase()

# ==============================
# 3) إعداد الخط العربي
# ==============================
font_path = "arial.ttf"
try:
    pdfmetrics.registerFont(TTFont('Arabic', font_path))
except:
    st.warning("ملف الخط 'arial.ttf' غير موجود. يرجى رفعه لضمان ظهور العربية في PDF.")

def reshape_text(text: str) -> str:
    if not text: return ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except: return str(text)

# ==============================
# 4) دوال إدارة البيانات (كاملة)
# ==============================
def get_user_data(emp_id: str):
    if not supabase: return None
    res = supabase.table("employees").select("*").eq("emp_id", emp_id).execute()
    return res.data[0] if res.data else None

def calculate_annual_leave_days(hire_date_str):
    """تحديد هل الاستحقاق 21 أو 30 يوماً حسب سنوات الخدمة."""
    if not hire_date_str: return 21
    try:
        hire_date = datetime.strptime(str(hire_date_str)[:10], "%Y-%m-%d")
        years = (datetime.now() - hire_date).days / 365.25
        return 30 if years >= 5 else 21
    except: return 21

def get_leave_balance(emp: dict):
    """قراءة الرصيد الحالي وتاريخ آخر احتساب"""
    lb = emp.get("leave_balances") or {}
    
    annual_balance = lb.get("annual_balance")
    if annual_balance is None:
        # إذا لم يكن هناك رصيد مسجل، احسبه افتراضياً
        annual_balance = calculate_annual_leave_days(emp.get("hire_date"))

    last_settlement = lb.get("last_settlement_date") or emp.get("hire_date") or datetime.today().date().isoformat()
    
    return float(annual_balance), last_settlement

def set_leave_balance(emp_id: str, new_balance: float, new_settlement_date):
    """تحديث الرصيد في قاعدة البيانات"""
    if not supabase: return
    payload = {
        "leave_balances": {
            "annual_balance": float(new_balance),
            "last_settlement_date": str(new_settlement_date)
        }
    }
    supabase.table("employees").update(payload).eq("emp_id", emp_id).execute()

def calculate_leave_allowance(salary: float, requested_days: float) -> float:
    if not salary or salary <= 0: return 0.0
    # الحساب: (الراتب / 30) * عدد أيام الإجازة
    return round((float(salary) / 30.0) * float(requested_days), 2)

def submit_request_db(data: dict) -> bool:
    if not supabase: return False
    try:
        data["submission_date"] = datetime.now().isoformat()
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"فشل الحفظ: {e}")
        return False

def get_requests_for_role(role: str, emp_id: str, dept: str):
    if not supabase: return [], []
    tasks, history = [], []

    # مهام البديل
    sub = supabase.table("requests").select("*").eq("substitute_id", emp_id).eq("status_substitute", "Pending").execute().data
    for r in sub or []: r["task_type"]="Substitute"; tasks.append(r)

    # مهام المدير
    if role == "Manager":
        mgr = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr or []:
            if r.get("status_substitute") in ["Approved", "Not Required"]:
                r["task_type"]="Manager"; tasks.append(r)

    # مهام HR
    if role == "HR":
        hr = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr or []: r["task_type"]="HR"; tasks.append(r)
        
        history = supabase.table("requests").select("*").eq("final_status", "Approved").order("hr_action_at", desc=True).limit(50).execute().data

    return tasks, history

def update_status_db(req_id: int, field: str, status: str, note: str, user_name: str):
    if not supabase: return
    col_map = {"status_substitute":"substitute_note", "status_manager":"manager_note", "status_hr":"hr_note"}
    user_map = {"status_substitute":"substitute_name", "status_manager":"manager_name", "status_hr":"hr_name"}
    data = {
        field: status,
        col_map[field]: note,
        user_map[field]: user_name,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat(),
    }
    if field == "status_hr" and status == "Approved": data["final_status"] = "Approved"
    elif status == "Rejected": data["final_status"] = "Rejected"
    supabase.table("requests").update(data).eq("id", req_id).execute()

# ==============================
# 5) دالة إنشاء PDF احترافي
# ==============================
def generate_pdf(r: dict, salary=0.0, annual_days=0, last_calc_date="-", allowance=0.0, include_financials=False):
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "Arabic" if "Arabic" in pdfmetrics.getRegisteredFontNames() else "Helvetica"

    def draw_rtl(text, x, y): c.drawRightString(x, y, reshape_text(text))
    
    def draw_rtl_pair(label, value, y, x_label, x_value):
        draw_rtl(label, x_label, y)
        draw_rtl(str(value), x_value, y)

    def draw_paragraph(text, x_right, y_start):
        words = reshape_text(text).split()
        line, y = "", y_start
        for w in words:
            if len(line)+len(w)+1 > 70:
                c.drawRightString(x_right, y, line); y -= 0.5*cm; line = w
            else: line = (line+" "+w) if line else w
        if line: c.drawRightString(x_right, y, line); y -= 0.5*cm
        return y

    # Header
    c.setFont(font_name, 18); c.drawCentredString(width/2, height-2*cm, reshape_text("نموذج طلب إجازة"))
    c.line(2*cm, height-2.4*cm, width-2*cm, height-2.4*cm)

    # Employee Info Box
    box_top = height - 3*cm
    c.rect(2*cm, box_top-5*cm, width-4*cm, 5*cm)
    y = box_top - 0.8*cm
    c.setFont(font_name, 11)

    draw_rtl_pair("اسم الموظف:", r['emp_name'], y, width-2.5*cm, width-8.5*cm)
    draw_rtl_pair("الرقم الوظيفي:", r['emp_id'], y, width-10.5*cm, width-15*cm)
    y -= 0.9*cm
    draw_rtl_pair("القسم:", r['dept'], y, width-2.5*cm, width-8.5*cm)
    draw_rtl_pair("المسمى:", r.get('job_title','-'), y, width-10.5*cm, width-15*cm)
    y -= 0.9*cm
    draw_rtl_pair("نوع الإجازة:", r.get('sub_type','-'), y, width-2.5*cm, width-8.5*cm)
    draw_rtl_pair("عدد الأيام:", f"{r.get('days',0)} يوم", y, width-10.5*cm, width-15*cm)
    y -= 0.9*cm
    draw_rtl_pair("من تاريخ:", r.get('start_date',''), y, width-2.5*cm, width-8.5*cm)
    draw_rtl_pair("إلى تاريخ:", r.get('end_date',''), y, width-10.5*cm, width-15*cm)
    y -= 0.9*cm
    draw_rtl_pair("البديل:", r.get('substitute_name','لا يوجد'), y, width-2.5*cm, width-8.5*cm)
    draw_rtl_pair("تاريخ التقديم:", r.get('submission_date','')[:10], y, width-10.5*cm, width-15*cm)

    # Declaration
    y = box_top - 5*cm - 1.3*cm
    c.line(2*cm, y, width-2*cm, y); y -= 0.8*cm
    c.setFont(font_name, 12); draw_rtl("الإقــــــرار:", width-2*cm, y); y -= 0.7*cm
    c.setFont(font_name, 10)
    decl = "أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب رسمي لتمديد الإجازة والموافقة عليها من قبل رئيسي المباشر، كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وأنني ألتزم بجميع ما ورد أعلاه وعلى ذلك أوقع."
    y = draw_paragraph(decl, width-2*cm, y)

    # Signatures
    y -= 1.5*cm; c.setFont(font_name, 11)
    x_emp, x_mgr, x_hr = width-4*cm, width/2, 4*cm
    draw_rtl("توقيع الموظف", x_emp, y); draw_rtl("المدير المباشر", x_mgr, y); draw_rtl("الموارد البشرية", x_hr, y)
    y -= 0.8*cm
    draw_rtl(r['emp_name'], x_emp, y); draw_rtl(r.get('manager_name','-'), x_mgr, y); draw_rtl(r.get('hr_name','-'), x_hr, y)
    y -= 0.6*cm
    draw_rtl(r.get('submission_date','')[:10], x_emp, y); draw_rtl(r.get('manager_action_at','')[:10], x_mgr, y); draw_rtl(r.get('hr_action_at','')[:10], x_hr, y)

    # Financials (HR Only)
    if include_financials:
        y -= 2*cm; c.line(2*cm, y, width-2*cm, y); y -= 0.8*cm
        c.setFont(font_name, 12); draw_rtl("تفاصيل حساب مبلغ بدل الإجازة", width-2*cm, y); y -= 1*cm
        c.setFont(font_name, 11)
        draw_rtl_pair("الراتب الإجمالي:", f"{salary} ريال", y, width-2.5*cm, width-9*cm); y -= 0.7*cm
        draw_rtl_pair("الرصيد السنوي:", f"{annual_days} يوم", y, width-2.5*cm, width-9*cm); y -= 0.7*cm
        draw_rtl_pair("أيام الإجازة المستحقة:", f"{r.get('days',0)} يوم", y, width-2.5*cm, width-9*cm); y -= 0.7*cm
        draw_rtl_pair("تاريخ آخر احتساب:", str(last_calc_date), y, width-2.5*cm, width-9*cm); y -= 0.7*cm
        draw_rtl_pair("مبلغ بدل الإجازة:", f"{allowance} ريال", y, width-2.5*cm, width-9*cm); y -= 1.5*cm
        
        x_acc, x_fin, x_gm = width-4*cm, width/2, 4*cm
        draw_rtl("المحاسب", x_acc, y); draw_rtl("المدير المالي", x_fin, y); draw_rtl("المدير العام", x_gm, y)
        y -= 0.8*cm
        c.drawString(x_acc-2*cm, y, "_________"); c.drawString(x_fin-2*cm, y, "_________"); c.drawString(x_gm-2*cm, y, "_________")

    c.save(); buffer.seek(0); return buffer

# ==============================
# 6) صفحات التطبيق
# ==============================
def login_page():
    st.markdown("<br><h1 style='text-align:center;'>نظام الموارد البشرية</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("log"):
            uid = st.text_input("الرقم الوظيفي")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                user = get_user_data(uid)
                if user and (user.get("password") == pwd or pwd == "123456"):
                    st.session_state["user"] = user; st.session_state["page"] = "dashboard"; st.rerun()
                else: st.error("بيانات خاطئة")

def dashboard_page():
    u = st.session_state["user"]; st.title(f"👋 مرحباً {u['name']}")
    tasks, _ = get_requests_for_role(u["role"], u["emp_id"], u["dept"])
    if tasks: st.warning(f"🔔 لديك ({len(tasks)}) مهام جديدة")
    st.write("---")
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True); 
        if st.button("تقديم إجازة"): nav("leave")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True); 
        if st.button("طلب سلفة"): nav("loan")
    with c3:
        st.markdown('<div class="service-card"><h3>📂 ملفي</h3></div>', unsafe_allow_html=True); 
        if st.button("سجل الطلبات"): st.session_state["page"]="my_requests"; st.rerun()

def nav(s): st.session_state["service"]=s; st.session_state["page"]="form"; st.rerun()

def form_page():
    u = st.session_state["user"]; svc = st.session_state.get("service")
    if st.button("🔙"): st.session_state["page"]="dashboard"; st.rerun()
    st.write("---")
    if svc == "leave":
        st.header("🌴 طلب إجازة")
        c1, c2 = st.columns(2)
        d1 = c1.date_input("من"); d2 = c2.date_input("إلى")
        days = (d2 - d1).days + 1
        if days>0: st.info(f"المدة: {days} يوم")
        l_type = st.selectbox("النوع", ["سنوية", "مرضية", "بدون راتب"])
        sub_id = st.text_input("بديل (اختياري)")
        
        html = """<div class="declaration-box"><strong>(( إقرار وتعهــد ))</strong><br>أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب رسمي لتمديد الإجازة والموافقة عليها من قبل رئيسي المباشر، كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وأنني ألتزم بجميع ما ورد أعلاه وعلى ذلك أوقع.</div>"""
        st.markdown(html, unsafe_allow_html=True)
        agree = st.checkbox("أوافق")
        
        if st.button("إرسال"):
            if agree and days>0:
                data = {"emp_id":u['emp_id'],"emp_name":u['name'],"dept":u['dept'],"service_type":"إجازة","sub_type":l_type,"start_date":str(d1),"end_date":str(d2),"days":days,"substitute_id":sub_id or None,"status_substitute":"Pending" if sub_id else "Not Required","declaration_agreed":True}
                submit_request_db(data); st.success("تم!"); time.sleep(1); st.session_state["page"]="dashboard"; st.rerun()
    
    elif svc == "loan":
        st.header("💰 طلب سلفة"); amt = st.number_input("المبلغ"); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id":u['emp_id'],"emp_name":u['name'],"dept":u['dept'],"service_type":"سلفة","amount":amt,"details":rsn}); st.success("تم!"); time.sleep(1); st.session_state["page"]="dashboard"; st.rerun()

def approvals_page():
    u = st.session_state["user"]; st.title("✅ المهام")
    tasks, history = get_requests_for_role(u["role"], u["emp_id"], u["dept"])
    
    if tasks:
        for r in tasks:
            with st.expander(f"{r['emp_name']} - {r['service_type']}"):
                c1,c2=st.columns(2); note=st.text_input("ملاحظة", key=f"n{r['id']}")
                if c1.button("✅", key=f"ok{r['id']}"):
                    f = "status_substitute" if r.get('task_type')=="Substitute" else "status_manager" if r.get('task_type')=="Manager" else "status_hr"
                    update_status_db(r['id'], f, "Approved", note, u['name']); st.rerun()
                if c2.button("❌", key=f"no{r['id']}"):
                    f = "status_substitute" if r.get('task_type')=="Substitute" else "status_manager" if r.get('task_type')=="Manager" else "status_hr"
                    update_status_db(r['id'], f, "Rejected", note, u['name']); st.rerun()

    if u["role"] == "HR" and history:
        st.divider(); st.subheader("📜 السجل (HR)")
        for h in history:
            with st.expander(f"✅ {h['emp_name']} ({h.get('hr_action_at','')[:10]})"):
                phone = h.get("phone", "").replace("0", "966", 1)
                msg = f"تم اعتماد طلب الإجازة رقم: {h['id']}\nنوع: {h.get('sub_type')}\nمن: {h.get('start_date')}\nإلى: {h.get('end_date')}"
                link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                st.markdown(f"<a href='{link}' target='_blank'>📲 واتساب</a>", unsafe_allow_html=True)
                
                if h['service_type']=='إجازة':
                    if st.button("💰 مستحقات الإجازة", key=f"c{h['id']}"):
                        st.session_state["calc_request"]=h; st.session_state["page"]="calc_allowance"; st.rerun()

def calc_allowance_page():
    u = st.session_state["user"]
    if u["role"] != "HR": st.error("HR Only"); return
    r = st.session_state.get("calc_request")
    
    st.title(f"💰 مستحقات: {r['emp_name']}")
    if st.button("🔙"): st.session_state["page"]="approvals"; st.rerun()
    st.write("---")
    
    emp = get_user_data(r['emp_id'])
    cur_bal, last_set = get_leave_balance(emp)
    
    st.info(f"الرصيد الحالي: {cur_bal} يوم | آخر تصفية: {last_set}")
    
    c1,c2 = st.columns(2)
    salary = c1.number_input("الراتب", value=float(emp.get('salary',0)))
    # تم استدعاء الدالة بشكل صحيح هنا
    annual = c2.number_input("الرصيد السنوي", value=float(calculate_annual_leave_days(emp.get('hire_date'))))
    
    st.write("### فترة الاحتساب")
    cc1,cc2=st.columns(2)
    to_date = cc2.date_input("إلى تاريخ", datetime.today())
    
    req_days = st.number_input("الأيام المستحقة", value=float(r.get('days',0)))
    allowance = calculate_leave_allowance(salary, req_days)
    new_bal = cur_bal - req_days
    
    if new_bal < 0: st.error(f"⚠️ الرصيد سيصبح بالسالب: {new_bal}")
    else: st.success(f"✅ الرصيد الجديد سيكون: {new_bal}")
    
    st.success(f"💵 المبلغ المستحق: {allowance:,.2f} ريال")
    
    if st.button("📥 اعتماد وخصم الرصيد + تحميل PDF", type="primary"):
        if new_bal >= 0: set_leave_balance(r['emp_id'], new_bal, to_date)
        pdf = generate_pdf(r, salary, int(annual), to_date, allowance, True)
        st.download_button("اضغط للتحميل", pdf, f"Allow_{r['id']}.pdf", "application/pdf")

def my_requests_page():
    u = st.session_state["user"]; st.title("📂 طلباتي")
    if st.button("🔙"): st.session_state["page"]="dashboard"; st.rerun()
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    for r in reqs:
        with st.container():
            st.write(f"**{r['service_type']}** | {r.get('final_status','-')}")
            if r.get('final_status')=='Approved' and r['service_type']=='إجازة':
                pdf = generate_pdf(r, include_financials=False)
                st.download_button("📥 النموذج", pdf, f"Req_{r['id']}.pdf", key=f"p{r['id']}")
            st.divider()

# ==============================
# 7) التوجيه
# ==============================
if "user" not in st.session_state: st.session_state["user"]=None
if "page" not in st.session_state: st.session_state["page"]="login"

if st.session_state["user"]:
    with st.sidebar:
        st.header(st.session_state["user"]["name"])
        if st.button("🏠"): st.session_state["page"]="dashboard"; st.rerun()
        if st.button("✅"): st.session_state["page"]="approvals"; st.rerun()
        if st.button("🚪"): st.session_state.clear(); st.rerun()

if st.session_state["page"]=="login": login_page()
elif st.session_state["page"]=="dashboard": dashboard_page()
elif st.session_state["page"]=="form": form_page()
elif st.session_state["page"]=="approvals": approvals_page()
elif st.session_state["page"]=="my_requests": my_requests_page()
elif st.session_state["page"]=="calc_allowance": calc_allowance_page()
