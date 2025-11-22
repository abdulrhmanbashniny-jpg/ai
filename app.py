import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- 1. إعدادات الصفحة والتصميم ---
st.set_page_config(page_title="بوابة الخدمات الذكية", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تحسين البطاقات */
    .service-card {
        background-color: white;
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        text-align: center;
        transition: 0.3s;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .service-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        border-color: #2196f3;
    }
    /* تنسيق العناوين */
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #2c3e50; }
    
    /* الأزرار */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 50px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. دوال الاتصال بـ Google Sheets ---
@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        else:
            return None
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ خطأ اتصال: {e}")
        return None

# --- 3. زر الإصلاح (لتوحيد أعمدة الإكسل) ---
with st.expander("⚠️ إعدادات المدير (اضغط هنا لإصلاح ملف الإكسل أول مرة)"):
    if st.button("🛠️ إعادة بناء ورقة الطلبات (سيحذف البيانات القديمة)"):
        client = init_connection()
        if client:
            sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
            try:
                try: sh.del_worksheet(sh.worksheet("الطلبات"))
                except: pass
                
                # إنشاء الورقة بالأعمدة الصحيحة
                ws = sh.add_worksheet(title="الطلبات", rows="1000", cols="20")
                headers = [
                    "رقم_الطلب", "تاريخ_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم",
                    "نوع_الخدمة", "التفاصيل_الفرعية", "شرح_الطلب", "المبلغ_المالي", 
                    "المدة_بالأيام", "تاريخ_البداية", "تاريخ_النهاية", "وقت_الاستئذان", 
                    "حالة_الطلب", "رد_المدير", "توصية_AI"
                ]
                ws.append_row(headers)
                st.success("✅ تم إصلاح ملف الإكسل! البيانات الجديدة ستنزل مرتبة الآن.")
            except Exception as e:
                st.error(f"حدث خطأ: {e}")

# --- 4. دالة الحفظ الذكية (المحدثة) ---
def save_to_sheet(data_row):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات")
        ws.append_row(data_row)
        return True
    except:
        st.error("لم يتم العثور على ورقة 'الطلبات'. الرجاء ضغط زر الإصلاح بالأعلى.")
        return False

def submit_request(service_main, sub_type, details, amount, days, start_d="-", end_d="-", time_range="-"):
    user = st.session_state.get('user', {'رقم الموظف': '000', 'اسم الموظف': 'Guest', 'الهيكل الإداري': 'عام'})
    
    # تجهيز الصف بنفس ترتيب الأعمدة الجديد
    row = [
        int(time.time()),               # رقم الطلب
        str(datetime.now().date()),     # تاريخ
        user['رقم الموظف'],
        user['اسم الموظف'],
        user.get('الهيكل الإداري', 'غير محدد'),
        service_main,                   # نوع الخدمة
        sub_type,                       # النوع الفرعي
        details,                        # التفاصيل
        amount,                         # المبلغ
        days,                           # الأيام
        str(start_d),                   # تاريخ بداية
        str(end_d),                     # تاريخ نهاية
        str(time_range),                # وقت الاستئذان
        "تحت المراجعة",
        "-",
        "جاري التحليل..."
    ]
    
    if save_to_sheet(row):
        st.balloons()
        st.success("✅ تم إرسال طلبك بنجاح وحفظه في النظام!")
        time.sleep(2)
        st.session_state['page'] = 'dashboard'
        st.rerun()

# --- 5. إدارة الصفحات ---
if 'page' not in st.session_state: st.session_state['page'] = 'dashboard' # (تجاوزنا اللوجن للتجربة)
if 'service' not in st.session_state: st.session_state['service'] = None

# تعريف المستخدم الافتراضي (للتجربة)
if 'user' not in st.session_state:
    st.session_state['user'] = {'رقم الموظف': '1011', 'اسم الموظف': 'موظف تجريبي', 'الهيكل الإداري': 'IT'}

# --- 6. تصميم الواجهات ---
def dashboard():
    st.title("👋 مرحباً، " + st.session_state['user']['اسم الموظف'])
    st.markdown("### اختر الخدمة المطلوبة:")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب إجازة جديد"):
            st.session_state['service'] = 'leave'
            st.session_state['page'] = 'form'
            st.rerun()
            
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"):
            st.session_state['service'] = 'purchase'
            st.session_state['page'] = 'form'
            st.rerun()

    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف المالية</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"):
            st.session_state['service'] = 'loan'
            st.session_state['page'] = 'form'
            st.rerun()
            
        st.markdown('<div class="service-card"><h3>✈️ رحلات العمل</h3></div>', unsafe_allow_html=True)
        if st.button("انتداب / رحلة"):
            st.session_state['service'] = 'travel'
            st.session_state['page'] = 'form'
            st.rerun()

    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"):
            st.session_state['service'] = 'perm'
            st.session_state['page'] = 'form'
            st.rerun()
            
        st.markdown('<div class="service-card"><h3>📂 طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("متابعة الطلبات"):
            st.info("قريباً...")

def form_page():
    svc = st.session_state['service']
    
    if st.button("🔙 عودة للقائمة الرئيسية"):
        st.session_state['page'] = 'dashboard'
        st.rerun()
    
    st.markdown("---")
    
    # --- نموذج الإجازة ---
    if svc == 'leave':
        st.header("🌴 طلب إجازة")
        with st.form("f1"):
            t = st.selectbox("النوع", ["سنوية", "اضطرارية", "مرضية"])
            c1, c2 = st.columns(2)
            d1 = c1.date_input("من تاريخ")
            d2 = c2.date_input("إلى تاريخ")
            days = st.number_input("المدة (أيام)", 1)
            det = st.text_area("ملاحظات")
            if st.form_submit_button("إرسال"):
                submit_request("إجازة", t, det, 0, days, d1, d2)

    # --- نموذج السلفة ---
    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        with st.form("f2"):
            amt = st.number_input("المبلغ", 1000)
            mon = st.slider("أشهر السداد", 1, 12, 3)
            det = st.text_area("السبب")
            if st.form_submit_button("إرسال"):
                submit_request("سلفة", f"سداد {mon} شهر", det, amt, 0)

    # --- نموذج الاستئذان ---
    elif svc == 'perm':
        st.header("⏱️ طلب استئذان")
        with st.form("f3"):
            day = st.date_input("اليوم")
            c1, c2 = st.columns(2)
            t1 = c1.time_input("من")
            t2 = c2.time_input("إلى")
            det = st.text_area("الظرف/السبب")
            if st.form_submit_button("إرسال"):
                submit_request("استئذان", "ساعي", det, 0, 0, day, day, f"{t1}-{t2}")

    # --- نموذج المشتريات ---
    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        with st.form("f4"):
            item = st.text_input("اسم المنتج")
            cost = st.number_input("التكلفة التقريبية", 0)
            det = st.text_area("مبررات الشراء")
            if st.form_submit_button("إرسال"):
                submit_request("مشتريات", item, det, cost, 0)
                
    # --- نموذج الرحلات ---
    elif svc == 'travel':
        st.header("✈️ طلب رحلة عمل")
        with st.form("f5"):
            dest = st.text_input("الوجهة")
            c1, c2 = st.columns(2)
            d1 = c1.date_input("الذهاب")
            d2 = c2.date_input("العودة")
            purp = st.text_area("الغرض من الزيارة")
            if st.form_submit_button("إرسال"):
                days_diff = (d2 - d1).days
                submit_request("رحلة عمل", dest, purp, 0, days_diff, d1, d2)

# --- 7. الموجه الرئيسي ---
if st.session_state['page'] == 'dashboard':
    dashboard()
elif st.session_state['page'] == 'form':
    form_page()
