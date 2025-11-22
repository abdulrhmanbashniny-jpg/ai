import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام HR الذكي", layout="wide", page_icon="🏢")

# --- دوال التعامل مع Google Sheets (محاكاة للسرعة) ---
# في النسخة الحية، سنستبدل هذا الجزء بربط مباشر مع Google Sheets API
# الآن سنستخدم الملف المرفوع مباشرة ليعمل التطبيق فوراً
@st.cache_data
def load_data(file):
    try:
        xl = pd.ExcelFile(file)
        return {
            "الموظفين": xl.parse("الموظفين"),
            "الطلبات": xl.parse("الطلبات"),
            "الإعدادات": xl.parse("الإعدادات")
        }
    except:
        return None

# --- واجهة تسجيل الدخول ---
def login_page():
    st.markdown("""
        <style>
        .stTextInput input {text-align: center;}
        </style>
        """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 تسجيل الدخول - منصة الموارد البشرية")
        user_id = st.text_input("رقم الموظف")
        password = st.text_input("الرقم السري", type="password")
        
        if st.button("دخول", use_container_width=True):
            if user_id and password:
                verify_login(user_id, password)
            else:
                st.error("الرجاء إدخال البيانات")

def verify_login(uid, pwd):
    # هنا يتم التحقق من البيانات
    df_emps = st.session_state['data']['الموظفين']
    user = df_emps[df_emps['رقم الموظف'].astype(str) == str(uid)]
    
    if not user.empty and str(user.iloc[0]['الرقم السري']) == str(pwd):
        st.session_state['user'] = user.iloc[0].to_dict()
        st.session_state['logged_in'] = True
        st.rerun()
    else:
        st.error("بيانات الدخول غير صحيحة")

# --- الواجهة الرئيسية للموظف ---
def employee_dashboard():
    user = st.session_state['user']
    st.sidebar.title(f"مرحباً، {user['اسم الموظف']}")
    st.sidebar.info(f"القسم: {user['الهيكل الإداري']}")
    
    menu = st.sidebar.radio("القائمة", ["الرئيسية", "تقديم طلب", "طلباتي"])
    
    if menu == "الرئيسية":
        col1, col2, col3 = st.columns(3)
        col1.metric("رصيد الإجازة السنوية", f"{user['رصيد_إجازة_سنوية']} يوم")
        col2.metric("رصيد الاضطرارية", f"{user['رصيد_إجازة_اضطرارية']} يوم")
        col3.metric("الراتب الأساسي", f"{user['الراتب الاساسي']} ريال")
        
    elif menu == "تقديم طلب":
        st.header("📝 تقديم طلب جديد")
        req_type = st.selectbox("نوع الطلب", ["إجازة سنوية", "إجازة اضطرارية", "سلفة مالية", "شراء مواد"])
        
        details = st.text_area("سبب الطلب / التفاصيل")
        
        # حقول متغيرة حسب الطلب
        days = 0
        amount = 0
        if "إجازة" in req_type:
            days = st.number_input("عدد الأيام", min_value=1, max_value=30)
        if "سلفة" in req_type or "شراء" in req_type:
            amount = st.number_input("المبلغ المطلوب", min_value=100)
            
        if st.button("إرسال الطلب للذكاء الاصطناعي"):
            # محاكاة الرد الذكي
            ai_response = simulate_ai_analysis(req_type, days, amount, user, details)
            st.success("تم استلام الطلب وتحليله!")
            st.info(f"🤖 تحليل الذكاء الاصطناعي المبدئي: {ai_response}")
            
            # حفظ الطلب (في الذاكرة المؤقتة حالياً)
            new_req = {
                "رقم_الطلب": len(st.session_state['data']['الطلبات']) + 1,
                "تاريخ_الطلب": datetime.now().strftime("%Y-%m-%d"),
                "رقم_الموظف": user['رقم الموظف'],
                "اسم_الموظف": user['اسم الموظف'],
                "القسم": user['الهيكل الإداري'],
                "نوع_الطلب": req_type,
                "التفاصيل": details,
                "مدة_الإجازة_أيام": days,
                "مبلغ_السلفة": amount,
                "حالة_الطلب": "تحت المراجعة",
                "توصية_الذكاء_الاصطناعي": ai_response,
                "رد_المدير": "-"
            }
            st.session_state['data']['الطلبات'] = pd.concat([st.session_state['data']['الطلبات'], pd.DataFrame([new_req])], ignore_index=True)

    elif menu == "طلباتي":
        st.header("📂 سجل طلباتك")
        my_reqs = st.session_state['data']['الطلبات'][st.session_state['data']['الطلبات']['رقم_الموظف'] == user['رقم الموظف']]
        st.dataframe(my_reqs)

# --- لوحة تحكم المدير (Admin / Manager) ---
def manager_dashboard():
    user = st.session_state['user']
    is_admin = user['نوع الصلاحية'] == 'Admin'
    
    st.sidebar.title("👨‍💼 لوحة المدير")
    page = st.sidebar.radio("الإدارة", ["الموافقات", "التقارير الذكية", "إعدادات AI"])
    
    df_reqs = st.session_state['data']['الطلبات']
    
    # فلترة الطلبات حسب الصلاحية
    if is_admin:
        pending_reqs = df_reqs[df_reqs['حالة_الطلب'] == 'تحت المراجعة']
    else:
        # المدير يرى طلبات قسمه فقط
        pending_reqs = df_reqs[
            (df_reqs['حالة_الطلب'] == 'تحت المراجعة') & 
            (df_reqs['القسم'] == user['الهيكل الإداري'])
        ]

    if page == "الموافقات":
        st.header("📋 طلبات تنتظر الموافقة")
        if pending_reqs.empty:
            st.info("لا توجد طلبات معلقة.")
        else:
            for idx, row in pending_reqs.iterrows():
                with st.expander(f"طلب #{row['رقم_الطلب']} - {row['اسم_الموظف']} ({row['نوع_الطلب']})"):
                    col1, col2 = st.columns([2,1])
                    with col1:
                        st.write(f"**التفاصيل:** {row['التفاصيل']}")
                        st.write(f"**البيانات:** {row['مدة_الإجازة_أيام']} أيام | {row['مبلغ_السلفة']} ريال")
                    with col2:
                        st.warning(f"🤖 **رأي AI:**\n{row['توصية_الذكاء_الاصطناعي']}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✅ موافقة", key=f"app_{idx}"):
                        st.session_state['data']['الطلبات'].at[idx, 'حالة_الطلب'] = 'مقبول'
                        st.session_state['data']['الطلبات'].at[idx, 'رد_المدير'] = f"تمت الموافقة بواسطة {user['اسم الموظف']}"
                        st.rerun()
                    if c2.button("❌ رفض", key=f"rej_{idx}"):
                        st.session_state['data']['الطلبات'].at[idx, 'حالة_الطلب'] = 'مرفوض'
                        st.session_state['data']['الطلبات'].at[idx, 'رد_المدير'] = f"تم الرفض بواسطة {user['اسم الموظف']}"
                        st.rerun()

    elif page == "التقارير الذكية":
        st.header("📊 تحليل أداء الشركة")
        st.bar_chart(df_reqs['نوع_الطلب'].value_counts())
        st.write("يمكن هنا ربط API لتحليل أعمق للبيانات.")

    elif page == "إعدادات AI":
        if not is_admin:
            st.error("هذه الصفحة للمدير العام فقط")
        else:
            st.header("⚙️ ربط الذكاء الاصطناعي")
            provider = st.selectbox("المزود", ["OpenAI", "DeepSeek", "Gemini"])
            api_key = st.text_input("API Key", type="password")
            if st.button("حفظ الإعدادات"):
                st.success("تم حفظ إعدادات الربط بنجاح!")

# --- دالة محاكاة الذكاء الاصطناعي (Placeholder) ---
def simulate_ai_analysis(rtype, days, amount, user, details):
    # هذا الكود سيتم استبداله بـ API Call حقيقي لـ GPT/DeepSeek
    if "إجازة" in rtype:
        balance = user['رصيد_إجازة_سنوية'] if "سنوية" in rtype else user['رصيد_إجازة_اضطرارية']
        if days > balance:
            return f"❌ أوصي بالرفض: الرصيد ({balance}) لا يكفي لطلب ({days})."
        else:
            return "✅ أوصي بالموافقة: الرصيد يسمح ولا يوجد تعارض."
    elif "سلفة" in rtype:
        limit = user['الراتب الاساسي'] * 2
        if amount > limit:
            return f"⚠️ مخاطرة: المبلغ ({amount}) أكبر من ضعف الراتب."
        else:
            return "✅ أوصي بالموافقة: المبلغ ضمن الحدود المسموحة."
    return "ℹ️ يرجى مراجعة المدير."

# --- التشغيل الرئيسي ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# تحميل البيانات مرة واحدة
if 'data' not in st.session_state:
    # هنا نطلب من المستخدم رفع الملف لأول مرة لبدء المحاكاة
    # في النسخة النهائية يكون الربط تلقائي
    uploaded_file = st.file_uploader("الرجاء رفع ملف HR_AI_Platform_Data.xlsx لبدء النظام", type=['xlsx'])
    if uploaded_file:
        st.session_state['data'] = load_data(uploaded_file)
        st.rerun()
    else:
        st.stop()

if not st.session_state['logged_in']:
    login_page()
else:
    if st.session_state['user']['نوع الصلاحية'] in ['Admin', 'Manager']:
        manager_dashboard()
    else:
        employee_dashboard()

