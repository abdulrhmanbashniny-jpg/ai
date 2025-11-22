import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="بوابة الخدمات الذكية", layout="wide", page_icon="🏢")

# CSS لتحسين المظهر
st.markdown("""
<style>
    .service-card {
        background-color: white; padding: 20px; border-radius: 10px;
        border: 1px solid #ddd; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: 0.3s;
    }
    .service-card:hover {
        transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); border-color: #2196f3;
    }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: bold; }
    
    /* تلوين حالات الطلب */
    .status-pending { color: #f39c12; font-weight: bold; }
    .status-approved { color: #27ae60; font-weight: bold; }
    .status-rejected { color: #c0392b; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            return gspread.authorize(creds)
        return None
    except: return None

# --- 3. زر إصلاح الإكسل (يظهر للمدير فقط) ---
with st.sidebar.expander("🛠️ أدوات المدير (إصلاح ملف البيانات)"):
    if st.button("إعادة تهيئة ورقة الطلبات"):
        client = init_connection()
        if client:
            sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
            try:
                try: sh.del_worksheet(sh.worksheet("الطلبات"))
                except: pass
                ws = sh.add_worksheet(title="الطلبات", rows="1000", cols="20")
                headers = ["رقم_الطلب", "تاريخ_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم", "نوع_الخدمة", "التفاصيل_الفرعية", "شرح_الطلب", "المبلغ_المالي", "المدة_بالأيام", "تاريخ_البداية", "تاريخ_النهاية", "وقت_الاستئذان", "حالة_الطلب", "رد_المدير", "توصية_AI"]
                ws.append_row(headers)
                st.success("تم الإصلاح!")
            except: st.error("فشل الإصلاح")

# --- 4. دوال البيانات ---
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
        ws = sh.worksheet("الطلبات")
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        # فلترة طلبات الموظف الحالي فقط
        # (نحول العمود لنص لضمان المطابقة)
        return df[df['رقم_الموظف'].astype(str) == str(emp_id)]
    except: return pd.DataFrame()

# --- 5. إدارة الجلسة (تسجيل الدخول/الخروج) ---
if 'page' not in st.session_state: st.session_state['page'] = 'dashboard'
if 'service' not in st.session_state: st.session_state['service'] = None
if 'user' not in st.session_state:
    # مستخدم افتراضي للتجربة (تستطيع تغييره لاحقاً لصفحة دخول حقيقية)
    st.session_state['user'] = {'رقم الموظف': '1011', 'اسم الموظف': 'موظف المشتريات 11', 'الهيكل الإداري': 'المشتريات'}

# زر تسجيل الخروج في القائمة الجانبية
with st.sidebar:
    st.header(f"👤 {st.session_state['user']['اسم الموظف']}")
    st.caption(f"القسم: {st.session_state['user']['الهيكل الإداري']}")
    if st.button("🚪 تسجيل الخروج"):
        # هنا نعيد المستخدم لصفحة الدخول (أو نعيد تحميل الصفحة)
        st.session_state['user'] = {'رقم الموظف': '000', 'اسم الموظف': 'Guest', 'الهيكل الإداري': ''}
        st.rerun()

# --- 6. الصفحات ---

# أ. لوحة التحكم
def dashboard():
    st.title("👋 أهلاً بك في البوابة الرقمية")
    st.write("---")
    
    c1, c2, c3 = st.columns(3)
    
    # الصف الأول
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب إجازة"): navigate("leave")
        
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): navigate("purchase")

    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): navigate("loan")
        
        st.markdown('<div class="service-card"><h3>✈️ الرحلات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب رحلة"): navigate("travel")

    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("طلب استئذان"): navigate("perm")
        
        # زر طلباتي المحدث
        st.markdown('<div class="service-card" style="border-color: #f39c12;"><h3>📂 طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("متابعة سجل الطلبات"): 
            st.session_state['page'] = 'my_requests' # توجيه لصفحة الطلبات
            st.rerun()

def navigate(service_name):
    st.session_state['service'] = service_name
    st.session_state['page'] = 'form'
    st.rerun()

# ب. صفحة متابعة الطلبات (الجديدة)
def my_requests_page():
    st.title("📂 سجل طلباتي السابقة")
    if st.button("🔙 عودة للرئيسية"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    # جلب البيانات
    with st.spinner("جاري جلب البيانات من السحابة..."):
        df = get_my_requests(st.session_state['user']['رقم الموظف'])
    
    if df.empty:
        st.info("لا توجد طلبات سابقة مسجلة لك.")
    else:
        # عرض جدول أنيق
        # نختار الأعمدة المهمة فقط للعرض
        cols_to_show = ['رقم_الطلب', 'تاريخ_الطلب', 'نوع_الخدمة', 'التفاصيل_الفرعية', 'حالة_الطلب', 'رد_المدير']
        # التحقق من وجود الأعمدة قبل العرض لتجنب الأخطاء
        valid_cols = [c for c in cols_to_show if c in df.columns]
        
        st.dataframe(
            df[valid_cols], 
            use_container_width=True,
            hide_index=True
        )

# ج. صفحة النماذج (Forms) - نفس السابقة
def form_page():
    svc = st.session_state['service']
    if st.button("🔙 إلغاء وعودة"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    st.write("---")
    
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        with st.form("f"):
            t = st.selectbox("النوع", ["سنوية", "اضطرارية"])
            c1,c2 = st.columns(2)
            d1 = c1.date_input("من")
            d2 = c2.date_input("إلى")
            days = st.number_input("الأيام", 1)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("إجازة", t, rsn, 0, days, d1, d2)
            
    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        with st.form("f"):
            amt = st.number_input("المبلغ", 500)
            m = st.slider("أشهر السداد", 1, 12, 3)
            rsn = st.text_area("الغرض")
            if st.form_submit_button("إرسال"): submit("سلفة", f"سداد {m} أشهر", rsn, amt, 0)

    elif svc == 'perm':
        st.header("⏱️ طلب استئذان")
        with st.form("f"):
            d = st.date_input("التاريخ")
            c1,c2 = st.columns(2)
            t1 = c1.time_input("من")
            t2 = c2.time_input("إلى")
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("استئذان", "ساعي", rsn, 0, 0, d, d, f"{t1}-{t2}")

    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        with st.form("f"):
            it = st.text_input("المادة")
            pr = st.number_input("السعر التقريبي", 0)
            rsn = st.text_area("السبب")
            if st.form_submit_button("إرسال"): submit("مشتريات", it, rsn, pr, 0)

    elif svc == 'travel':
        st.header("✈️ رحلة عمل")
        with st.form("f"):
            dst = st.text_input("الوجهة")
            c1,c2 = st.columns(2)
            d1 = c1.date_input("ذهاب")
            d2 = c2.date_input("عودة")
            rsn = st.text_area("الهدف")
            if st.form_submit_button("إرسال"): submit("رحلة عمل", dst, rsn, 0, (d2-d1).days, d1, d2)

def submit(srv, sub, det, amt, days, sd="-", ed="-", tm="-"):
    user = st.session_state['user']
    row = [
        int(time.time()), str(datetime.now().date()), user['رقم الموظف'], user['اسم الموظف'], 
        user['الهيكل الإداري'], srv, sub, det, amt, days, str(sd), str(ed), str(tm), 
        "تحت المراجعة", "-", "جاري التحليل..."
    ]
    if save_to_sheet(row):
        st.success("✅ تم الإرسال!")
        time.sleep(1)
        st.session_state['page'] = 'dashboard'
        st.rerun()
    else:
        st.error("فشل الحفظ، تأكد من إصلاح ملف الإكسل من القائمة الجانبية")

# --- 7. التوجيه ---
if st.session_state['page'] == 'dashboard': dashboard()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
