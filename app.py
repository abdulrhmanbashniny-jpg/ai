import streamlit as st
import pandas as pd
from datetime import datetime

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام HR الذكي", layout="wide", page_icon="🏢")

# --- رابط ملف Google Sheets الخاص بك ---
# نستخدم رابط التصدير المباشر لقراءة البيانات من ملفك
SHEET_ID = "1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs"
# ملاحظة: نفترض أن الورقة الأولى هي الموظفين.
# إذا لم تكن الأوراق الأخرى (الطلبات/الإعدادات) موجودة في ملفك، سينشئها النظام في الذاكرة مؤقتاً.
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# --- دوال النظام ---
@st.cache_data(ttl=600) # تحديث البيانات كل 10 دقائق
def load_google_sheet():
    try:
        # محاولة قراءة ورقة الموظفين من الرابط
        df_emp = pd.read_csv(SHEET_URL)
        # تنظيف أسماء الأعمدة
        df_emp.columns = df_emp.columns.str.strip()
        
        # التأكد من وجود الأعمدة الضرورية، إذا نقصت نضيفها افتراضياً
        required_cols = {
            'رقم الموظف': 0, 'الرقم السري': '123456', 
            'رصيد_إجازة_سنوية': 30, 'رصيد_إجازة_اضطرارية': 5, 
            'الراتب الاساسي': 5000, 'الهيكل الإداري': 'عام'
        }
        for col, default_val in required_cols.items():
            if col not in df_emp.columns:
                df_emp[col] = default_val

        return df_emp
    except Exception as e:
        st.error(f"خطأ في قراءة ملف Google Sheets: {e}")
        return None

def initialize_session():
    if 'data' not in st.session_state:
        df_emps = load_google_sheet()
        if df_emps is not None:
            # إنشاء جداول فارغة للطلبات والإعدادات في الذاكرة
            df_reqs = pd.DataFrame(columns=[
                "رقم_الطلب", "تاريخ_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم",
                "نوع_الطلب", "التفاصيل", "مدة_الإجازة_أيام", "مبلغ_السلفة",
                "حالة_الطلب", "توصية_الذكاء_الاصطناعي", "رد_المدير"
            ])
            st.session_state['data'] = {
                "الموظفين": df_emps,
                "الطلبات": df_reqs
            }
        else:
            st.stop()

# --- واجهة تسجيل الدخول ---
def login_page():
    st.markdown("<h1 style='text-align: center; color: #2e86de;'>🔐 بوابة الموظفين</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_id = st.text_input("رقم الموظف")
            password = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("تسجيل الدخول", use_container_width=True)
            
            if submitted:
                verify_login(user_id, password)

def verify_login(uid, pwd):
    df = st.session_state['data']['الموظفين']
    # تحويل المدخلات لنصوص للمقارنة
    user = df[df['رقم الموظف'].astype(str) == str(uid)]
    
    if not user.empty:
        stored_pass = str(user.iloc[0]['الرقم السري'])
        # تجاوز التحقق إذا كانت كلمة المرور غير موجودة في الملف الأصلي (للتسهيل)
        if stored_pass == 'nan' or stored_pass == str(pwd): 
            st.session_state['user'] = user.iloc[0].to_dict()
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.error("كلمة المرور غير صحيحة")
    else:
        st.error("رقم الموظف غير مسجل")

# --- القائمة الجانبية (Logout) ---
def sidebar_menu():
    user = st.session_state['user']
    st.sidebar.markdown(f"### 👤 {user['اسم الموظف']}")
    st.sidebar.caption(f"القسم: {user.get('الهيكل الإداري', 'غير محدد')}")
    
    if st.sidebar.button("تسجيل الخروج 🚪", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['user'] = None
        st.rerun()
    
    st.sidebar.divider()

# --- واجهة تقديم الطلبات (للموظف والمدير) ---
def request_form():
    st.header("📝 تقديم طلب جديد")
    user = st.session_state['user']
    
    with st.form("new_request"):
        col1, col2 = st.columns(2)
        with col1:
            req_type = st.selectbox("نوع الطلب", ["إجازة سنوية", "إجازة اضطرارية", "سلفة مالية", "أخرى"])
        with col2:
            days = st.number_input("عدد الأيام (للإجازات)", min_value=0, value=1)
        
        amount = st.number_input("المبلغ (للسلف)", min_value=0, step=100)
        details = st.text_area("ملاحظات / تفاصيل الطلب")
        
        submit = st.form_submit_button("إرسال الطلب")
        
        if submit:
            # محاكاة الذكاء الاصطناعي
            ai_rec = "✅ موافقة مبدئية (الرصيد يسمح)" if days < 30 else "⚠️ يحتاج مراجعة (المدة طويلة)"
            
            new_req = {
                "رقم_الطلب": len(st.session_state['data']['الطلبات']) + 1001,
                "تاريخ_الطلب": datetime.now().strftime("%Y-%m-%d"),
                "رقم_الموظف": user['رقم الموظف'],
                "اسم_الموظف": user['اسم الموظف'],
                "القسم": user.get('الهيكل الإداري', 'عام'),
                "نوع_الطلب": req_type,
                "التفاصيل": details,
                "مدة_الإجازة_أيام": days,
                "مبلغ_السلفة": amount,
                "حالة_الطلب": "تحت المراجعة",
                "توصية_الذكاء_الاصطناعي": ai_rec,
                "رد_المدير": "-"
            }
            # إضافة الطلب للذاكرة
            st.session_state['data']['الطلبات'] = pd.concat(
                [st.session_state['data']['الطلبات'], pd.DataFrame([new_req])], 
                ignore_index=True
            )
            st.success("تم إرسال الطلب بنجاح!")

# --- لوحة المدير ---
def admin_dashboard():
    st.title("لوحة تحكم المدير 👨‍💼")
    
    # تبديل بين لوحة المدير وتقديم طلب شخصي
    view_mode = st.radio("وضع العرض:", ["إدارة الطلبات", "تقديم طلب شخصي"], horizontal=True)
    
    if view_mode == "تقديم طلب شخصي":
        request_form()
        return

    # عرض الطلبات
    df_reqs = st.session_state['data']['الطلبات']
    pending = df_reqs[df_reqs['حالة_الطلب'] == 'تحت المراجعة']
    
    col1, col2 = st.columns(2)
    col1.metric("الطلبات المعلقة", len(pending))
    col2.metric("إجمالي الطلبات", len(df_reqs))
    
    st.divider()
    
    if len(pending) == 0:
        st.info("لا توجد طلبات جديدة للمراجعة.")
    else:
        st.write("### 📥 طلبات واردة")
        for i, row in pending.iterrows():
            with st.expander(f"{row['نوع_الطلب']} - {row['اسم_الموظف']}", expanded=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**التفاصيل:** {row['التفاصيل']}")
                    st.caption(f"توصية AI: {row['توصية_الذكاء_الاصطناعي']}")
                with c2:
                    if st.button("✅ موافقة", key=f"acc_{i}"):
                        st.session_state['data']['الطلبات'].at[i, 'حالة_الطلب'] = 'مقبول'
                        st.rerun()
                    if st.button("❌ رفض", key=f"rej_{i}"):
                        st.session_state['data']['الطلبات'].at[i, 'حالة_الطلب'] = 'مرفوض'
                        st.rerun()

# --- تشغيل التطبيق ---
initialize_session()

if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login_page()
else:
    sidebar_menu()
    user_role = st.session_state['user'].get('نوع الصلاحية', 'Employee')
    
    # إذا كان المدير، يفتح لوحة المدير، وإلا يفتح نموذج الطلب
    if str(user_role).lower() in ['admin', 'manager']:
        admin_dashboard()
    else:
        st.title("لوحة الموظف")
        # عرض حالة الطلبات السابقة
        my_reqs = st.session_state['data']['الطلبات'][
            st.session_state['data']['الطلبات']['رقم_الموظف'] == st.session_state['user']['رقم الموظف']
        ]
        if not my_reqs.empty:
            st.dataframe(my_reqs[['نوع_الطلب', 'حالة_الطلب', 'رد_المدير']])
        request_form()
