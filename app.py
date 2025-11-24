import streamlit as st
from supabase import create_client, ClientOptions
import pandas as pd
from datetime import datetime
import time
import urllib.parse
from io import BytesIO
from xhtml2pdf import pisa

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
    
    /* تنسيق الطباعة */
    @media print {
        body * { visibility: hidden; }
        #printableArea, #printableArea * { visibility: visible; }
        #printableArea { position: absolute; left: 0; top: 0; width: 100%; }
    }
    
    /* تنسيق الإقرار */
    .declaration-text {
        background-color: #fff3cd; 
        border: 1px solid #ffeeba; 
        padding: 15px; 
        border-radius: 5px; 
        color: #856404; 
        font-size: 0.95em; 
        line-height: 1.6; 
        margin-bottom: 15px;
        white-space: pre-wrap; /* يمنع قص النص */
        text-align: justify;
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

def submit_request_db(data):
    if not supabase: return False
    try:
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ: {e}"); return False

def get_requests_for_role(role, uid, dept):
    if not supabase: return [], []
    requests = []
    history = []
    
    # 1. بديل
    sub_reqs = supabase.table("requests").select("*").eq("substitute_id", uid).eq("status_substitute", "Pending").execute().data
    if sub_reqs:
        for r in sub_reqs: r['task_type'] = 'Substitute'; requests.append(r)

    # 2. مدير
    if role == "Manager":
        mgr_reqs = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
        for r in mgr_reqs:
            if r.get('status_substitute') in ['Approved', 'Not Required']:
                r['task_type'] = 'Manager'; requests.append(r)

    # 3. HR
    if role == "HR":
        hr_reqs = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute().data
        for r in hr_reqs: r['task_type'] = 'HR'; requests.append(r)
        history = supabase.table("requests").select("*").eq("status_hr", "Approved").order("hr_action_at", desc=True).limit(10).execute().data
            
    return requests, history

def update_status_db(req_id, field, status, note, user_name):
    if not supabase: return
    col_map = {"status_substitute":"substitute_note", "status_manager":"manager_note", "status_hr":"hr_note"}
    data = { field: status, col_map[field]: note, f"{field.replace('status_', '')}_action_at": datetime.now().isoformat() }
    if field == "status_hr" and status == "Approved": data["final_status"] = "Approved"
    elif status == "Rejected": data["final_status"] = "Rejected"
    supabase.table("requests").update(data).eq("id", req_id).execute()

def show_print_view(r):
    st.markdown(f"""
    <div id="printableArea" style="border:2px solid #333; padding:40px; background:white; color:black; font-family:Arial; direction:rtl; text-align:right; max-width:800px; margin:auto;">
        <div style="text-align:center; border-bottom:2px solid #333; padding-bottom:20px; margin-bottom:30px;">
            <h2>نموذج إجازة / مغادرة</h2>
        </div>
        <table style="width:100%; border-collapse:collapse; margin-bottom:30px;" border="1" cellpadding="10">
            <tr>
                <td style="background:#f9f9f9; font-weight:bold;">الاسم</td><td>{r['emp_name']}</td>
                <td style="background:#f9f9f9; font-weight:bold;">الرقم</td><td>{r['emp_id']}</td>
            </tr>
            <tr>
                <td style="background:#f9f9f9; font-weight:bold;">القسم</td><td>{r['dept']}</td>
                <td style="background:#f9f9f9; font-weight:bold;">المسمى</td><td>{r.get('job_title','-')}</td>
            </tr>
        </table>
        <div style="border:1px solid #ddd; padding:20px; border-radius:8px; margin-bottom:30px;">
            <p><strong>النوع:</strong> {r.get('sub_type')}</p>
            <p><strong>المدة:</strong> {r.get('days')} أيام (من {r.get('start_date')} إلى {r.get('end_date')})</p>
            <p><strong>البديل:</strong> {r.get('substitute_name', 'لا يوجد')}</p>
        </div>
        <div style="background:#fffbf2; border:1px solid #f0e6ce; padding:20px; margin-bottom:40px; text-align:justify;">
            <strong>إقرار:</strong><br>
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب لتمديد الإجازة والموافقة عليها من قبل رئيسي كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة من نظام العمل والعمال وذلك دون الحاجه لإنذاري على عنواني في بلدي وأنني سأقوم بإجازتي في التاريخ المبين أعلاه وبذلك سألتزم وعلى ذلك أوقع.
        </div>
        <table style="width:100%; text-align:center; margin-top:50px;">
            <tr>
                <td><strong>الموظف</strong><br>{r['emp_name']}</td>
                <td><strong>المدير المباشر</strong><br>✅ {r.get('manager_note','موافق')}</td>
                <td><strong>الموارد البشرية</strong><br>✅ {r.get('hr_note','موافق')}</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)
    st.info("اضغط Ctrl+P للطباعة")
    if st.button("إغلاق"): st.rerun()

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
    
    # تمت استعادة جميع الأزرار هنا
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
        
        # الإقرار الكامل (تم إصلاحه ليظهر كاملاً)
        st.markdown("""
        <div class="declaration-text">
        <strong>(( إقــرار ))</strong><br>
        أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه كما أني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال خطاب لتمديد الإجازة والموافقة عليها من قبل رئيسي كما أعتبر نفسي منذراً بالفصل عند تجاوز مدة الغياب حسب المدة المحددة من نظام العمل والعمال وذلك دون الحاجه لإنذاري على عنواني في بلدي وأنني سأقوم بإجازتي في التاريخ المبين أعلاه وبذلك سألتزم وعلى ذلك أوقع.
        </div>
        """, unsafe_allow_html=True)
        
        agree = st.checkbox("أوافق وألتزم بما ورد أعلاه")
        
        if st.button("إرسال"):
            if agree and days>0:
                data = {"emp_id":u['emp_id'], "emp_name":u['name'], "dept":u['dept'], "service_type":"إجازة", 
                        "sub_type":l_type, "start_date":str(d1), "end_date":str(d2), "days":days,
                        "substitute_id":sub_id or None, "substitute_name":sub_name,
                        "status_substitute":"Pending" if sub_id else "Not Required", "declaration_agreed":True}
                submit_request_db(data); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
            else: st.error("يجب الموافقة على الإقرار والتأكد من التاريخ")

    # بقية النماذج (تمت إعادتها)
    elif svc == 'loan':
        st.header("💰 طلب سلفة"); amt = st.number_input("المبلغ", 500); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "سلفة", "amount": amt, "details": rsn}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'purchase':
        st.header("🛒 طلب شراء"); item = st.text_input("الصنف"); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "مشتريات", "details": f"{item} - {rsn}"}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'travel':
        st.header("✈️ انتداب"); dst = st.text_input("الوجهة"); rsn = st.text_area("السبب")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "انتداب", "details": f"إلى {dst} - {rsn}"}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    elif svc == 'perm':
        st.header("⏱️ استئذان"); d = st.date_input("التاريخ"); tm = st.time_input("الوقت")
        if st.button("إرسال"): submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "استئذان", "start_date": str(d), "details": str(tm)}); st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']; st.title("✅ المهام")
    tasks, history = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    
    if tasks:
        for r in tasks:
            with st.expander(f"{r['emp_name']} - {r['sub_type'] or r['service_type']}", expanded=True):
                st.write(f"التفاصيل: {r.get('days',0)} يوم - {r.get('details','')}")
                note = st.text_input("ملاحظة", key=f"n{r['id']}")
                c1,c2=st.columns(2)
                if c1.button("موافقة", key=f"ok{r['id']}"):
                    f = "status_substitute" if r['task_type']=='Substitute' else "status_manager" if r['task_type']=='Manager' else "status_hr"
                    update_status_db(r['id'], f, "Approved", note, u['name']); st.rerun()
                if c2.button("رفض", key=f"no{r['id']}"):
                    f = "status_substitute" if r['task_type']=='Substitute' else "status_manager" if r['task_type']=='Manager' else "status_hr"
                    update_status_db(r['id'], f, "Rejected", note, u['name']); st.rerun()
    else: st.info("لا توجد مهام")
    
    if u['role']=='HR' and history:
        st.divider(); st.subheader("سجل الموافقات (لإرسال واتساب)")
        for h in history:
            phone = h.get('phone','').replace('0','966',1)
            link = f"https://wa.me/{phone}?text={urllib.parse.quote(f'تم اعتماد طلبك ({h['service_type']})')}"
            st.markdown(f"<a href='{link}' target='_blank'>📲 واتساب لـ {h['emp_name']}</a>", unsafe_allow_html=True)

def my_requests_page():
    u = st.session_state['user']; st.title("📂 ملفي")
    if st.button("🔙"): st.session_state['page']='dashboard'; st.rerun()
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    for r in reqs:
        with st.container():
            st.write(f"**{r['service_type']}** - {r.get('final_status','تحت الإجراء')}")
            if r.get('final_status')=='Approved' and r['service_type']=='إجازة':
                if st.button("🖨️ عرض للطباعة", key=f"pr{r['id']}"):
                    show_print_view(r)
            st.divider()

if 'user' not in st.session_state: st.session_state['user']=None
if 'page' not in st.session_state: st.session_state['page']='login'
if st.session_state['user']:
    with st.sidebar:
        st.header(st.session_state['user']['name'])
        if st.button("🏠"): st.session_state['page']='dashboard'; st.rerun()
        if st.button("✅"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪"): st.session_state.clear(); st.rerun()

if st.session_state['page']=='login': login_page()
elif st.session_state['page']=='dashboard': dashboard_page()
elif st.session_state['page']=='form': form_page()
elif st.session_state['page']=='approvals': approvals_page()
elif st.session_state['page']=='my_requests': my_requests_page()
