import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="بوابة الخدمات المتكاملة", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; margin-bottom: 10px; cursor: pointer;
    }
    .service-card:hover {
        transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); border-color: #2196f3;
    }
    .status-pending { color: orange; font-weight: bold; }
    .status-approved { color: green; font-weight: bold; }
    .status-rejected { color: red; font-weight: bold; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال وقاعدة البيانات ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds)
        return None
    except: return None

# --- 3. أدوات المدير (إصلاح الأعمدة الجديدة) ---
with st.sidebar.expander("🛠️ أدوات النظام (اضغط هنا لتحديث الأعمدة)"):
    if st.button("تحديث هيكل الإكسل (للإضافات الجديدة)"):
        client = init_connection()
        if client:
            sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
            try:
                try: sh.del_worksheet(sh.worksheet("الطلبات"))
                except: pass
                ws = sh.add_worksheet(title="الطلبات", rows="1000", cols="25")
                # أضفنا أعمدة جديدة: المرفقات، وقت_الموافقة، مدة_الإجراء
                headers = [
                    "رقم_الطلب", "وقت_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم", 
                    "نوع_الخدمة", "التفاصيل", "شرح_الطلب", "المبلغ", "الأيام", 
                    "تاريخ_البداية", "تاريخ_النهاية", "وقت_الاستئذان", 
                    "حالة_الطلب", "رد_المدير", "وقت_الرد", "مدة_الإجراء_ساعة", "المرفقات", "توصية_AI"
                ]
                ws.append_row(headers)
                st.success("✅ تم تحديث الأعمدة لتشمل المرفقات والتحليل الزمني!")
            except: st.error("فشل الاتصال")

# --- 4. دوال البيانات ---
def save_to_sheet(row):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        sh.worksheet("الطلبات").append_row(row)
        return True
    except: return False

def get_all_requests():
    client = init_connection()
    if not client: return pd.DataFrame()
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        data = sh.worksheet("الطلبات").get_all_records()
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def update_request_status(req_id, status, manager_note, manager_name):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات")
        cell = ws.find(str(req_id)) # البحث عن رقم الطلب
        if cell:
            row = cell.row
            # تحديث الحالة (العمود 14)
            ws.update_cell(row, 14, status)
            # تحديث رد المدير (العمود 15)
            ws.update_cell(row, 15, f"{manager_note} (بواسطة: {manager_name})")
            # تحديث وقت الرد (العمود 16)
            reply_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ws.update_cell(row, 16, reply_time)
            
            # حساب مدة الإجراء (التحليل الزمني)
            # نجلب وقت الطلب (العمود 2)
            req_time_str = ws.cell(row, 2).value
            try:
                fmt = "%Y-%m-%d %H:%M:%S"
                t1 = datetime.strptime(req_time_str, fmt)
                t2 = datetime.strptime(reply_time, fmt)
                duration_hours = round((t2 - t1).total_seconds() / 3600, 2)
                ws.update_cell(row, 17, duration_hours) # العمود 17: مدة الإجراء
            except:
                ws.update_cell(row, 17, "خطأ في التنسيق")
                
            return True
    except: return False
    return False

# --- 5. إدارة الجلسة ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'user' not in st.session_state: st.session_state['user'] = None

def login_page():
    st.markdown("<br><br><h1 style='text-align: center; color:#2980b9;'>🔐 بوابة الموظفين</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            uid = st.text_input("رقم الموظف")
            pwd = st.text_input("كلمة المرور", type="password")
            is_manager = st.checkbox("دخول كمدير قسم / مسؤول")
            
            if st.form_submit_button("دخول"):
                # محاكاة الدخول (يمكنك ربطها بالإكسل لاحقاً)
                role = "Manager" if is_manager else "Employee"
                # إذا كان المدير 1001 فهو Admin (يرى كل شيء)، غيره يرى قسمه
                user_dept = "المشتريات" if uid == "1011" else "الموارد البشرية"
                
                st.session_state['user'] = {
                    'رقم الموظف': uid,
                    'اسم الموظف': f"الموظف {uid}",
                    'الهيكل الإداري': user_dept,
                    'الصلاحية': role
                }
                st.session_state['page'] = 'dashboard'
                st.rerun()

# القائمة الجانبية
if st.session_state['user']:
    user = st.session_state['user']
    with st.sidebar:
        st.header(f"👤 {user['اسم الموظف']}")
        st.info(f"الدور: {user['الصلاحية']} | القسم: {user['الهيكل الإداري']}")
        
        st.markdown("---")
        if st.button("🏠 الرئيسية"):
            st.session_state['page'] = 'dashboard'
            st.rerun()
            
        # زر خاص بالمدير فقط
        if user['الصلاحية'] == 'Manager':
            if st.button("✅ اعتماد الطلبات"):
                st.session_state['page'] = 'approvals'
                st.rerun()
                
        if st.button("🚪 تسجيل الخروج"):
            st.session_state['user'] = None
            st.session_state['page'] = 'login'
            st.rerun()

# --- 6. الصفحات ---

# أ. لوحة التحكم
def dashboard_page():
    user = st.session_state['user']
    st.title(f"👋 مرحباً بك في قسم {user['الهيكل الإداري']}")
    
    # لوحة المدير (تنبيهات)
    if user['الصلاحية'] == 'Manager':
        st.warning("🔔 لديك صلاحيات مدير: يرجى مراجعة صفحة 'اعتماد الطلبات' دورياً.")
    
    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم طلب إجازة"): navigate("leave")
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): navigate("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): navigate("loan")
        st.markdown('<div class="service-card"><h3>✈️ الرحلات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب رحلة عمل"): navigate("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"): navigate("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("متابعة سجل الطلبات"):
            st.session_state['page'] = 'my_requests'
            st.rerun()

def navigate(svc):
    st.session_state['service'] = svc
    st.session_state['page'] = 'form'
    st.rerun()

# ب. صفحة اعتماد الطلبات (للمدير) - الجديدة
def approvals_page():
    st.title("✅ لوحة اعتماد الطلبات")
    
    df = get_all_requests()
    if df.empty:
        st.info("لا توجد بيانات.")
        return

    # فلترة: المدير يرى فقط طلبات قسمه، والحالات "تحت المراجعة"
    user_dept = st.session_state['user']['الهيكل الإداري']
    # تحويل القيم لنصوص للمقارنة الآمنة
    pending_reqs = df[
        (df['حالة_الطلب'] == 'تحت المراجعة') & 
        (df['القسم'].astype(str) == str(user_dept))
    ]
    
    if pending_reqs.empty:
        st.success("🎉 لا توجد طلبات معلقة في قسمك.")
        return
        
    st.write(f"يوجد ({len(pending_reqs)}) طلبات بانتظار موافقتك:")
    
    for index, row in pending_reqs.iterrows():
        with st.expander(f"طلب #{row['رقم_الطلب']} | {row['اسم_الموظف']} ({row['نوع_الخدمة']})", expanded=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**التفاصيل:** {row['شرح_الطلب']}")
                st.write(f"**التاريخ:** {row['وقت_الطلب']}")
                if row['المرفقات']:
                    st.info(f"📎 مرفق: {row['المرفقات']}")
                st.caption(f"🤖 تحليل AI: {row['توصية_AI']}")
            
            with c2:
                note = st.text_input("ملاحظات المدير", key=f"note_{row['رقم_الطلب']}")
                col_a, col_r = st.columns(2)
                if col_a.button("✅ موافقة", key=f"app_{row['رقم_الطلب']}"):
                    if update_request_status(row['رقم_الطلب'], "مقبول", note, st.session_state['user']['اسم_الموظف']):
                        st.success("تم الاعتماد!")
                        time.sleep(1)
                        st.rerun()
                
                if col_r.button("❌ رفض", key=f"rej_{row['رقم_الطلب']}"):
                    if update_request_status(row['رقم_الطلب'], "مرفوض", note, st.session_state['user']['اسم_الموظف']):
                        st.error("تم الرفض.")
                        time.sleep(1)
                        st.rerun()

# ج. صفحة متابعة الطلبات (للموظف)
def my_requests_page():
    st.title("📂 سجل طلباتي")
    if st.button("🔙 عودة"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    df = get_all_requests()
    if not df.empty:
        # فلترة طلبات الموظف الحالي
        my_df = df[df['رقم_الموظف'].astype(str) == str(st.session_state['user']['رقم الموظف'])]
        if not my_df.empty:
            # عرض الأعمدة المهمة بما فيها مدة الإجراء
            cols = ['رقم_الطلب', 'نوع_الخدمة', 'حالة_الطلب', 'رد_المدير', 'وقت_الرد', 'مدة_الإجراء_ساعة']
            valid_cols = [c for c in cols if c in my_df.columns]
            st.dataframe(my_df[valid_cols], use_container_width=True, hide_index=True)
        else:
            st.info("ليس لديك طلبات.")
    else:
        st.info("جاري تحميل البيانات...")

# د. صفحة النماذج (مع زر الرفع والوقت التلقائي)
def form_page():
    svc = st.session_state['service']
    if st.button("🔙 إلغاء"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    st.write("---")
    
    # حقل المرفقات (مشترك للكل)
    uploaded_file = st.file_uploader("📎 إرفاق ملف/صورة (اختياري)", type=['png', 'jpg', 'pdf'])
    file_name = uploaded_file.name if uploaded_file else ""

    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        with st.form("f"):
            t = st.selectbox("النوع", ["سنوية", "اضطرارية"])
            c1,c2 = st.columns(2)
            d1 = c1.date_input("من")
            d2 = c2.date_input("إلى")
            days = st.number_input("الأيام", 1)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("إجازة", t, rsn, 0, days, file_name, d1, d2)

    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        with st.form("f"):
            amt = st.number_input("المبلغ", 500)
            m = st.slider("أشهر السداد", 1, 12, 3)
            rsn = st.text_area("الغرض")
            if st.form_submit_button("إرسال"): submit("سلفة", f"سداد {m} أشهر", rsn, amt, 0, file_name)

    elif svc == 'perm':
        st.header("⏱️ طلب استئذان")
        with st.form("f"):
            d = st.date_input("التاريخ")
            c1,c2 = st.columns(2)
            t1 = c1.time_input("من")
            t2 = c2.time_input("إلى")
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("استئذان", "ساعي", rsn, 0, 0, file_name, d, d, f"{t1}-{t2}")

    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        with st.form("f"):
            it = st.text_input("المادة")
            pr = st.number_input("السعر التقريبي", 0)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("مشتريات", it, rsn, pr, 0, file_name)

    elif svc == 'travel':
        st.header("✈️ رحلة عمل")
        with st.form("f"):
            dst = st.text_input("الوجهة")
            c1,c2 = st.columns(2)
            d1 = c1.date_input("ذهاب")
            d2 = c2.date_input("عودة")
            rsn = st.text_area("الهدف")
            if st.form_submit_button("إرسال"): submit("رحلة عمل", dst, rsn, 0, (d2-d1).days, file_name, d1, d2)

def submit(srv, sub, det, amt, days, fname, sd="-", ed="-", tm="-"):
    user = st.session_state['user']
    # وقت الطلب أوتوماتيك
    req_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    row = [
        int(time.time()), req_time, user['رقم الموظف'], user['اسم الموظف'], 
        user['الهيكل الإداري'], srv, sub, det, amt, days, str(sd), str(ed), str(tm), 
        "تحت المراجعة", "-", "-", "-", fname, "جاري التحليل..."
    ]
    if save_to_sheet(row):
        st.balloons()
        st.success("✅ تم إرسال الطلب والمرفقات!")
        time.sleep(1.5)
        st.session_state['page'] = 'dashboard'
        st.rerun()
    else:
        st.error("فشل الحفظ، تأكد من تحديث الأعمدة من القائمة الجانبية.")

# --- 7. الموجه الرئيسي ---
if st.session_state['page'] == 'login':
    login_page()
elif st.session_state['page'] == 'dashboard':
    dashboard_page()
elif st.session_state['page'] == 'form':
    form_page()
elif st.session_state['page'] == 'approvals':
    approvals_page()
elif st.session_state['page'] == 'my_requests':
    my_requests_page()
