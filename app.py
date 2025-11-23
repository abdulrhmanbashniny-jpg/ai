import streamlit as st
from supabase import create_client, ClientOptions
import pandas as pd
from datetime import datetime
import time
import urllib.parse
from io import BytesIO
from xhtml2pdf import pisa  # مكتبة جديدة للـ PDF تدعم HTML

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
    .step-now { background: #cce5ff; color: #004085; border: 1px solid #b8daff; font-weight:bold; }
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
    
    # 1. البحث عن الطلبات المعلقة
    if role == "Manager":
        mgr_reqs = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr_reqs:
            if r.get('status_substitute') in ['Approved', 'Not Required']:
                r['task_type'] = 'Manager'
                requests.append(r)
    
    if role == "HR":
        hr_reqs = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr_reqs:
            r['task_type'] = 'HR'
            requests.append(r)
            
    # 2. البحث عن الطلبات المنتهية (لغرض الواتساب والسجل)
    history = []
    if role == "HR":
        # آخر 10 طلبات معتمدة
        history = supabase.table("requests").select("*").eq("status_hr", "Approved").order("hr_action_at", desc=True).limit(10).execute().data
        
    return requests, history

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

def generate_pdf_html(r):
    """توليد PDF يدعم العربية باستخدام HTML"""
    # سنستخدم خطاً عاماً يدعم العربية، أو نعتمد على خط النظام
    # ملاحظة: في الويب، الخطوط العربية تحتاج تهيئة خاصة، هنا نستخدم قالب HTML بسيط
    
    html_content = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 2cm; }}
            body {{ font-family: sans-serif; }}
            .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }}
            .title {{ font-size: 24px; font-weight: bold; }}
            .info-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .info-table td {{ border: 1px solid #ddd; padding: 8px; }}
            .label {{ background-color: #f9f9f9; font-weight: bold; width: 30%; }}
            .declaration {{ background-color: #fffbf2; border: 1px solid #f0e6ce; padding: 15px; text-align: justify; margin: 20px 0; font-size: 12px; }}
            .signatures {{ width: 100%; margin-top: 50px; }}
            .signatures td {{ text-align: center; vertical-align: bottom; height: 100px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">نموذج طلب إجازة</div>
            <div>Leave Request Form</div>
        </div>

        <table class="info-table">
            <tr>
                <td class="label">اسم الموظف</td>
                <td>{r['emp_name']}</td>
                <td class="label">الرقم الوظيفي</td>
                <td>{r['emp_id']}</td>
            </tr>
            <tr>
                <td class="label">القسم</td>
                <td>{r['dept']}</td>
                <td class="label">المسمى الوظيفي</td>
                <td>{r.get('job_title', '-')}</td>
            </tr>
            <tr>
                <td class="label">نوع الإجازة</td>
                <td>{r.get('sub_type', '-')}</td>
                <td class="label">المدة</td>
                <td>{r.get('days')} أيام</td>
            </tr>
            <tr>
                <td class="label">من تاريخ</td>
                <td>{r.get('start_date')}</td>
                <td class="label">إلى تاريخ</td>
                <td>{r.get('end_date')}</td>
            </tr>
            <tr>
                <td class="label">الموظف البديل</td>
                <td colspan="3">{r.get('substitute_name', 'لا يوجد')}</td>
            </tr>
        </table>

        <div class="declaration">
            <strong>إقــرار وتعهــد:</strong><br>
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب رسمي لتمديد الإجازة والموافقة عليها خطياً من قبل رئيسي المباشر. 
            كما أعتبر نفسي منذراً بالفصل النهائي عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وذلك دون الحاجة لإنذاري رسمياً على عنواني في بلدي. 
            وأنني سأقوم بإجازتي في التاريخ المبين أعلاه، وبذلك ألتزم وعلى ذلك أوقع إلكترونياً.
        </div>

        <table class="signatures">
            <tr>
                <td>
                    <strong>توقيع الموظف</strong><br>
                    {r['emp_name']}<br>
                    {r['created_at'][:10]}
                </td>
                <td>
                    <strong>المدير المباشر</strong><br>
                    {r.get('manager_note') or 'موافق'}<br>
                    {r.get('manager_action_at', '')[:10]}
                </td>
                <td>
                    <strong>الموارد البشرية</strong><br>
                    {r.get('hr_note') or 'موافق'}<br>
                    {r.get('hr_action_at', '')[:10]}
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    result = BytesIO()
    pisa.CreatePDF(BytesIO(html_content.encode("UTF-8")), result)
    return result.getvalue()

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
    
    tasks, _ = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
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

        st.warning("**(( إقــرار ))**\nأقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد... ولن أتجاوز المدة إلا عند إرسال **خطاب** لتمديد الإجازة والموافقة عليها...")
        agree = st.checkbox("✅ أوافق")
        
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
    
    tasks, history = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    
    # 1. قسم المهام المعلقة
    if tasks:
        st.subheader("📌 مهام بانتظار إجرائك")
        for r in tasks:
            task_type = r.get('task_type', 'Manager')
            label = "موافقة بديل" if task_type=='Substitute' else "موافقة مدير" if task_type=='Manager' else "موافقة HR"
            
            with st.expander(f"[{label}] {r['service_type']} - {r['emp_name']}", expanded=True):
                st.write(f"**التفاصيل:** {r.get('sub_type','-')} ({r.get('days','-')} أيام)")
                note = st.text_input("ملاحظة", key=f"n_{r['id']}")
                c1, c2 = st.columns(2)
                
                field = "status_substitute" if task_type=='Substitute' else "status_manager" if task_type=='Manager' else "status_hr"
                
                if c1.button("✅ اعتماد", key=f"ok_{r['id']}"):
                    update_status_db(r['id'], field, "Approved", note, u['name'])
                    st.success("تم!")
                    time.sleep(1); st.rerun()
                if c2.button("❌ رفض", key=f"no_{r['id']}"):
                    update_status_db(r['id'], field, "Rejected", note, u['name'])
                    st.rerun()
    else:
        st.info("🎉 لا توجد مهام معلقة.")
    
    # 2. قسم السجل (لإرسال الواتساب لاحقاً)
    if u['role'] == 'HR' and history:
        st.divider()
        st.subheader("📜 سجل الموافقات الأخيرة (لإرسال الواتساب)")
        for h in history:
            with st.expander(f"✅ {h['emp_name']} - {h['sub_type']} ({h['created_at'][:10]})"):
                phone = h.get('phone', '').replace('0', '966', 1)
                msg = f"عزيزي {h['emp_name']}،\nتم اعتماد طلبك ({h['sub_type']}).\nالمدة: {h['days']} أيام."
                wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                
                st.markdown(f"""
                <a href="{wa_link}" target="_blank">
                    <button style="background-color:#25D366; color:white; border:none; padding:8px 15px; border-radius:5px; font-weight:bold; cursor:pointer;">
                    📲 إرسال واتساب
                    </button>
                </a>
                """, unsafe_allow_html=True)

def my_requests_page():
    st.title("📂 تتبع معاملاتي")
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
            final = r.get('final_status', 'Under Review')
            
            st.markdown(f"""
            <span class="{s_sub}">1. البديل</span> ➡️ 
            <span class="{s_mgr}">2. المدير</span> ➡️ 
            <span class="{s_hr}">3. HR</span> ➡️ 
            <span class="step-now">{final}</span>
            """, unsafe_allow_html=True)
            
            if final == 'Approved':
                pdf_data = generate_pdf_html(r)
                st.download_button(
                    label="📥 تحميل القرار (PDF)",
                    data=pdf_data,
                    file_name=f"Decision_{r['id']}.pdf",
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
        if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.rerun()
        if st.button("✅ المهام"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪 خروج"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
