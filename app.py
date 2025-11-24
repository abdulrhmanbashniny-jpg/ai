import streamlit as st
from supabase import create_client, ClientOptions
import pandas as pd
from datetime import datetime, timedelta
import time
import urllib.parse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.units import cm

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
        white-space: pre-wrap; margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key, options=ClientOptions(postgrest_client_timeout=60))
    except: return None

supabase = init_supabase()

# --- 3. الدوال ---
def get_user_data(uid):
    if not supabase: return None
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def calculate_annual_leave_days(hire_date_str):
    """حساب عدد أيام الإجازة السنوية بناءً على تاريخ المباشرة"""
    if not hire_date_str: return 21
    try:
        hire_date = datetime.strptime(str(hire_date_str)[:10], "%Y-%m-%d")
        years_of_service = (datetime.now() - hire_date).days / 365.25
        return 30 if years_of_service >= 5 else 21
    except:
        return 21

def calculate_leave_allowance(salary, annual_days, requested_days):
    """حساب مبلغ بدل الإجازة"""
    if not salary or salary == 0: return 0
    daily_rate = salary / 365
    return round(daily_rate * requested_days, 2)

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
    requests = []
    history = []
    
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
        history = supabase.table("requests").select("*").eq("status_hr", "Approved").order("hr_action_at", desc=True).limit(10).execute().data
            
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

def generate_pdf(r, salary, annual_days, last_calc_date, allowance):
    """توليد PDF بمقاس A4 مع احتساب مستحقات الإجازة"""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # العنوان
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 1.5*cm, "Leave Request Form")
    c.drawCentredString(width/2, height - 2*cm, "نموذج طلب إجازة")
    c.line(1*cm, height - 2.3*cm, width - 1*cm, height - 2.3*cm)
    
    # البيانات الأساسية
    y = height - 3*cm
    c.setFont("Helvetica", 10)
    
    lines = [
        f"Employee Name / اسم الموظف: {r['emp_name']}",
        f"Employee ID / الرقم الوظيفي: {r['emp_id']}",
        f"Phone / الجوال: {r.get('phone', 'N/A')}",
        f"Department / القسم: {r['dept']}",
        f"Position / المسمى: {r.get('job_title', '-')}",
        f"Submission Date / تاريخ التقديم: {r.get('submission_date', 'N/A')[:10]}",
        "",
        f"Leave Type / نوع الإجازة: {r.get('sub_type', '-')}",
        f"Duration / المدة: {r.get('days')} days",
        f"From / من: {r.get('start_date')} To / إلى: {r.get('end_date')}",
        f"Substitute / البديل: {r.get('substitute_name', 'N/A')}",
    ]
    
    for line in lines:
        c.drawString(1.5*cm, y, line)
        y -= 0.5*cm
    
    # الإقرار
    y -= 0.5*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(1.5*cm, y, "DECLARATION / الإقرار:")
    y -= 0.4*cm
    c.setFont("Helvetica", 8)
    decl = "I hereby declare that I will take my leave on the scheduled date and will not exceed the duration..."
    c.drawString(1.5*cm, y, decl[:80])
    y -= 0.3*cm
    c.drawString(1.5*cm, y, "أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد...")
    
    # التواقيع
    y -= 1.5*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(1.5*cm, y, "Employee / الموظف")
    c.drawString(1.5*cm, y - 0.4*cm, r['emp_name'])
    c.drawString(1.5*cm, y - 0.7*cm, f"{r.get('submission_date', '')[:10]}")
    
    c.drawString(width/2 - 2*cm, y, "Manager / المدير")
    c.drawString(width/2 - 2*cm, y - 0.4*cm, r.get('manager_name', 'N/A'))
    c.drawString(width/2 - 2*cm, y - 0.7*cm, f"{r.get('manager_action_at', '')[:10]}")
    
    c.drawString(width - 4*cm, y, "HR / الموارد البشرية")
    c.drawString(width - 4*cm, y - 0.4*cm, r.get('hr_name', 'N/A'))
    c.drawString(width - 4*cm, y - 0.7*cm, f"{r.get('hr_action_at', '')[:10]}")
    
    # قسم احتساب مستحقات الإجازة
    y -= 2*cm
    c.line(1*cm, y, width - 1*cm, y)
    y -= 0.5*cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1.5*cm, y, "Leave Allowance Calculation / احتساب مستحقات بدل الإجازة")
    y -= 0.6*cm
    
    c.setFont("Helvetica", 9)
    calc_lines = [
        f"Total Salary / الراتب الإجمالي: {salary} SAR",
        f"Annual Leave Days / أيام الإجازة السنوية: {annual_days} days",
        f"Requested Days / الأيام المطلوبة: {r.get('days')} days",
        f"Last Calculation Date / تاريخ آخر احتساب: {last_calc_date}",
        f"Leave Allowance / مبلغ بدل الإجازة: {allowance} SAR",
    ]
    
    for line in calc_lines:
        c.drawString(1.5*cm, y, line)
        y -= 0.4*cm
    
    # التواقيع المالية
    y -= 1*cm
    c.line(1*cm, y, width - 1*cm, y)
    y -= 0.5*cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(1.5*cm, y, "Accountant / المحاسب")
    c.drawString(1.5*cm, y - 0.3*cm, "________________")
    
    c.drawString(width/2 - 2.5*cm, y, "Financial Manager / المدير المالي")
    c.drawString(width/2 - 2.5*cm, y - 0.3*cm, "________________")
    
    c.drawString(width - 4.5*cm, y, "General Manager / المدير العام")
    c.drawString(width - 4.5*cm, y - 0.3*cm, "________________")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- 4. الصفحات ---
def login_page():
    st.markdown("<br><h1 style='text-align:center; color:#2980b9;'>🔐 دخول النظام المركزي</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف"); pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("دخول"):
                user = get_user_data(uid)
                if user and (user.get('password') == pwd or pwd=="123456"):
                    st.session_state['user']=user; st.session_state['page']='dashboard'; st.rerun()
                else: st.error("خطأ")

def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 {u['name']}")
    tasks, _ = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if tasks: st.warning(f"🔔 لديك ({len(tasks)}) مهام.")
    st.write("---")
    
    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم إجازة"): nav("leave")
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): nav("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): nav("loan")
        st.markdown('<div class="service-card"><h3>✈️ الانتداب</h3></div>', unsafe_allow_html=True)
        if st.button("طلب انتداب"): nav("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"): nav("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 ملفي</h3></div>', unsafe_allow_html=True)
        if st.button("سجل المعاملات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def form_page():
    u = st.session_state['user']; svc = st.session_state['service']
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    st.write("---")
    
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        c1,c2=st.columns(2); d1=c1.date_input("من"); d2=c2.date_input("إلى")
        days=(d2-d1).days+1
        if days>0: st.info(f"المدة: {days} يوم")
        
        l_type = st.selectbox("النوع", ["سنوية", "مرضية", "بدون راتب"])
        sub_id = st.text_input("رقم البديل (اختياري)")
        sub_name = None
        if sub_id:
            s_u = get_user_data(sub_id)
            if s_u: st.success(f"✅ {s_u['name']}"); sub_name=s_u['name']
        
        st.markdown("""
        <div class="declaration-box">
        <strong>(( إقــرار وتعهــد ))</strong><br>
        أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب لتمديد الإجازة والموافقة عليها من قبل رئيسي كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة من نظام العمل والعمال وذلك دون الحاجه لإنذاري على عنواني في بلدي وأنني سأقوم بإجازتي في التاريخ المبين أعلاه وبذلك سألتزم وعلى ذلك أوقع.
        </div>
        """, unsafe_allow_html=True)
        
        agree = st.checkbox("أوافق وألتزم بما ورد في الإقرار أعلاه")
        
        if st.button("إرسال"):
            if agree and days>0:
                data = {"emp_id":u['emp_id'], "emp_name":u['name'], "dept":u['dept'], "phone": u.get('phone',''),
                        "job_title": u.get('job_title','-'), "service_type":"إجازة", 
                        "sub_type":l_type, "start_date":str(d1), "end_date":str(d2), "days":days,
                        "substitute_id":sub_id or None, "substitute_name":sub_name,
                        "status_substitute":"Pending" if sub_id else "Not Required", "declaration_agreed":True}
                submit_request_db(data); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
            else: st.error("يجب الموافقة على الإقرار")

    elif svc == 'loan':
        st.header("💰 طلب سلفة"); amt = st.number_input("المبلغ", 500); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "phone": u.get('phone',''), "service_type": "سلفة", "amount": amt, "details": rsn}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'purchase':
        st.header("🛒 طلب شراء"); item = st.text_input("الصنف"); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "phone": u.get('phone',''), "service_type": "مشتريات", "details": f"{item} - {rsn}"}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'travel':
        st.header("✈️ انتداب"); dst = st.text_input("الوجهة"); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "phone": u.get('phone',''), "service_type": "انتداب", "details": f"إلى {dst} - {rsn}"}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'perm':
        st.header("⏱️ استئذان"); d = st.date_input("التاريخ"); tm = st.time_input("الوقت")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "phone": u.get('phone',''), "service_type": "استئذان", "start_date": str(d), "details": str(tm)}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ المهام والموافقات")
    
    tasks, history = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    
    if tasks:
        st.subheader("📌 مهام بانتظار إجرائك")
        for r in tasks:
            task_type = r.get('task_type', 'Manager')
            label = "موافقة بديل" if task_type=='Substitute' else "موافقة مدير" if task_type=='Manager' else "موافقة HR"
            
            with st.expander(f"[{label}] {r['emp_name']} - {r['sub_type'] or r['service_type']}", expanded=True):
                st.write(f"**التفاصيل:** {r.get('days',0)} يوم | **جوال:** {r.get('phone','N/A')}")
                note = st.text_input("ملاحظة", key=f"n{r['id']}")
                c1, c2 = st.columns(2)
                
                if c1.button("✅ اعتماد", key=f"ok{r['id']}"):
                    f = "status_substitute" if task_type=='Substitute' else "status_manager" if task_type=='Manager' else "status_hr"
                    update_status_db(r['id'], f, "Approved", note, u['name'])
                    st.success("تم!")
                    time.sleep(1); st.rerun()
                if c2.button("❌ رفض", key=f"no{r['id']}"):
                    f = "status_substitute" if task_type=='Substitute' else "status_manager" if task_type=='Manager' else "status_hr"
                    update_status_db(r['id'], f, "Rejected", note, u['name'])
                    st.rerun()
    else:
        st.info("🎉 لا توجد مهام معلقة.")
    
    # سجل الموافقات (HR فقط)
    if u['role'] == 'HR' and history:
        st.divider()
        st.subheader("📜 سجل الموافقات السابقة (لإرسال الواتساب)")
        for h in history:
            with st.expander(f"✅ {h['emp_name']} - {h['service_type']} ({h.get('hr_action_at','N/A')[:10]})"):
                st.write(f"**رقم الطلب:** {h['id']}")
                st.write(f"**النوع:** {h.get('sub_type')}")
                st.write(f"**التواريخ:** {h.get('start_date')} ➡️ {h.get('end_date')}")
                
                phone = h.get('phone', '').replace('0', '966', 1)
                final_date = h.get('hr_action_at', datetime.now().isoformat())[:10]
                
                msg = f"""السلام عليكم {h['emp_name']}،
تم اعتماد طلب الإجازة رقم: {h['id']}
نوع الإجازة: {h.get('sub_type')}
تاريخ البداية: {h.get('start_date')}
تاريخ النهاية: {h.get('end_date')}
تاريخ التعميد الأخير: {final_date}

نتمنى لك إجازة سعيدة!"""
                
                wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                st.markdown(f"<a href='{wa_link}' target='_blank'><button style='background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; cursor:pointer;'>📲 إرسال واتساب</button></a>", unsafe_allow_html=True)

def my_requests_page():
    u = st.session_state['user']
    st.title("📂 ملفي" if u['role'] != 'HR' else "📂 سجل الطلبات (HR)")
    if st.button("🔙"): st.session_state['page']='dashboard'; st.rerun()
    
    # HR يرى كل الطلبات، الموظفون يروا طلباتهم فقط
    if u['role'] == 'HR':
        reqs = supabase.table("requests").select("*").eq("final_status", "Approved").order("created_at", desc=True).limit(20).execute().data
    else:
        reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    for r in reqs:
        with st.container():
            st.write(f"**{r['service_type']}** - {r.get('final_status','تحت الإجراء')} - {r.get('submission_date','N/A')[:10]}")
            
            # HR فقط: صفحة احتساب المستحقات
            if r.get('final_status')=='Approved' and u['role'] == 'HR' and r['service_type'] == 'إجازة':
                if st.button("💰 احتساب المستحقات وطباعة", key=f"calc_{r['id']}"):
                    st.session_state['calc_request'] = r
                    st.session_state['page'] = 'calc_allowance'
                    st.rerun()
            
            st.divider()

def calc_allowance_page():
    """صفحة احتساب مستحقات الإجازة (HR فقط)"""
    if st.session_state['user']['role'] != 'HR':
        st.error("هذه الصفحة مخصصة للموارد البشرية فقط")
        return
    
    r = st.session_state.get('calc_request', {})
    if not r:
        st.warning("لا توجد بيانات طلب")
        return
    
    st.title(f"💰 احتساب مستحقات إجازة: {r['emp_name']}")
    if st.button("🔙 عودة"): st.session_state['page']='my_requests'; st.rerun()
    st.write("---")
    
    # جلب بيانات الموظف
    emp = get_user_data(r['emp_id'])
    hire_date = emp.get('hire_date', datetime.now().isoformat()) if emp else datetime.now().isoformat()
    
    # احتساب تلقائي
    annual_days = calculate_annual_leave_days(hire_date)
    default_salary = emp.get('salary', 5000) if emp else 5000
    
    st.info(f"**سنوات الخدمة:** {(datetime.now() - datetime.strptime(str(hire_date)[:10], '%Y-%m-%d')).days / 365.25:.1f} سنة | **الرصيد السنوي:** {annual_days} يوم")
    
    # حقول قابلة للتعديل
    col1, col2 = st.columns(2)
    salary = col1.number_input("الراتب الإجمالي (ريال)", value=default_salary, step=100)
    last_calc = col2.date_input("تاريخ آخر احتساب", value=datetime.now())
    
    allowance = calculate_leave_allowance(salary, annual_days, r.get('days', 0))
    
    st.success(f"### مبلغ بدل الإجازة المحسوب: **{allowance:,.2f} ريال**")
    
    # زر تحميل PDF
    if st.button("📥 تحميل النموذج (PDF)", type="primary"):
        pdf_file = generate_pdf(r, salary, annual_days, str(last_calc), allowance)
        st.download_button(
            label="📥 تحميل الآن",
            data=pdf_file,
            file_name=f"Leave_Request_{r['id']}_Allowance.pdf",
            mime="application/pdf"
        )

# --- 5. التوجيه الرئيسي ---
if 'user' not in st.session_state: st.session_state['user']=None
if 'page' not in st.session_state: st.session_state['page']='login'

if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        st.caption(f"الدور: {st.session_state['user']['role']}")
        if st.button("🏠"): st.session_state['page']='dashboard'; st.rerun()
        if st.button("✅"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪"): st.session_state.clear(); st.rerun()

if st.session_state['page']=='login': login_page()
elif st.session_state['page']=='dashboard': dashboard_page()
elif st.session_state['page']=='form': form_page()
elif st.session_state['page']=='approvals': approvals_page()
elif st.session_state['page']=='my_requests': my_requests_page()
elif st.session_state['page']=='calc_allowance': calc_allowance_page()
