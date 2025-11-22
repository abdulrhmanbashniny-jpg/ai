import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات التصميم (CSS الاحترافي) ---
st.set_page_config(page_title="بوابة الموظف الذكية", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تحسين البطاقات في القائمة الرئيسية */
    .service-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e9ecef;
        text-align: center;
        transition: 0.3s;
        cursor: pointer;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .service-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        background-color: #e3f2fd;
        border-color: #2196f3;
    }
    h3 {color: #2c3e50;}
    
    /* زر الرجوع */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. دوال الاتصال (نفس الكود الذي يعمل لديك) ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # قراءة المفتاح من Secrets
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        else:
            return None
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ خطأ اتصال: {e}")
        return None

def save_to_google_sheet(data):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        # التأكد من وجود ورقة الطلبات
        try:
            ws = sh.worksheet("الطلبات")
        except:
            ws = sh.add_worksheet(title="الطلبات", rows="1000", cols="20")
            ws.append_row(["id", "emp_id", "name", "type", "details", "amount", "days", "date", "status"])
        
        ws.append_row(data)
        return True
    except Exception as e:
        st.error(f"فشل الحفظ: {e}")
        return False

# --- 3. إدارة الصفحات (Navigation) ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'current_service' not in st.session_state: st.session_state['current_service'] = None

def navigate_to(page, service=None):
    st.session_state['page'] = page
    if service: st.session_state['current_service'] = service
    st.rerun()

# --- 4. الصفحات (الشاشات) ---

# أ. الشاشة الرئيسية (لوحة الخدمات)
def dashboard_page():
    st.title("🏢 الخدمات الإلكترونية")
    st.markdown("---")
    
    # تصميم الشبكة (Grid) للخدمات
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("🌴 **الإجازات**")
        if st.button("تقديم طلب إجازة", key="btn_leave"):
            navigate_to("service_form", "leave")
            
        st.write("") # مسافة
        st.warning("🛒 **المشتريات**")
        if st.button("طلب مشتريات", key="btn_purchase"):
            navigate_to("service_form", "purchase")

    with col2:
        st.success("💰 **السلف والقروض**")
        if st.button("طلب سلفة مالية", key="btn_loan"):
            navigate_to("service_form", "loan")
            
        st.write("")
        st.error("✈️ **رحلات العمل**")
        if st.button("طلب رحلة عمل", key="btn_travel"):
            navigate_to("service_form", "travel")

    with col3:
        st.info("⏱️ **الاستئذان**")
        if st.button("طلب استئذان", key="btn_permission"):
            navigate_to("service_form", "permission")
            
        st.write("")
        if st.button("📂 سجل طلباتي السابق", key="btn_history"):
            navigate_to("history")

# ب. شاشة النموذج الموحد (ديناميكية حسب الخدمة)
def service_form_page():
    service = st.session_state['current_service']
    
    # زر الرجوع في الأعلى
    if st.button("🔙 العودة للقائمة الرئيسية"):
        navigate_to("dashboard")
    
    st.markdown("---")
    
    # 1. نموذج الإجازات
    if service == "leave":
        st.header("🌴 تقديم طلب إجازة")
        with st.form("leave_form"):
            l_type = st.selectbox("نوع الإجازة", ["سنوية", "اضطرارية", "مرضية", "بدون راتب"])
            c1, c2 = st.columns(2)
            start_date = c1.date_input("تاريخ البداية")
            end_date = c2.date_input("تاريخ النهاية")
            days = st.number_input("عدد الأيام", min_value=1)
            reason = st.text_area("سبب الإجازة / الملاحظات")
            
            if st.form_submit_button("إرسال طلب الإجازة"):
                submit_request("إجازة", l_type, reason, 0, days)

    # 2. نموذج السلف
    elif service == "loan":
        st.header("💰 تقديم طلب سلفة")
        with st.form("loan_form"):
            amount = st.number_input("المبلغ المطلوب (ريال)", min_value=500, step=500)
            months = st.slider("مدة السداد (أشهر)", 1, 12, 3)
            reason = st.text_area("الغرض من السلفة")
            
            if st.form_submit_button("إرسال طلب السلفة"):
                submit_request("سلفة", f"سداد على {months} أشهر", reason, amount, 0)

    # 3. نموذج الاستئذان
    elif service == "permission":
        st.header("⏱️ طلب استئذان")
        with st.form("perm_form"):
            p_date = st.date_input("تاريخ الاستئذان")
            c1, c2 = st.columns(2)
            time_from = c1.time_input("من الساعة")
            time_to = c2.time_input("إلى الساعة")
            reason = st.text_area("السبب")
            
            if st.form_submit_button("إرسال الاستئذان"):
                submit_request("استئذان", f"{time_from} - {time_to}", reason, 0, 0)

    # 4. نموذج المشتريات
    elif service == "purchase":
        st.header("🛒 طلب مشتريات")
        with st.form("purchase_form"):
            item = st.text_input("اسم السلعة / الخدمة")
            cost = st.number_input("التكلفة التقديرية", min_value=0)
            reason = st.text_area("مبررات الشراء")
            
            if st.form_submit_button("اعتماد طلب الشراء"):
                submit_request("مشتريات", item, reason, cost, 0)

    # 5. نموذج رحلة العمل
    elif service == "travel":
        st.header("✈️ طلب رحلة عمل")
        with st.form("travel_form"):
            dest = st.text_input("الوجهة (المدينة/الدولة)")
            c1, c2 = st.columns(2)
            d_from = c1.date_input("تاريخ الذهاب")
            d_to = c2.date_input("تاريخ العودة")
            purpose = st.text_area("الهدف من الزيارة")
            
            if st.form_submit_button("إرسال طلب الرحلة"):
                submit_request("رحلة عمل", dest, purpose, 0, (d_to - d_from).days)

# دالة الحفظ الموحدة
def submit_request(rtype, sub_type, details, amount, days):
    user = st.session_state.get('user', {'رقم الموظف': '000', 'اسم الموظف': 'Guest'})
    
    with st.spinner("جاري حفظ الطلب في النظام..."):
        row_data = [
            int(time.time()),
            user['رقم الموظف'],
            user['اسم الموظف'],
            f"{rtype} - {sub_type}",
            details,
            amount,
            days,
            str(datetime.now().date()),
            "تحت المراجعة"
        ]
        
        if save_to_google_sheet(row_data):
            st.success("✅ تم حفظ الطلب بنجاح!")
            time.sleep(1.5)
            navigate_to("dashboard")

# --- تشغيل التطبيق ---
# تجاوز تسجيل الدخول للتجربة (يمكنك تفعيله لاحقاً)
if 'user' not in st.session_state:
    st.session_state['user'] = {'رقم الموظف': '1001', 'اسم الموظف': 'مدير النظام (تجريبي)'}

if st.session_state['page'] == 'login':
    navigate_to("dashboard") # تخطي مؤقت
elif st.session_state['page'] == 'dashboard':
    dashboard_page()
elif st.session_state['page'] == 'service_form':
    service_form_page()
elif st.session_state['page'] == 'history':
    st.title("سجل الطلبات")
    if st.button("عودة"): navigate_to("dashboard")
    # هنا يمكنك إضافة كود عرض الجدول من Google Sheets
