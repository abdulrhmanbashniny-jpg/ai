import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات النظام والتصميم ---
st.set_page_config(page_title="HR CRM Enterprise", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تحسينات بصرية احترافية */
    .main { background-color: #f4f6f9; }
    .service-card {
        background-color: white; padding: 25px; border-radius: 15px;
        border: 1px solid #e1e4e8; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: 0.3s;
        cursor: pointer; margin-bottom: 15px;
    }
    .service-card:hover {
        transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        border-color: #3498db;
    }
    .status-step {
        display: inline-block; padding: 5px 10px; border-radius: 20px;
        font-size: 0.8em; font-weight: bold; margin: 2px;
    }
    .pending { background-color: #f39c12; color: white; }
    .approved { background-color: #27ae60; color: white; }
    .rejected { background-color: #c0392b; color: white; }
    
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 2. نواة الاتصال (Backend Core) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds)
        return None
    except: return None

# --- 3. محرك التحديث الذكي (Database Migration) ---
def smart_db_migration():
    client = init_connection()
    if not client: return False, "فشل الاتصال"
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        try: ws = sh.worksheet("الطلبات_V2") # نستخدم ورقة جديدة للإصدار 2
        except: ws = sh.add_worksheet("الطلبات_V2", 1000, 30)
        
        # الأعمدة الشاملة للنظام الجديد
        columns = [
            "رقم_الطلب", "وقت_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم", "المسمى_الوظيفي",
            "نوع_الخدمة", "التفاصيل", "شرح_الطلب", "المرفقات",
            "المبلغ", "الأيام", "تاريخ_البداية", "تاريخ_النهاية",
            # سير العمل (Workflow)
            "حالة_المشرف", "ملاحظات_المشرف", "وقت_المشرف", "اسم_المشرف",
            "حالة_المدير", "ملاحظات_المدير", "وقت_المدير", "اسم_المدير",
            "حالة_HR", "ملاحظات_HR", "وقت_HR", "اسم_HR",
            "الحالة_النهائية", "توصية_AI", "مدة_الإجراء_الكامل"
        ]
        
        current = ws.row_values(1)
        if current != columns:
            ws.clear()
            ws.append_row(columns)
            return True, "تم بناء قاعدة البيانات V2 بنجاح!"
        return True, "قاعدة البيانات محدثة."
    except Exception as e: return False, str(e)

# --- 4. محرك البيانات وسير العمل ---
def submit_new_request(data):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات_V2")
        
        # تجهيز الصف (تحويل القاموس إلى قائمة حسب الترتيب)
        headers = ws.row_values(1)
        row = [str(data.get(h, "-")) for h in headers]
        ws.append_row(row)
        return True
    except: return False

def get_requests_df():
    client = init_connection()
    if not client: return pd.DataFrame()
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        data = sh.worksheet("الطلبات_V2").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def process_approval(req_id, role, status, note, user_name):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات_V2")
        cell = ws.find(str(req_id))
        if cell:
            r = cell.row
            headers = ws.row_values(1)
            
            # تحديث حقول المرحلة الحالية
            mapping = {
                "Supervisor": ["حالة_المشرف", "ملاحظات_المشرف", "وقت_المشرف", "اسم_المشرف"],
                "Manager": ["حالة_المدير", "ملاحظات_المدير", "وقت_المدير", "اسم_المدير"],
                "HR": ["حالة_HR", "ملاحظات_HR", "وقت_HR", "اسم_HR"]
            }
            
            fields = mapping.get(role)
            if fields:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # تحديث القيم
                for i, val in enumerate([status, note, ts, user_name]):
                    if fields[i] in headers:
                        ws.update_cell(r, headers.index(fields[i])+1, val)
                
                # تحديث الحالة النهائية (Logic)
                # إذا رفض أي أحد -> مرفوض نهائي
                if status == "مرفوض":
                    ws.update_cell(r, headers.index("الحالة_النهائية")+1, "مرفوض")
                
                # إذا وافق HR -> مقبول نهائي
                elif role == "HR" and status == "مقبول":
                    ws.update_cell(r, headers.index("الحالة_النهائية")+1, "مقبول")
                
                # إذا وافق المشرف/المدير -> تحويل للمرحلة التالية
                else:
                    next_stage = "بانتظار المدير" if role == "Supervisor" else "بانتظار HR"
                    ws.update_cell(r, headers.index("الحالة_النهائية")+1, next_stage)
                    
            return True
    except: return False
    return False

# --- 5. واجهات المستخدم ---

# أ. تسجيل الدخول (محاكاة للأدوار)
def login_system():
    st.markdown("<br><h1 style='text-align: center; color:#2c3e50;'>🔐 بوابة الموارد البشرية</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            uid = st.text_input("رقم الموظف")
            pwd = st.text_input("كلمة المرور", type="password")
            role = st.selectbox("الدخول بصلاحية:", ["موظف (Employee)", "مشرف (Supervisor)", "مدير قسم (Manager)", "مدير موارد بشرية (HR)"])
            
            if st.form_submit_button("دخول"):
                # محاكاة بيانات المستخدم
                role_map = {"موظف (Employee)": "Employee", "مشرف (Supervisor)": "Supervisor", 
                           "مدير قسم (Manager)": "Manager", "مدير موارد بشرية (HR)": "HR"}
                
                st.session_state['user'] = {
                    'uid': uid,
                    'name': f"المستخدم {uid}",
                    'dept': "المشتريات", # افتراضي
                    'role': role_map[role]
                }
                st.session_state['page'] = 'home'
                st.rerun()

# ب. لوحة التحكم الرئيسية
def home_page():
    u = st.session_state['user']
    st.title(f"مرحباً، {u['name']}")
    st.caption(f"الدور الحالي: {u['role']} | القسم: {u['dept']}")
    
    # تنبيهات المهام (لأصحاب الصلاحية)
    if u['role'] in ['Supervisor', 'Manager', 'HR']:
        st.info(f"🔔 لديك مهام اعتماد في لوحة {u['role']}. انتقل لصفحة 'المهام' للمراجعة.")

    st.write("---")
    
    # قائمة الخدمات (Grid)
    services = [
        ("🌴 إجازات", "leave"), ("💰 سلف وتعويضات", "loan"), ("🛒 طلبات شراء", "purchase"),
        ("✈️ انتداب وسفر", "travel"), ("⏱️ استئذان", "perm"), ("📄 خطابات وتعريف", "letter"),
        ("⚠️ شكاوى", "complaint"), ("🎓 تدريب", "training")
    ]
    
    cols = st.columns(4)
    for i, (label, key) in enumerate(services):
        with cols[i % 4]:
            st.markdown(f'<div class="service-card"><h3>{label}</h3></div>', unsafe_allow_html=True)
            if st.button(f"تقديم {label.split()[1]}", key=key):
                st.session_state['service'] = key
                st.session_state['page'] = 'form'
                st.rerun()

# ج. صفحة النماذج الذكية
def form_engine():
    srv = st.session_state['service']
    if st.button("🔙 عودة"): st.session_state['page']='home'; st.rerun()
    
    st.header(f"تقديم طلب جديد: {srv}")
    
    # الحقول المشتركة
    up_file = st.file_uploader("📎 المرفقات")
    fname = up_file.name if up_file else ""
    
    with st.form("universal_form"):
        # حقول ديناميكية حسب الخدمة
        subtype = st.text_input("نوع الطلب الفرعي")
        details = st.text_area("التفاصيل / المبررات")
        
        c1, c2 = st.columns(2)
        amt = c1.number_input("المبلغ (إن وجد)", 0)
        days = c2.number_input("عدد الأيام (إن وجد)", 0)
        
        d1 = c1.date_input("تاريخ البداية")
        d2 = c2.date_input("تاريخ النهاية")
        
        if st.form_submit_button("🚀 إرسال الطلب"):
            u = st.session_state['user']
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # منطق الـ AI البسيط
            ai_rec = "مقبول مبدئياً"
            if srv == "leave" and days > 30: ai_rec = "مرفوض: الرصيد لا يسمح"
            if srv == "loan" and amt > 5000: ai_rec = "يحتاج موافقة مالية خاصة"

            data = {
                "رقم_الطلب": int(time.time()), "وقت_الطلب": ts,
                "رقم_الموظف": u['uid'], "اسم_الموظف": u['name'], "القسم": u['dept'],
                "نوع_الخدمة": srv, "التفاصيل": subtype, "شرح_الطلب": details,
                "المرفقات": fname, "المبلغ": amt, "الأيام": days,
                "تاريخ_البداية": str(d1), "تاريخ_النهاية": str(d2),
                "حالة_المشرف": "بانتظار المراجعة", "حالة_المدير": "-", "حالة_HR": "-",
                "الحالة_النهائية": "بانتظار المشرف", "توصية_AI": ai_rec
            }
            
            if submit_new_request(data):
                st.success("✅ تم إرسال الطلب وبدء سير العمل (Workflow)!")
                time.sleep(1.5)
                st.session_state['page'] = 'home'
                st.rerun()
            else:
                st.error("فشل الحفظ! تأكد من تحديث قاعدة البيانات.")

# د. مركز المهام (Approvals Center) - موحد لكل الأدوار
def tasks_center():
    u = st.session_state['user']
    role = u['role']
    st.title(f"📋 مركز مهام: {role}")
    
    df = get_requests_df()
    if df.empty: st.info("لا توجد طلبات."); return
    
    # فلترة الطلبات حسب الدور
    if role == "Supervisor":
        pending = df[df['حالة_المشرف'] == 'بانتظار المراجعة']
    elif role == "Manager":
        # المدير يرى فقط ما وافق عليه المشرف
        pending = df[(df['حالة_المشرف'] == 'مقبول') & (df['حالة_المدير'] == '-')]
    elif role == "HR":
        # الـ HR يرى ما وافق عليه المدير
        pending = df[(df['حالة_المدير'] == 'مقبول') & (df['حالة_HR'] == '-')]
    else:
        st.error("ليس لديك صلاحية اعتماد."); return

    if pending.empty:
        st.success("🎉 لا توجد مهام معلقة لديك."); return
        
    for i, row in pending.iterrows():
        with st.expander(f"{row['نوع_الخدمة']} | {row['اسم_الموظف']} (#{row['رقم_الطلب']})", expanded=True):
            c1, c2 = st.columns([2,1])
            with c1:
                st.write(f"**التفاصيل:** {row['شرح_الطلب']}")
                st.caption(f"🤖 توصية النظام: {row['توصية_AI']}")
                # عرض سير العمل السابق
                if role != "Supervisor":
                    st.info(f"✅ موافقة المشرف: {row['ملاحظات_المشرف']}")
                if role == "HR":
                    st.success(f"✅ موافقة المدير: {row['ملاحظات_المدير']}")
            
            with c2:
                note = st.text_input("ملاحظاتك", key=f"n_{row['رقم_الطلب']}")
                if st.button("✅ اعتماد", key=f"ok_{row['رقم_الطلب']}"):
                    process_approval(row['رقم_الطلب'], role, "مقبول", note, u['name'])
                    st.rerun()
                if st.button("❌ رفض", key=f"no_{row['رقم_الطلب']}"):
                    process_approval(row['رقم_الطلب'], role, "مرفوض", note, u['name'])
                    st.rerun()

# هـ. صفحة تتبع الطلبات (Timeline)
def tracking_page():
    st.title("🔍 تتبع طلباتي")
    if st.button("🔙 عودة"): st.session_state['page']='home'; st.rerun()
    
    df = get_requests_df()
    if df.empty: return
    
    # فلترة طلباتي
    my_reqs = df[df['رقم_الموظف'].astype(str) == str(st.session_state['user']['uid'])]
    
    for i, row in my_reqs.iterrows():
        with st.container():
            st.markdown(f"### {row['نوع_الخدمة']} - {row['الحالة_النهائية']}")
            # رسم شريط الحالة
            s1 = "✅" if row['حالة_المشرف'] == 'مقبول' else ("⏳" if row['حالة_المشرف'] == 'بانتظار المراجعة' else "❌")
            s2 = "✅" if row['حالة_المدير'] == 'مقبول' else ("⏳" if row['حالة_المشرف'] == 'مقبول' and row['حالة_المدير'] == '-' else "⚪")
            s3 = "✅" if row['حالة_HR'] == 'مقبول' else ("⏳" if row['حالة_المدير'] == 'مقبول' and row['حالة_HR'] == '-' else "⚪")
            
            st.markdown(f"""
            1. مشرف: {s1} &nbsp;&nbsp;➡️&nbsp;&nbsp; 
            2. مدير: {s2} &nbsp;&nbsp;➡️&nbsp;&nbsp; 
            3. موارد بشرية: {s3}
            """)
            st.caption(f"آخر تحديث: {row['الحالة_النهائية']}")
            st.divider()

# --- 6. الموجه الرئيسي (Router) ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'

# القائمة الجانبية العامة
with st.sidebar:
    if st.session_state.get('user'):
        st.header(st.session_state['user']['name'])
        if st.button("🏠 الرئيسية"): st.session_state['page']='home'; st.rerun()
        if st.button("📂 تتبع طلباتي"): st.session_state['page']='track'; st.rerun()
        
        role = st.session_state['user']['role']
        if role in ['Supervisor', 'Manager', 'HR']:
            if st.button(f"⚡ مهام {role}"): st.session_state['page']='tasks'; st.rerun()
            
        st.markdown("---")
        if st.button("🚪 خروج"): st.session_state.clear(); st.rerun()
    
    # أدوات الأدمن (دائماً موجودة في الأسفل للصيانة)
    with st.expander("⚙️ إعدادات النظام"):
        if st.button("تحديث هيكل الإكسل الشامل (V2)"):
            ok, msg = smart_db_migration()
            if ok: st.success(msg)
            else: st.error(msg)

# التوجيه للصفحات
if st.session_state['page'] == 'login': login_system()
elif st.session_state['page'] == 'home': home_page()
elif st.session_state['page'] == 'form': form_engine()
elif st.session_state['page'] == 'tasks': tasks_center()
elif st.session_state['page'] == 'track': tracking_page()
