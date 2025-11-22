import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# --- إعدادات الصفحة ---
st.set_page_config(page_title="HR ONE | النظام المتصل", layout="wide", page_icon="🏢")

# --- الاتصال بـ Google Sheets (القلب النابض) ---
# اسم ملفك في جوجل شيتس بالضبط
SHEET_NAME = "HR_AI_Platform_Data" 

@st.cache_resource
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # محاولة قراءة المفتاح من Secrets (للاستضافة) أو من ملف محلي (للتجربة)
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ فشل الاتصال بـ Google Sheets: {e}")
        return None

# --- دوال القراءة والكتابة الحقيقية ---
def get_data():
    client = init_connection()
    if not client: return None, None
    
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        # ورقة الموظفين (نفترض أنها الأولى)
        worksheet_emps = sh.get_worksheet(0)
        df_emps = pd.DataFrame(worksheet_emps.get_all_records())
        
        # ورقة الطلبات (نبحث عنها أو ننشئها)
        try:
            worksheet_reqs = sh.worksheet("الطلبات")
        except:
            worksheet_reqs = sh.add_worksheet(title="الطلبات", rows="1000", cols="20")
            worksheet_reqs.append_row(["id", "emp_id", "name", "dept", "type", "date", "status", "details", "amount", "days", "ai_rec"])
            
        df_reqs = pd.DataFrame(worksheet_reqs.get_all_records())
        
        return df_emps, df_reqs
    except Exception as e:
        st.error(f"خطأ في قراءة البيانات: {e}")
        return None, None

def save_request_to_sheet(req_data):
    client = init_connection()
    sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
    worksheet_reqs = sh.worksheet("الطلبات")
    
    # إضافة الصف الجديد في جوجل شيت مباشرة
    row = [
        req_data['id'], req_data['emp_id'], req_data['name'], req_data['dept'],
        req_data['type'], req_data['date'], req_data['status'],
        req_data['details'], req_data['amount'], req_data['days'], req_data['ai_rec']
    ]
    worksheet_reqs.append_row(row)

# --- واجهة المستخدم (نفس التصميم المحسن) ---
# (تم اختصار الأكواد المكررة، سنركز على التغييرات في الحفظ)

if 'page' not in st.session_state: st.session_state['page'] = 'login'

# تحميل البيانات
df_emps, df_reqs = get_data()

# --- صفحة تسجيل الدخول ---
if st.session_state['page'] == 'login':
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 دخول الموظفين (المتصل)")
        uid = st.text_input("رقم الموظف")
        pwd = st.text_input("كلمة المرور", type="password")
        
        if st.button("دخول"):
            if df_emps is not None:
                # تنظيف ومطابقة
                # تأكد أن أسماء الأعمدة في ملفك مطابقة (رقم الموظف، الرقم السري)
                user = df_emps[df_emps['رقم الموظف'].astype(str) == str(uid)]
                if not user.empty:
                    # هنا يمكنك تفعيل فحص الباسورد الحقيقي
                    st.session_state['user'] = user.iloc[0].to_dict()
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else:
                    st.error("بيانات خاطئة")

# --- لوحة التحكم وتقديم الطلب ---
elif st.session_state['page'] == 'dashboard':
    user = st.session_state['user']
    st.sidebar.title(f"👤 {user.get('اسم الموظف')}")
    if st.sidebar.button("تسجيل خروج"):
        st.session_state['page'] = 'login'
        st.rerun()
        
    st.title("تقديم طلب جديد (حفظ مباشر)")
    
    with st.form("req_form"):
        rtype = st.selectbox("نوع الطلب", ["إجازة سنوية", "إجازة اضطرارية", "سلفة"])
        details = st.text_area("التفاصيل")
        days = st.number_input("الأيام", 0)
        amount = st.number_input("المبلغ", 0)
        
        if st.form_submit_button("إرسال وحفظ"):
            new_req = {
                'id': int(time.time()),
                'emp_id': user['رقم الموظف'],
                'name': user['اسم الموظف'],
                'dept': user.get('الهيكل الإداري', 'عام'),
                'type': rtype,
                'date': str(datetime.now().date()),
                'status': 'جديد',
                'details': details,
                'amount': amount,
                'days': days,
                'ai_rec': "تحليل AI..."
            }
            
            with st.spinner("جاري الحفظ في Google Sheets..."):
                save_request_to_sheet(new_req)
                st.success("✅ تم الحفظ بنجاح في قاعدة البيانات!")
                time.sleep(1)
                st.rerun()

    # عرض الطلبات المحدثة
    st.divider()
    st.subheader("سجل الطلبات (من قاعدة البيانات)")
    if df_reqs is not None and not df_reqs.empty:
        # تصفية طلبات هذا الموظف
        my_reqs = df_reqs[df_reqs['emp_id'].astype(str) == str(user['رقم الموظف'])]
        st.dataframe(my_reqs)
