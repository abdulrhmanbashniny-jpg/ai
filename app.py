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

# تسجيل خط عربي
try:
    pdfmetrics.registerFont(TTFont('Arabic', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
except:
    pass

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="HR Enterprise System", layout="wide", page_icon="🏢")

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
    
    .step { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; margin: 5px; }
    .step-done { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .step-wait { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بـ Supabase ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key, options=ClientOptions(postgrest_client_timeout=60))
    except Exception as e:
        st.error(f"خطأ اتصال: {e}")
        return None

supabase = init_supabase()

# --- 3. دوال البيانات ---
def get_user_data(uid):
    if not supabase: return None
    res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
    if res.data: return res.data[0]
    return None

def submit_request_db(data):
    if not supabase: return False
    try:
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ: {e}")
        return False

def get_requests_for_role(role, uid, dept):
    if not supabase: return []
    requests = []
    
    # 1. بديل
    sub_reqs = supabase.table("requests").select("*").eq("substitute_id", uid).eq("status_substitute", "Pending").execute().data
    if sub_reqs:
        for r in sub_reqs: r['task_type'] = 'Substitute'
        requests.extend(sub_reqs)

    # 2. مدير
    if role == "Manager":
        mgr_reqs = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr_reqs:
            if r.get('status_substitute') in ['Approved', 'Not Required']:
                r['task_type'] = 'Manager'
                requests.append(r)

    # 3. HR
    if role == "HR":
        hr_reqs = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr_reqs:
            r['task_type'] = 'HR'
            requests.append(r)
            
    return requests

def update_status_db(req_id, field, status, note, user_name):
    if not supabase: return
    
    note_col = ""
    if field == "status_substitute": note_col = "substitute_note"
    elif field == "status_manager": note_col = "manager_note"
    elif field == "status_hr": note_col = "hr_note"
    
    data = { 
        field: status, 
        note_col: note,
        f"{field.replace('status_', '')}_action_at": datetime.now().isoformat()
    }
    
    if field == "status_hr" and status == "Approved":
        data["final_status"] = "Approved"
    elif status == "Rejected":
        data["final_status"] = "Rejected"
        
    supabase.table("requests").update(data).eq("id", req_id).execute()

def generate_pdf(r, approver_name=""):
    """توليد PDF للنموذج مع التوقيعات"""
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # العنوان
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 1*cm, "LEAVE REQUEST FORM")
    c.drawCentredString(width/2, height - 1.5*cm, "نموذج طلب إجازة")
    
    # الخط الفاصل
    c.line(1*cm, height - 1.8*cm, width - 1*cm, height - 1.8*cm)
    
    # المعلومات
    y_pos = height - 2.5*cm
    c.setFont("Helvetica", 10)
    
    c.drawString(1*cm, y_pos, f"Employee Name: {r['emp_name']}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Employee ID: {r['emp_id']}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Department: {r['dept']}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Position: {r.get('job_title', '-')}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Leave Type: {r.get('sub_type', '-')}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Duration: {r.get('days')} days")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"From: {r.get('start_date')} To: {r.get('end_date')}")
    y_pos -= 0.5*cm
    c.drawString(1*cm, y_pos, f"Substitute: {r.get('substitute_name', 'N/A')}")
    
    # الإقرار الكامل
    y_pos -= 1*cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1*cm, y_pos, "DECLARATION / الاقرار:")
    y_pos -= 0.5*cm
    
    declaration_text = """أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال 
خطاب رسمي لتمديد الإجازة والموافقة عليها خطياً من قبل رئيسي المباشر. كما أعتبر نفسي منذراً بالفصل النهائي عند تجاوز 
مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وذلك دون الحاجة لإنذاري رسمياً على عنواني في بلدي. وأنني سأقوم 
بإجازتي في التاريخ المبين أعلاه، وبذلك ألتزم وعلى ذلك أوقع إلكترونياً."""
    
    c.setFont("Helvetica", 8)
    for line in declaration_text.split('\n'):
        c.drawString(1*cm, y_pos, line.strip())
        y_pos -= 0.4*cm
    
    # التواقيع
    y_pos -= 0.5*cm
    c.line(1*cm, y_pos, width - 1*cm, y_pos)
    y_pos -= 0.8*cm
    
    # توقيع الموظف
    c.setFont("Helvetica-Bold", 9)
    c.drawString(1*cm, y_pos, "Employee Signature")
    c.drawString(1*cm, y_pos - 0.3*cm, f"توقيع الموظف: {r['emp_name']}")
    c.drawString(1*cm, y_pos - 0.6*cm, f"Date / التاريخ: {datetime.now().strftime('%Y-%m-%d')}")
    
    # توقيع المدير
    c.drawString(width/2, y_pos, "Manager Approval")
    c.drawString(width/2, y_pos - 0.3*cm, f"توقيع المدير")
    c.drawString(width/2, y_pos - 0.6*cm, f"Date / التاريخ: {r.get('manager_action_at', 'Pending')[:10]}")
    
    # توقيع HR
    if r.get('final_status') == 'Approved':
        y_pos -= 1.2*cm
        c.drawString(1*cm, y_pos, "HR Approval")
        c.drawString(1*cm, y_pos - 0.3*cm, f"توقيع الموارد البشرية: {approver_name}")
        c.drawString(1*cm, y_pos - 0.6*cm, f"Date / التاريخ: {r.get('hr_action_at', 'Pending')[:10]}")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- 4. الصفحات ---
def login_page():
    st.markdown("<br><h1 style='text-align:center; color:#2980b9;'>🔐 دخول النظام المركزي</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user_data(uid)
                if user and (user.get('password') == pwd or pwd=="123456"):
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else: st.error("بيانات خاطئة")

def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 مرحباً، {u['name']}")
    
    tasks = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if tasks: st.warning(f"🔔 لديك ({len(tasks)}) مهام معلقة.")

    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم طلب إجازة"): nav("leave")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف المالية</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم طلب سلفة"): nav("loan")
    with c3:
        st.markdown('<div class="service-card"><h3>📂 ملفي والطلبات</h3></div>', unsafe_allow_html=True)
        if st.button("سجل المعاملات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def form_page():
    u = st.session_state['user']
    svc = st.session_state['service']
    if st.button("🔙 إلغاء"): st.session_state['page']='dashboard'; st.rerun()
    st.write("---")
    
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        c1, c2, c3 = st.columns(3)
        c1.text_input("الاسم", u['name'], disabled=True)
        c2.text_input("القسم", u['dept'], disabled=True)
        c3.text_input("الجوال", u.get('phone',''), disabled=True)
        st.divider()
        
        l_type = st.selectbox("النوع", ["سنوية (Yearly)", "مرضية (Sick)", "بدون راتب (Unpaid)"])
        c_d1, c_d2 = st.columns(2)
        d1 = c_d1.date_input("من", datetime.today())
        d2 = c_d2.date_input("إلى", datetime.today())
        
        days = 0
        if d2 >= d1:
            days = (d2 - d1).days + 1
            st.info(f"📅 المدة: {days} يوم")
            if l_type.startswith("مرضية") and days > 60:
                st.error("❌ الحد الأقصى للمرضية 60 يوماً."); days=-1
            elif l_type.startswith("بدون") and days > 10:
                st.error("❌ الحد الأقصى لبدون راتب 10 أيام."); days=-1
        else: st.error("التواريخ غير صحيحة"); days=-1

        st.write("### الموظف البديل")
        sub_id = st.text_input("رقم البديل (اختياري)")
        sub_name = None
        if sub_id:
            sub_user = get_user_data(sub_id)
            if sub_user: 
                st.success(f"✅ البديل: {sub_user['name']}")
                sub_name = sub_user['name']
            else: st.warning("⚠️ الرقم غير صحيح")

        st.markdown("""
        <div style="background:#fffbf2; border:1px solid #f0e6ce; padding:15px; border-radius:8px; color:#5a4a2d; font-size:0.95em; line-height:1.6; text-align:justify;">
        <strong>(( إقــرار وتعهــد ))</strong><br>
        أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال <strong>خطاب رسمي</strong> لتمديد الإجازة والموافقة عليها خطياً من قبل رئيسي المباشر. 
        كما أعتبر نفسي منذراً بالفصل النهائي عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وذلك دون الحاجة لإنذاري رسمياً على عنواني في بلدي. 
        وأنني سأقوم بإجازتي في التاريخ المبين أعلاه، وبذلك ألتزم وعلى ذلك أوقع إلكترونياً.
        </div>
        """, unsafe_allow_html=True)
        
        agree = st.checkbox("✅ أوافق وألتزم بما ورد في الإقرار أعلاه")
        
        if st.button("🚀 إرسال", type="primary"):
            if days > 0 and agree:
                data = {
                    "emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'],
                    "job_title": u.get('job_title','-'), "phone": u.get('phone',''), "nationality": u.get('nationality','-'),
                    "service_type": "إجازة", "sub_type": l_type, "details": "طلب إجازة",
                    "start_date": str(d1), "end_date": str(d2), "days": days,
                    "substitute_id": sub_id if sub_id else None, "substitute_name": sub_name,
                    "status_substitute": "Pending" if sub_id else "Not Required",
                    "declaration_agreed": True
                }
                if submit_request_db(data):
                    st.success("تم الإرسال!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        amt = st.number_input("المبلغ", 500); rsn = st.text_area("الغرض")
        if st.button("إرسال"): 
            submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "سلفة", "amount": amt, "details": rsn})
            st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ المهام والموافقات")
    
    tasks = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if not tasks: st.success("🎉 لا توجد مهام."); return
    
    for r in tasks:
        task_type = r.get('task_type', 'Manager')
        label = "موافقة بديل" if task_type=='Substitute' else "موافقة مدير" if task_type=='Manager' else "موافقة HR"
        
        with st.expander(f"[{label}] {r['service_type']} - {r['emp_name']}", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write(f"**نوع الطلب:** {r.get('sub_type','-')}")
                st.write(f"**المدة:** {r.get('days','-')} أيام (من {r.get('start_date')} إلى {r.get('end_date')})")
                if task_type == 'Substitute': 
                    st.warning("⚠️ هذا الزميل اختارك بديلاً له. يرجى التأكيد من توفرك.")
            
            with col2:
                note = st.text_input("ملاحظات", key=f"n_{r['id']}", placeholder="اختياري")
                
                c_ok, c_no = st.columns(2)
                field = "status_substitute" if task_type=='Substitute' else "status_manager" if task_type=='Manager' else "status_hr"
                
                if c_ok.button("✅ موافقة", key=f"ok_{r['id']}"):
                    update_status_db(r['id'], field, "Approved", note, u['name'])
                    st.success("✅ تم الاعتماد!")
                    
                    # إذا كانت موافقة HR النهائية، أظهر زر الواتساب
                    if task_type == 'HR':
                        phone = r.get('phone', '').replace('0', '966', 1)
                        msg = f"السلام عليكم {r['emp_name']}،\n\n✅ تم اعتماد إجازتك\n📅 النوع: {r.get('sub_type')}\n⏳ المدة: {r.get('days')} أيام\n📆 من {r.get('start_date')} إلى {r.get('end_date')}\n\nإجازة موفقة!"
                        wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                        st.markdown(f"""
                        <a href="{wa_link}" target="_blank" style="text-decoration:none;">
                            <button style="background-color:#25D366; color:white; border:none; padding:12px 20px; border-radius:8px; cursor:pointer; font-weight:bold; width:100%; margin-top:10px;">
                            📲 إرسال إشعار واتساب للموظف
                            </button>
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        time.sleep(1); st.rerun()
                
                if c_no.button("❌ رفض", key=f"no_{r['id']}"):
                    update_status_db(r['id'], field, "Rejected", note, u['name'])
                    st.rerun()

def my_requests_page():
    st.title("📂 سجل معاملاتي")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    
    u = st.session_state['user']
    if not supabase: return
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs: st.info("السجل فارغ."); return
    
    for r in reqs:
        with st.container():
            st.markdown(f"### {r['service_type']} ({r.get('sub_type', '-')})")
            
            s_sub = "step-done" if r.get('status_substitute') in ['Approved','Not Required'] else "step-wait"
            s_mgr = "step-done" if r['status_manager']=='Approved' else "step-wait"
            s_hr = "step-done" if r['status_hr']=='Approved' else "step-wait"
            final = r.get('final_status', 'تحت الإجراء')
            
            st.markdown(f"""
            <span class="{s_sub}">1. البديل</span> ➡️ 
            <span class="{s_mgr}">2. المدير</span> ➡️ 
            <span class="{s_hr}">3. HR</span> ➡️ 
            <span style="display:inline-block; padding:5px 15px; border-radius:20px; font-weight:bold; background:#cce5ff; color:#004085;">{final}</span>
            """, unsafe_allow_html=True)
            
            # زر تحميل PDF (يظهر فقط عند الموافقة النهائية)
            if final == 'Approved':
                col1, col2 = st.columns([1, 4])
                with col1:
                    pdf_buffer = generate_pdf(r, r.get('hr_note', 'N/A'))
                    st.download_button(
                        label="📥 تحميل PDF",
                        data=pdf_buffer,
                        file_name=f"Leave_Request_{r['emp_id']}_{r['created_at'][:10]}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{r['id']}"
                    )
            
            st.divider()

# --- 5. التوجيه الرئيسي ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'

if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        st.caption(f"الدور: {st.session_state['user']['role']}")
        if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.rerun()
        if st.button("✅ المهام والموافقات"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪 خروج"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
