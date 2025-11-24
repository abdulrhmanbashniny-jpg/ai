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
        st.error(f"خطأ في إعداد الاتصال بـ Supabase: {e}")
        return None

supabase = init_supabase()

# ==============================
# 3) إعداد الخط العربي لـ PDF
# ==============================
font_path = "arial.ttf"

try:
    pdfmetrics.registerFont(TTFont('Arabic', font_path))
except Exception:
    st.warning("تحذير: لم يتم العثور على ملف الخط 'arial.ttf'. قد لا تظهر العربية بشكل مثالي في الـ PDF.")

def reshape_text(text: str) -> str:
    """معالجة النص العربي ليظهر متصلاً وباتجاه صحيح في PDF"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)

# ==============================
# 4) دوال المساعدة (البيانات والمنطق)
# ==============================
def get_user_data(emp_id: str):
    if not supabase:
        return None
    res = supabase.table("employees").select("*").eq("emp_id", emp_id).execute()
    if res.data:
        return res.data[0]
    return None

def calculate_annual_leave_days(hire_date_str):
    """تحديد هل الاستحقاق 21 أو 30 يوماً حسب سنوات الخدمة."""
    if not hire_date_str:
        return 21
    try:
        hire_date = datetime.strptime(str(hire_date_str)[:10], "%Y-%m-%d")
        years = (datetime.now() - hire_date).days / 365.25
        return 30 if years >= 5 else 21
    except Exception:
        return 21

def calculate_leave_allowance(salary: float, requested_days: float) -> float:
    """حساب مبلغ بدل الإجازة: (راتب شهر / 30) × أيام الإجازة."""
    if not salary or salary <= 0:
        return 0.0
    daily_rate = float(salary) / 30.0
    return round(daily_rate * float(requested_days), 2)

def submit_request_db(data: dict) -> bool:
    if not supabase:
        return False
    try:
        data["submission_date"] = datetime.now().isoformat()
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"فشل حفظ الطلب في قاعدة البيانات: {e}")
        return False

def get_requests_for_role(role: str, emp_id: str, dept: str):
    """إرجاع (tasks, history) حسب دور المستخدم."""
    if not supabase:
        return [], []
    tasks = []
    history = []

    # مهام البديل
    sub = supabase.table("requests").select("*").eq("substitute_id", emp_id).eq("status_substitute", "Pending").execute().data
    for r in sub or []:
        r["task_type"] = "Substitute"
        tasks.append(r)

    # مهام المدير
    if role == "Manager":
        mgr = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr or []:
            if r.get("status_substitute") in ["Approved", "Not Required"]:
                r["task_type"] = "Manager"
                tasks.append(r)

    # مهام HR
    if role == "HR":
        hr = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr or []:
            r["task_type"] = "HR"
            tasks.append(r)
        history = supabase.table("requests").select("*").eq("final_status", "Approved").order("hr_action_at", desc=True).limit(50).execute().data

    return tasks, history

def update_status_db(req_id: int, field: str, status: str, note: str, user_name: str):
    """تحديث حالة الطلب (بديل / مدير / HR) مع توثيق الاسم والتاريخ."""
    if not supabase:
        return
    col_map = {
        "status_substitute": "substitute_note",
        "status_manager": "manager_note",
        "status_hr": "hr_note",
    }
    user_map = {
        "status_substitute": "substitute_name",
        "status_manager": "manager_name",
        "status_hr": "hr_name",
    }
    data = {
        field: status,
        col_map[field]: note,
        user_map[field]: user_name,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat(),
    }
    if field == "status_hr" and status == "Approved":
        data["final_status"] = "Approved"
    elif status == "Rejected":
        data["final_status"] = "Rejected"

    supabase.table("requests").update(data).eq("id", req_id).execute()

# ==============================
# 5) دالة إنشاء PDF منسق
# ==============================
def generate_pdf(r: dict, salary=0.0, annual_days=0, last_calc_date="-", allowance=0.0, include_financials=False):
    """إنشاء PDF عربي منسق بمقاس A4"""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "Arabic" if "Arabic" in pdfmetrics.getRegisteredFontNames() else "Helvetica"

    def draw_rtl(text, x, y):
        c.drawRightString(x, y, reshape_text(text))

    def draw_rtl_pair(label, value, y, x_label, x_value):
        draw_rtl(label, x_label, y)
        draw_rtl(str(value), x_value, y)

    def draw_paragraph(text, x_right, y_start, max_chars=70, line_height=0.5 * cm):
        words = reshape_text(text).split()
        line = ""
        y = y_start
        for w in words:
            if len(line) + len(w) + 1 > max_chars:
                c.drawRightString(x_right, y, line)
                y -= line_height
                line = w
            else:
                line = (line + " " + w) if line else w
        if line:
            c.drawRightString(x_right, y, line)
            y -= line_height
        return y

    # العنوان
    c.setFont(font_name, 18)
    c.drawCentredString(width / 2, height - 2 * cm, reshape_text("نموذج طلب إجازة"))
    c.line(2 * cm, height - 2.4 * cm, width - 2 * cm, height - 2.4 * cm)

    # إطار بيانات الموظف
    box_top = height - 3 * cm
    box_height = 5 * cm
    c.rect(2 * cm, box_top - box_height, width - 4 * cm, box_height)

    y = box_top - 0.8 * cm
    c.setFont(font_name, 11)

    draw_rtl_pair("اسم الموظف:", r["emp_name"], y, width - 2.5 * cm, width - 8.5 * cm)
    draw_rtl_pair("الرقم الوظيفي:", r["emp_id"], y, width - 10.5 * cm, width - 15 * cm)
    y -= 0.9 * cm

    draw_rtl_pair("القسم:", r["dept"], y, width - 2.5 * cm, width - 8.5 * cm)
    draw_rtl_pair("المسمى الوظيفي:", r.get("job_title", "-"), y, width - 10.5 * cm, width - 15 * cm)
    y -= 0.9 * cm

    draw_rtl_pair("نوع الإجازة:", r.get("sub_type", "-"), y, width - 2.5 * cm, width - 8.5 * cm)
    draw_rtl_pair("عدد الأيام:", f"{r.get('days', 0)} يوم", y, width - 10.5 * cm, width - 15 * cm)
    y -= 0.9 * cm

    draw_rtl_pair("من تاريخ:", r.get("start_date", ""), y, width - 2.5 * cm, width - 8.5 * cm)
    draw_rtl_pair("إلى تاريخ:", r.get("end_date", ""), y, width - 10.5 * cm, width - 15 * cm)
    y -= 0.9 * cm

    draw_rtl_pair("الموظف البديل:", r.get("substitute_name", "لا يوجد"), y, width - 2.5 * cm, width - 8.5 * cm)
    draw_rtl_pair("تاريخ تقديم المعاملة:", r.get("submission_date", "")[:10], y, width - 10.5 * cm, width - 15 * cm)

    # الإقرار
    y = box_top - box_height - 1.3 * cm
    c.line(2 * cm, y, width - 2 * cm, y)
    y -= 0.8 * cm
    c.setFont(font_name, 12)
    draw_rtl("الإقــــــرار:", width - 2 * cm, y)
    y -= 0.7 * cm
    c.setFont(font_name, 10)

    declaration_text = "أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب رسمي لتمديد الإجازة والموافقة عليها من قبل رئيسي المباشر، كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وأنني ألتزم بجميع ما ورد أعلاه وعلى ذلك أوقع."
    y = draw_paragraph(declaration_text, width - 2 * cm, y)

    # التوقيعات الإدارية
    y -= 1.3 * cm
    c.setFont(font_name, 11)
    x_emp = width - 4 * cm
    x_mgr = width / 2
    x_hr = 4 * cm

    draw_rtl("توقيع الموظف", x_emp, y)
    draw_rtl("المدير المباشر", x_mgr, y)
    draw_rtl("الموارد البشرية", x_hr, y)
    y -= 0.8 * cm

    draw_rtl(r["emp_name"], x_emp, y)
    draw_rtl(r.get("manager_name", "-"), x_mgr, y)
    draw_rtl(r.get("hr_name", "-"), x_hr, y)
    y -= 0.6 * cm

    draw_rtl(r.get("submission_date", "")[:10], x_emp, y)
    draw_rtl(r.get("manager_action_at", "")[:10], x_mgr, y)
    draw_rtl(r.get("hr_action_at", "")[:10], x_hr, y)

    # قسم الحسابات المالية
    if include_financials:
        y -= 2 * cm
        c.line(2 * cm, y, width - 2 * cm, y)
        y -= 0.8 * cm
        c.setFont(font_name, 12)
        draw_rtl("تفاصيل حساب مبلغ بدل الإجازة", width - 2 * cm, y)
        y -= 1 * cm
        c.setFont(font_name, 11)

        draw_rtl_pair("الراتب الإجمالي:", f"{salary} ريال", y, width - 2.5 * cm, width - 9 * cm)
        y -= 0.7 * cm
        draw_rtl_pair("عدد أيام الإجازة السنوية:", f"{annual_days} يوم", y, width - 2.5 * cm, width - 9 * cm)
        y -= 0.7 * cm
        draw_rtl_pair("أيام الإجازة المستحقة:", f"{r.get('days', 0)} يوم", y, width - 2.5 * cm, width - 9 * cm)
        y -= 0.7 * cm
        draw_rtl_pair("تاريخ آخر احتساب:", str(last_calc_date), y, width - 2.5 * cm, width - 9 * cm)
        y -= 0.7 * cm
        draw_rtl_pair("مبلغ بدل الإجازة:", f"{allowance} ريال", y, width - 2.5 * cm, width - 9 * cm)
        y -= 1.5 * cm

        x_acc = width - 4 * cm
        x_fin = width / 2
        x_gm = 4 * cm

        draw_rtl("المحاسب", x_acc, y)
        draw_rtl("المدير المالي", x_fin, y)
        draw_rtl("المدير العام", x_gm, y)
        y -= 0.8 * cm
        c.drawString(x_acc - 2 * cm, y, "____________")
        c.drawString(x_fin - 2 * cm, y, "____________")
        c.drawString(x_gm - 2 * cm, y, "____________")

    c.save()
    buffer.seek(0)
    return buffer

# ==============================
# 6) صفحات الواجهة
# ==============================
def login_page():
    st.markdown("<br><h1 style='text-align:center;'>نظام الموارد البشرية</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login"):
            emp_id = st.text_input("الرقم الوظيفي")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                user = get_user_data(emp_id)
                if user and (user.get("password") == pwd or pwd == "123456"):
                    st.session_state["user"] = user
                    st.session_state["page"] = "dashboard"
                    st.rerun()
                else:
                    st.error("بيانات الدخول غير صحيحة")

def dashboard_page():
    u = st.session_state["user"]
    st.title(f"👋 مرحباً {u['name']}")
    tasks, _ = get_requests_for_role(u["role"], u["emp_id"], u["dept"])
    if tasks:
        st.warning(f"🔔 لديك ({len(tasks)}) مهام بانتظار الاعتماد")
    st.write("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم إجازة"):
            nav("leave")
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"):
            nav("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"):
            nav("loan")
        st.markdown('<div class="service-card"><h3>✈️ الانتداب</h3></div>', unsafe_allow_html=True)
        if st.button("طلب انتداب"):
            nav("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("طلب استئذان"):
            nav("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 ملفي</h3></div>', unsafe_allow_html=True)
        if st.button("سجل الطلبات"):
            st.session_state["page"] = "my_requests"
            st.rerun()

def nav(service: str):
    st.session_state["service"] = service
    st.session_state["page"] = "form"
    st.rerun()

def form_page():
    u = st.session_state["user"]
    svc = st.session_state.get("service")
    if st.button("🔙 العودة للرئيسية"):
        st.session_state["page"] = "dashboard"
        st.rerun()
    st.write("---")

    if svc == "leave":
        st.header("🌴 طلب إجازة")
        c1, c2 = st.columns(2)
        d1 = c1.date_input("تاريخ البداية", datetime.today())
        d2 = c2.date_input("تاريخ النهاية", datetime.today())
        days = (d2 - d1).days + 1
        if days > 0:
            st.info(f"المدة: {days} يوم")

        l_type = st.selectbox("نوع الإجازة", ["سنوية", "مرضية", "بدون راتب", "اضطرارية"])
        sub_id = st.text_input("رقم الموظف البديل (اختياري)")
        sub_name = None
        if sub_id:
            su = get_user_data(sub_id)
            if su:
                st.success(f"تم اختيار البديل: {su['name']}")
                sub_name = su["name"]
            else:
                st.error("رقم الموظف البديل غير صحيح")

        declaration_html = """<div class="declaration-box">
<strong>(( إقرار وتعهــد ))</strong><br>
أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب رسمي لتمديد الإجازة والموافقة عليها من قبل رئيسي المباشر، كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وأنني ألتزم بجميع ما ورد أعلاه وعلى ذلك أوقع.
</div>"""
        st.markdown(declaration_html, unsafe_allow_html=True)
        agree = st.checkbox("أوافق على الإقرار")

        if st.button("إرسال الطلب"):
            if not agree:
                st.error("يجب الموافقة على الإقرار قبل الإرسال")
            elif days <= 0:
                st.error("تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
            else:
                data = {
                    "emp_id": u["emp_id"],
                    "emp_name": u["name"],
                    "dept": u["dept"],
                    "job_title": u.get("job_title", "-"),
                    "phone": u.get("phone", ""),
                    "service_type": "إجازة",
                    "sub_type": l_type,
                    "start_date": str(d1),
                    "end_date": str(d2),
                    "days": days,
                    "substitute_id": sub_id or None,
                    "substitute_name": sub_name,
                    "status_substitute": "Pending" if sub_id else "Not Required",
                    "declaration_agreed": True,
                }
                if submit_request_db(data):
                    st.success("تم إرسال طلب الإجازة بنجاح")
                    time.sleep(1)
                    st.session_state["page"] = "dashboard"
                    st.rerun()

    elif svc == "loan":
        st.header("💰 طلب سلفة")
        amt = st.number_input("المبلغ المطلوب (ريال)", min_value=0.0, step=100.0)
        reason = st.text_area("سبب طلب السلفة")
        if st.button("إرسال"):
            data = {
                "emp_id": u["emp_id"],
                "emp_name": u["name"],
                "dept": u["dept"],
                "phone": u.get("phone", ""),
                "service_type": "سلفة",
                "amount": amt,
                "details": reason,
            }
            if submit_request_db(data):
                st.success("تم إرسال طلب السلفة")
                time.sleep(1)
                st.session_state["page"] = "dashboard"
                st.rerun()

    elif svc == "purchase":
        st.header("🛒 طلب شراء")
        item = st.text_input("الصنف")
        reason = st.text_area("السبب")
        if st.button("إرسال"):
            data = {
                "emp_id": u["emp_id"],
                "emp_name": u["name"],
                "dept": u["dept"],
                "phone": u.get("phone", ""),
                "service_type": "مشتريات",
                "details": f"{item} - {reason}",
            }
            if submit_request_db(data):
                st.success("تم إرسال طلب الشراء")
                time.sleep(1)
                st.session_state["page"] = "dashboard"
                st.rerun()

    elif svc == "travel":
        st.header("✈️ طلب انتداب")
        dst = st.text_input("الوجهة")
        reason = st.text_area("الهدف من الانتداب")
        if st.button("إرسال"):
            data = {
                "emp_id": u["emp_id"],
                "emp_name": u["name"],
                "dept": u["dept"],
                "phone": u.get("phone", ""),
                "service_type": "انتداب",
                "details": f"{dst} - {reason}",
            }
            if submit_request_db(data):
                st.success("تم إرسال طلب الانتداب")
                time.sleep(1)
                st.session_state["page"] = "dashboard"
                st.rerun()

    elif svc == "perm":
        st.header("⏱️ طلب استئذان")
        d = st.date_input("التاريخ")
        t = st.time_input("الوقت")
        reason = st.text_area("سبب الاستئذان")
        if st.button("إرسال"):
            data = {
                "emp_id": u["emp_id"],
                "emp_name": u["name"],
                "dept": u["dept"],
                "phone": u.get("phone", ""),
                "service_type": "استئذان",
                "start_date": str(d),
                "details": f"{t} - {reason}",
            }
            if submit_request_db(data):
                st.success("تم إرسال طلب الاستئذان")
                time.sleep(1)
                st.session_state["page"] = "dashboard"
                st.rerun()

def approvals_page():
    u = st.session_state["user"]
    st.title("✅ المهام والموافقات")
    tasks, history = get_requests_for_role(u["role"], u["emp_id"], u["dept"])

    if tasks:
        st.subheader("📌 طلبات تحتاج إلى إجراء")
        for r in tasks:
            task_type = r.get("task_type", "Manager")
            label = "موافقة بديل" if task_type == "Substitute" else "موافقة مدير" if task_type == "Manager" else "موافقة HR"
            with st.expander(f"[{label}] {r['emp_name']} - {r['service_type']}", expanded=True):
                st.write(f"النوع: {r.get('sub_type','-')}")
                st.write(f"الفترة: {r.get('start_date')} ➜ {r.get('end_date')} ({r.get('days','-')} يوم)")
                st.write(f"رقم الجوال: {r.get('phone','-')}")
                note = st.text_input("ملاحظات", key=f"note_{r['id']}")
                c1, c2 = st.columns(2)
                if c1.button("✅ موافقة", key=f"ok_{r['id']}"):
                    field = "status_substitute" if task_type == "Substitute" else "status_manager" if task_type == "Manager" else "status_hr"
                    update_status_db(r["id"], field, "Approved", note, u["name"])
                    st.success("تم الاعتماد")
                    time.sleep(1)
                    st.rerun()
                if c2.button("❌ رفض", key=f"no_{r['id']}"):
                    field = "status_substitute" if task_type == "Substitute" else "status_manager" if task_type == "Manager" else "status_hr"
                    update_status_db(r["id"], field, "Rejected", note, u["name"])
                    st.rerun()
    else:
        st.info("لا توجد مهام حالياً")

    if u["role"] == "HR" and history:
        st.divider()
        st.subheader("📜 سجل الموافقات السابقة (HR)")
        for h in history:
            with st.expander(f"✅ {h['emp_name']} - {h['service_type']} ({h.get('hr_action_at','')[:10]})"):
                st.write(f"رقم الطلب: {h['id']}")
                st.write(f"نوع الإجازة: {h.get('sub_type','-')}")
                st.write(f"الفترة: {h.get('start_date')} ➜ {h.get('end_date')} ({h.get('days','-')} يوم)")
                st.write(f"رقم الجوال: {h.get('phone','-')}")

                phone = h.get("phone", "").replace("0", "966", 1)
                final_date = h.get("hr_action_at", datetime.now().isoformat())[:10]
                msg = f"تم اعتماد طلب الإجازة رقم: {h['id']}\nنوع الإجازة: {h.get('sub_type','-')}\nتاريخ البداية: {h.get('start_date')}\nتاريخ النهاية: {h.get('end_date')}\nتاريخ التعميد الأخير: {final_date}"
                wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                st.markdown(f"<a href='{wa_link}' target='_blank'><button style='background:#25D366;color:white;border:none;padding:8px 15px;border-radius:5px;'>📲 إرسال واتساب</button></a>", unsafe_allow_html=True)

                if h["service_type"] == "إجازة":
                    if st.button("💰 مستحقات الإجازة وطباعة", key=f"calc_{h['id']}"):
                        st.session_state["calc_request"] = h
                        st.session_state["page"] = "calc_allowance"
                        st.rerun()

def calc_allowance_page():
    user = st.session_state.get("user")
    if not user or user.get("role") != "HR":
        st.error("هذه الصفحة مخصصة لقسم الموارد البشرية فقط")
        return

    r = st.session_state.get("calc_request")
    if not r:
        st.warning("لم يتم اختيار طلب. الرجاء العودة لسجل الموافقات واختيار طلب.")
        return

    st.title(f"💰 مستحقات إجازة: {r['emp_name']} ({r['emp_id']})")
    if st.button("🔙 عودة إلى المهام"):
        st.session_state["page"] = "approvals"
        st.rerun()

    st.write("---")

    emp = get_user_data(r["emp_id"])
    hire_date = emp.get("hire_date") if emp else None
    auto_annual_days = calculate_annual_leave_days(hire_date)
    base_salary = float(emp.get("salary", 0) or 0)

    st.info(f"تاريخ المباشرة: {hire_date} | الاستحقاق السنوي (محسوب): {auto_annual_days} يوم")

    col1, col2 = st.columns(2)
    salary = col1.number_input("الراتب الإجمالي (ريال)", value=base_salary, step=100.0, format="%.2f")
    annual_days = col2.number_input("عدد أيام الإجازة السنوية", value=float(auto_annual_days), step=1.0, format="%.0f", help="حسب النظام (21 أو 30) ويمكن تعديله عند الحاجة")

    requested_days = st.number_input("أيام الإجازة المستحقة (من الطلب)", value=float(r.get("days", 0)), step=1.0, format="%.0f")
    last_calc_date = st.date_input("تاريخ آخر احتساب", value=datetime.today())

    allowance = calculate_leave_allowance(salary, requested_days)

    st.success(f"مبلغ بدل الإجازة المحسوب: **{allowance:,.2f} ريال**")

    st.write("---")

    if st.button("📥 تحميل تقرير بدل الإجازة (PDF)", type="primary"):
        pdf_data = generate_pdf(r, salary=salary, annual_days=int(annual_days), last_calc_date=last_calc_date, allowance=allowance, include_financials=True)
        st.download_button(label="📥 اضغط هنا لتحميل الملف", data=pdf_data, file_name=f"Leave_Allowance_{r['id']}.pdf", mime="application/pdf")

def my_requests_page():
    u = st.session_state["user"]
    st.title("📂 سجل طلباتي")
    if st.button("🔙 العودة للرئيسية"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    if not supabase:
        st.error("لا يمكن الاتصال بقاعدة البيانات حالياً")
        return

    reqs = supabase.table("requests").select("*").eq("emp_id", u["emp_id"]).order("created_at", desc=True).execute().data

    if not reqs:
        st.info("لا توجد طلبات حتى الآن")
        return

    for r in reqs:
        with st.container():
            st.write(f"**{r['service_type']}** ({r.get('sub_type','-')}) | الحالة: {r.get('final_status','تحت الإجراء')}")
            st.caption(f"تاريخ التقديم: {r.get('submission_date','')[:10]}")

            if r.get("final_status") == "Approved" and r["service_type"] == "إجازة":
                pdf = generate_pdf(r, include_financials=False)
                st.download_button("📥 تحميل نموذج طلب الإجازة (PDF)", pdf, file_name=f"Leave_Request_{r['id']}.pdf", mime="application/pdf", key=f"pdf_{r['id']}")
            st.divider()

# ==============================
# 7) توجيه الصفحات
# ==============================
if "user" not in st.session_state:
    st.session_state["user"] = None
if "page" not in st.session_state:
    st.session_state["page"] = "login"

if st.session_state["user"]:
    with st.sidebar:
        st.header(st.session_state["user"]["name"])
        st.caption(f"الدور: {st.session_state['user'].get('role','-')}")
        if st.button("🏠 الرئيسية"):
            st.session_state["page"] = "dashboard"
            st.rerun()
        if st.button("✅ المهام والموافقات"):
            st.session_state["page"] = "approvals"
            st.rerun()
        if st.button("🚪 تسجيل خروج"):
            st.session_state.clear()
            st.rerun()

if st.session_state["page"] == "login":
    login_page()
elif st.session_state["page"] == "dashboard":
    dashboard_page()
elif st.session_state["page"] == "form":
    form_page()
elif st.session_state["page"] == "approvals":
    approvals_page()
elif st.session_state["page"] == "my_requests":
    my_requests_page()
elif st.session_state["page"] == "calc_allowance":
    calc_allowance_page()
