import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import urllib.parse

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="HR System V2", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; cursor: pointer; margin-bottom:15px;
    }
    .service-card:hover { transform: translateY(-5px); border-color: #2ecc71; }
    h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: 600; }
    
    /* شريط التتبع */
    .step { display: inline-block; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; margin: 5px; }
    .step-done { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .step-wait { background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .step-now { background: #cce5ff; color: #004085; border: 1px solid #b8daff; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال ---
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
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"خطأ: {e}")
        return False

def get_requests_for_role(role, uid, dept):
    if role == "Employee":
        return supabase.table("requests").select("*").eq("emp_id", uid).order("created_at", desc=True).execute().data
    if role == "Manager":
        # المدير يرى طلبات قسمه التي لم يوافق عليها بعد
        return supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute().data
    if role == "HR":
        # الـ HR يرى ما وافق عليه المدير
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

# --- 4. الصفحات ---

def login_page():
    st.markdown("<br><h1 style='text-align:center; color:#2980b9;'>🔐 دخول النظام المركزي</h1>", unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف", value="1011")
            pwd = st.text_input("كلمة المرور", type="password", value="123456")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user_data(uid)
                if user and user['password'] == pwd:
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else: st.error("بيانات خاطئة")

def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 مرحباً، {u['name']}")
    
    if u['role'] in ['Manager', 'HR']:
        count = len(get_requests_for_role(u['role'], u['emp_id'], u['dept']))
        if count > 0: st.info(f"🔔 لديك ({count}) طلبات بانتظار الاعتماد!")

    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم إجازة"): nav("leave")
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): nav("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): nav("loan")
        st.markdown('<div class="service-card"><h3>✈️ رحلات العمل</h3></div>', unsafe_allow_html=True)
        if st.button("طلب انتداب"): nav("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"): nav("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 متابعة طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("سجل المعاملات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def form_page():
    u = st.session_state['user']
    svc = st.session_state['service']
    if st.button("🔙 إلغاء"): st.session_state['page']='dashboard'; st.rerun()
    
    st.write("---")
    
    # --- نموذج الإجازات ---
    if svc == 'leave':
        st.header("🌴 نموذج طلب إجازة")
        
        c1, c2, c3 = st.columns(3)
        c1.text_input("الاسم", u['name'], disabled=True)
        c2.text_input("القسم", u['dept'], disabled=True)
        c3.text_input("الجوال", u['phone'], disabled=True)
        
        st.divider()
        
        # أنواع الإجازات الجديدة
        l_type = st.selectbox("نوع الإجازة", ["سنوية (Yearly)", "مرضية (Sick)", "بدون راتب (Unpaid)"])
        
        c_d1, c_d2 = st.columns(2)
        start_d = c_d1.date_input("تاريخ البداية")
        end_d = c_d2.date_input("تاريخ النهاية")
        
        days = 0
        if end_d >= start_d:
            days = (end_d - start_d).days + 1
            st.info(f"📅 المدة: {days} يوم")
            
            # التحقق من القوانين
            if l_type == "مرضية (Sick)" and days > 60:
                st.error("❌ لا يسمح بأكثر من 60 يوماً للإجازة المرضية.")
                days = -1 # لمنع الإرسال
            elif l_type == "بدون راتب (Unpaid)" and days > 10:
                st.error("❌ لا يسمح بأكثر من 10 أيام للإجازة بدون راتب.")
                days = -1
        else:
            st.error("تاريخ النهاية غير صحيح")
            days = -1

        st.write("### الموظف البديل")
        sub_id = st.text_input("رقم البديل (اختياري)")
        
        st.warning("**(( إقــرار ))**\nأقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد... ولن أتجاوز المدة إلا عند إرسال **خطاب** لتمديد الإجازة...")
        agree = st.checkbox("✅ أوافق على الإقرار")
        
        if st.button("🚀 إرسال", type="primary"):
            if days > 0 and agree:
                data = {
                    "emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'],
                    "job_title": u['job_title'], "phone": u['phone'], "nationality": u['nationality'],
                    "service_type": "إجازة", "sub_type": l_type, "details": "طلب إجازة",
                    "start_date": str(start_d), "end_date": str(end_d), "days": days,
                    "substitute_id": sub_id, "declaration_agreed": True
                }
                if submit_request_db(data):
                    st.success("تم الإرسال!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    
    # --- باقي الطلبات (تمت إعادتها) ---
    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        amt = st.number_input("المبلغ", 500); rsn = st.text_area("السبب")
        if st.button("إرسال"): 
            submit_request_db({"emp_id": u['emp_id'], "service_type": "سلفة", "amount": amt, "details": rsn})
            st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        item = st.text_input("اسم المادة"); rsn = st.text_area("السبب")
        if st.button("إرسال"): 
            submit_request_db({"emp_id": u['emp_id'], "service_type": "مشتريات", "details": f"{item} - {rsn}"})
            st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

    elif svc == 'perm':
        st.header("⏱️ استئذان")
        d = st.date_input("التاريخ"); tm = st.time_input("من الساعة")
        if st.button("إرسال"): 
            submit_request_db({"emp_id": u['emp_id'], "service_type": "استئذان", "start_date": str(d), "details": str(tm)})
            st.success("تم!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

def approvals_page():
    u = st.session_state['user']
    st.title("✅ اعتماد الطلبات")
    
    reqs = get_requests_for_role(u['role'], u['emp_id'], u['dept'])
    if not reqs: st.success("لا توجد مهام."); return
    
    for r in reqs:
        with st.expander(f"{r['service_type']} | {r['emp_name']}", expanded=True):
            c1, c2 = st.columns([2,1])
            with c1:
                st.write(f"**النوع:** {r['sub_type'] or r['service_type']}")
                if r['days']: st.write(f"**المدة:** {r['days']} يوم")
                st.caption(f"التفاصيل: {r['details']}")
            
            with c2:
                note = st.text_input("ملاحظة", key=f"n_{r['id']}")
                
                # زر واتساب (يظهر للموارد البشرية فقط عند الموافقة)
                if u['role'] == 'HR':
                    # تجهيز رسالة الواتساب
                    phone = r['phone'].replace('0', '966', 1) if r['phone'] else ""
                    msg = f"مرحباً {r['emp_name']}،\nتم اعتماد طلبك ({r['service_type']}) لمدة {r['days']} أيام.\nمن: {r['start_date']}\nإلى: {r['end_date']}\nحالة الطلب: معتمد نهائياً ✅"
                    encoded_msg = urllib.parse.quote(msg)
                    whatsapp_link = f"https://wa.me/{phone}?text={encoded_msg}"
                    
                    if st.button("✅ اعتماد وإرسال واتساب", key=f"ok_{r['id']}"):
                        update_status_db(r['id'], "status_hr", "Approved", note, u['name'])
                        st.success("تم الاعتماد!")
                        st.markdown(f"### [📲 اضغط هنا لإرسال الواتساب]({whatsapp_link})")
                        
                else:
                    if st.button("✅ موافقة", key=f"ok_{r['id']}"):
                        update_status_db(r['id'], "status_manager", "Approved", note, u['name'])
                        st.rerun()

                if st.button("❌ رفض", key=f"no_{r['id']}"):
                    field = "status_manager" if u['role']=="Manager" else "status_hr"
                    update_status_db(r['id'], field, "Rejected", note, u['name'])
                    st.rerun()

def my_requests_page():
    st.title("📂 تتبع معاملاتي")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    
    u = st.session_state['user']
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs: st.info("سجلك فارغ."); return
    
    for r in reqs:
        with st.container():
            st.markdown(f"### {r['service_type']} ({r['sub_type'] or '-'})")
            
            # شريط التتبع (Timeline)
            s1 = "step-done" if r['status_manager']=="Approved" else "step-wait"
            s2 = "step-done" if r['status_hr']=="Approved" else ("step-wait" if r['status_manager']=="Approved" else "step")
            final = "✅ معتمد" if r['final_status']=="Approved" else ("❌ مرفوض" if r['final_status']=="Rejected" else "⏳ تحت الإجراء")
            
            st.markdown(f"""
            <span class="{s1}">1. موافقة المدير</span> ➡️ 
            <span class="{s2}">2. الموارد البشرية</span> ➡️ 
            <span class="step-now">{final}</span>
            """, unsafe_allow_html=True)
            
            st.caption(f"تاريخ الطلب: {r['created_at'][:10]}")
            st.divider()

# --- 5. التوجيه ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'

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
