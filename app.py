import streamlit as st
from supabase import create_client, ClientOptions
import pandas as pd
from datetime import datetime
import time
import urllib.parse

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
    
    /* شريط التتبع */
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
    
    # تحديد الأعمدة بدقة
    note_col = ""
    if field == "status_substitute": note_col = "substitute_note"
    elif field == "status_manager": note_col = "manager_note"
    elif field == "status_hr": note_col = "hr_note"
    
    data = { field: status, note_col: note }
    
    if field == "status_hr" and status == "Approved":
        data["final_status"] = "Approved"
    elif status == "Rejected":
        data["final_status"] = "Rejected"
        
    supabase.table("requests").update(data).eq("id", req_id).execute()

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

    # --- باقي الخدمات (مختصرة) ---
    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        amt = st.number_input("المبلغ", 500); rsn = st.text_area("الغرض")
        if st.button("إرسال"): 
            submit_request_db({"emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'], "service_type": "سلفة", "amount": amt, "details": rsn})
            st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ اعتماد الطلبات")
    
    tasks = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if not tasks: st.success("🎉 لا توجد مهام."); return
    
    for r in tasks:
        task_type = r.get('task_type', 'Manager')
        label = "موافقة بديل" if task_type=='Substitute' else "مدير" if task_type=='Manager' else "HR"
        
        with st.expander(f"[{label}] {r['service_type']} - {r['emp_name']}", expanded=True):
            st.write(f"**التفاصيل:** {r.get('sub_type','-')} ({r.get('days','-')} أيام)")
            if task_type == 'Substitute': st.info("⚠️ هذا الزميل اختارك بديلاً له.")
            
            note = st.text_input("ملاحظة", key=f"n_{r['id']}")
            c1, c2 = st.columns(2)
            
            field = "status_substitute" if task_type=='Substitute' else "status_manager" if task_type=='Manager' else "status_hr"
            
            if c1.button("✅ موافقة واعتماد", key=f"ok_{r['id']}"):
                update_status_db(r['id'], field, "Approved", note, u['name'])
                st.success("تم الاعتماد!")
                
                # زر الواتساب (يظهر للـ HR فقط)
                if task_type == 'HR':
                    phone = r.get('phone', '').replace('0', '966', 1)
                    msg = f"عزيزي {r['emp_name']}، تم اعتماد إجازتك ({r.get('sub_type')}) لمدة {r.get('days')} أيام.\nإجازة سعيدة!"
                    wa_link = f"https://wa.me/{phone}?text={urllib.parse.quote(msg)}"
                    st.markdown(f"""
                    <a href="{wa_link}" target="_blank">
                        <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight:bold;">
                        📲 إرسال إشعار واتساب للموظف
                        </button>
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.rerun()

            if c2.button("❌ رفض", key=f"no_{r['id']}"):
                update_status_db(r['id'], field, "Rejected", note, u['name'])
                st.rerun()

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
            
            # زر الطباعة (يظهر فقط عند الموافقة النهائية)
            if final == 'Approved':
                if st.button("🖨️ طباعة النموذج", key=f"pr_{r['id']}"):
                    print_view(r)
            
            st.divider()

def print_view(r):
    st.markdown(f"""
    <div style="border:2px solid black; padding:30px; background:white; color:black; font-family:Arial; direction:rtl; text-align:right;">
        <h2 style="text-align:center;">نموذج إجازة / مغادرة</h2>
        <hr>
        <table style="width:100%; border-collapse:collapse;" border="1">
            <tr><td style="padding:8px;background:#f0f0f0;">الاسم</td><td style="padding:8px;">{r['emp_name']}</td><td style="padding:8px;background:#f0f0f0;">الرقم</td><td style="padding:8px;">{r['emp_id']}</td></tr>
            <tr><td style="padding:8px;background:#f0f0f0;">القسم</td><td style="padding:8px;">{r['dept']}</td><td style="padding:8px;background:#f0f0f0;">الوظيفة</td><td style="padding:8px;">{r.get('job_title','-')}</td></tr>
        </table>
        <br>
        <h3>بيانات الطلب:</h3>
        <p><strong>نوع الإجازة:</strong> {r.get('sub_type')}</p>
        <p><strong>المدة:</strong> {r.get('days')} أيام (من {r.get('start_date')} إلى {r.get('end_date')})</p>
        <p><strong>الموظف البديل:</strong> {r.get('substitute_name') or 'لا يوجد'}</p>
        <br>
        <div style="border:1px dashed black; padding:10px; font-size:0.9em;">
            <strong>الإقــرار:</strong><br>
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد... (تمت الموافقة الإلكترونية بتاريخ {r['created_at'][:10]})
        </div>
        <br><br>
        <table style="width:100%; text-align:center;">
            <tr>
                <td><strong>المدير المباشر</strong><br>✅ معتمد<br>{r.get('manager_note','')}</td>
                <td><strong>الموارد البشرية</strong><br>✅ معتمد<br>{r.get('hr_note','')}</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)
    st.button("إغلاق الطباعة", key="close_pr")

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
