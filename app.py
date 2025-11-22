import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات الصفحة والتصميم (CSS) ---
st.set_page_config(page_title="بوابة الخدمات الذكية", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تنسيق البطاقات */
    .service-card {
        background-color: white; padding: 20px; border-radius: 12px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s; margin-bottom: 10px;
    }
    .service-card:hover {
        transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); border-color: #2196f3;
    }
    /* تنسيق العناوين والأزرار */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 50px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بقاعدة البيانات (Google Sheets) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds)
        return None
    except: return None

# --- 3. أدوات المدير (لإصلاح الإكسل) ---
# تظهر فقط إذا دخلت، لكننا نضعها هنا كأداة مساعدة
with st.sidebar.expander("🛠️ أدوات النظام (إصلاح البيانات)"):
    if st.button("تهيئة ورقة الطلبات من جديد"):
        client = init_connection()
        if client:
            sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
            try:
                try: sh.del_worksheet(sh.worksheet("الطلبات"))
                except: pass
                ws = sh.add_worksheet(title="الطلبات", rows="1000", cols="20")
                headers = ["رقم_الطلب", "تاريخ_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم", "نوع_الخدمة", "التفاصيل_الفرعية", "شرح_الطلب", "المبلغ_المالي", "المدة_بالأيام", "تاريخ_البداية", "تاريخ_النهاية", "وقت_الاستئذان", "حالة_الطلب", "رد_المدير", "توصية_AI"]
                ws.append_row(headers)
                st.success("✅ تم إصلاح ملف الإكسل بنجاح!")
            except: st.error("فشل الاتصال بالملف")

# --- 4. دوال التعامل مع البيانات ---
def save_to_sheet(row):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        sh.worksheet("الطلبات").append_row(row)
        return True
    except: return False

def get_my_requests(emp_id):
    client = init_connection()
    if not client: return pd.DataFrame()
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        data = sh.worksheet("الطلبات").get_all_records()
        df = pd.DataFrame(data)
        return df[df['رقم_الموظف'].astype(str) == str(emp_id)]
    except: return pd.DataFrame()

def check_login(uid, pwd):
    # هنا يمكنك وضع التحقق الحقيقي (مطابقة مع ورقة الموظفين)
    # حالياً سنسمح بدخول أي شخص للتجربة، ونحفظ رقمه
    return {
        'رقم الموظف': uid,
        'اسم الموظف': f"الموظف {uid}", # يمكن جلبه من الإكسل لاحقاً
        'الهيكل الإداري': 'عام'
    }

# --- 5. إدارة الجلسة ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'service' not in st.session_state: st.session_state['service'] = None
if 'user' not in st.session_state: st.session_state['user'] = None

# القائمة الجانبية (تظهر فقط بعد الدخول)
if st.session_state['user']:
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
        st.header(f"👤 {st.session_state['user']['اسم الموظف']}")
        st.caption(f"القسم: {st.session_state['user']['الهيكل الإداري']}")
        st.markdown("---")
        if st.button("🏠 الرئيسية"):
            st.session_state['page'] = 'dashboard'
            st.rerun()
        if st.button("🚪 تسجيل الخروج"):
            st.session_state['user'] = None
            st.session_state['page'] = 'login'
            st.rerun()

# --- 6. الصفحات (الشاشات) ---

# أ. شاشة تسجيل الدخول
def login_page():
    st.markdown("<br><br><h1 style='text-align: center; color:#2980b9;'>🔐 بوابة الموظفين</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            uid = st.text_input("رقم الموظف", placeholder="أدخل رقمك الوظيفي")
            pwd = st.text_input("كلمة المرور", type="password", placeholder="••••••")
            if st.form_submit_button("تسجيل الدخول"):
                if uid and pwd:
                    user_data = check_login(uid, pwd)
                    st.session_state['user'] = user_data
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else:
                    st.error("الرجاء إدخال البيانات")

# ب. لوحة الخدمات (Dashboard)
def dashboard_page():
    st.title("👋 أهلاً بك، اختر الخدمة:")
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

# ج. صفحة متابعة الطلبات
def my_requests_page():
    st.title("📂 سجل طلباتي السابقة")
    if st.button("🔙 عودة"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    with st.spinner("جاري جلب البيانات..."):
        df = get_my_requests(st.session_state['user']['رقم الموظف'])
    
    if df.empty:
        st.info("ليس لديك أي طلبات سابقة.")
    else:
        # عرض الأعمدة المهمة فقط
        cols = ['رقم_الطلب', 'تاريخ_الطلب', 'نوع_الخدمة', 'التفاصيل_الفرعية', 'حالة_الطلب', 'رد_المدير']
        valid_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[valid_cols], use_container_width=True, hide_index=True)

# د. صفحة النماذج (Forms)
def form_page():
    svc = st.session_state['service']
    
    if st.button("🔙 إلغاء وعودة"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
        
    st.write("---")
    
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        with st.form("f_leave"):
            t = st.selectbox("النوع", ["سنوية", "اضطرارية"])
            c1,c2 = st.columns(2)
            d1 = c1.date_input("من")
            d2 = c2.date_input("إلى")
            days = st.number_input("الأيام", 1)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("إجازة", t, rsn, 0, days, d1, d2)

    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        with st.form("f_loan"):
            amt = st.number_input("المبلغ", 500)
            mon = st.slider("أشهر السداد", 1, 12, 3)
            rsn = st.text_area("الغرض")
            if st.form_submit_button("إرسال"): submit("سلفة", f"سداد {mon} أشهر", rsn, amt, 0)

    elif svc == 'perm':
        st.header("⏱️ طلب استئذان")
        with st.form("f_perm"):
            d = st.date_input("التاريخ")
            c1,c2 = st.columns(2)
            t1 = c1.time_input("من")
            t2 = c2.time_input("إلى")
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("استئذان", "ساعي", rsn, 0, 0, d, d, f"{t1}-{t2}")

    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        with st.form("f_pur"):
            it = st.text_input("المادة")
            pr = st.number_input("السعر التقريبي", 0)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("مشتريات", it, rsn, pr, 0)

    elif svc == 'travel':
        st.header("✈️ رحلة عمل")
        with st.form("f_trav"):
            dst = st.text_input("الوجهة")
            c1,c2 = st.columns(2)
            d1 = c1.date_input("ذهاب")
            d2 = c2.date_input("عودة")
            rsn = st.text_area("الهدف")
            if st.form_submit_button("إرسال"): submit("رحلة عمل", dst, rsn, 0, (d2-d1).days, d1, d2)

# هـ. دالة الإرسال الموحدة
def submit(srv, sub, det, amt, days, sd="-", ed="-", tm="-"):
    user = st.session_state['user']
    row = [
        int(time.time()), str(datetime.now().date()), user['رقم الموظف'], user['اسم الموظف'], 
        user['الهيكل الإداري'], srv, sub, det, amt, days, str(sd), str(ed), str(tm), 
        "تحت المراجعة", "-", "جاري التحليل..."
    ]
    if save_to_sheet(row):
        st.balloons()
        st.success("✅ تم إرسال الطلب بنجاح!")
        time.sleep(1.5)
        st.session_state['page'] = 'dashboard'
        st.rerun()
    else:
        st.error("فشل الحفظ، تأكد من إصلاح ملف الإكسل من القائمة الجانبية.")

# --- 7. الموجه الرئيسي (Router) ---
if st.session_state['page'] == 'login':
    login_page()
elif st.session_state['page'] == 'dashboard':
    if st.session_state['user']: dashboard_page()
    else: st.session_state['page'] = 'login'; st.rerun()
elif st.session_state['page'] == 'form':
    form_page()
elif st.session_state['page'] == 'my_requests':
    my_requests_page()
