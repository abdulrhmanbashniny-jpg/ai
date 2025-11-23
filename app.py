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
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: bold; }
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

# --- 3. التحديث الذكي ---
def smart_update_columns():
    client = init_connection()
    if not client: return False, "فشل الاتصال"
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات")
        required = [
            "رقم_الطلب", "وقت_الطلب", "رقم_الموظف", "اسم_الموظف", "القسم", 
            "نوع_الخدمة", "التفاصيل", "شرح_الطلب", "المبلغ", "الأيام", 
            "تاريخ_البداية", "تاريخ_النهاية", "وقت_الاستئذان", 
            "حالة_الطلب", "رد_المدير", "وقت_الرد", "مدة_الإجراء_ساعة", "المرفقات", "توصية_AI"
        ]
        current = ws.row_values(1)
        missing = [h for h in required if h not in current]
        if missing:
            ws.add_cols(len(missing))
            start = len(current) + 1
            for i, h in enumerate(missing): ws.update_cell(1, start + i, h)
            return True, f"تمت إضافة: {missing}"
        return True, "محدث"
    except Exception as e: return False, str(e)

with st.sidebar.expander("🛠️ صيانة النظام"):
    if st.button("تحديث قاعدة البيانات"):
        ok, msg = smart_update_columns()
        if ok: st.success(msg)
        else: st.error(msg)

# --- 4. البيانات ---
def save_to_sheet(row_dict):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات")
        headers = ws.row_values(1)
        vals = [str(row_dict.get(h, "-")) for h in headers]
        ws.append_row(vals)
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

def update_status(req_id, status, note, mgr_name):
    client = init_connection()
    if not client: return False
    try:
        sh = client.open_by_url("https://docs.google.com/spreadsheets/d/1WxcTEwCeou6NyHk0FX36Z4FbFEXD7PGNutAyEUhUDFs/edit")
        ws = sh.worksheet("الطلبات")
        cell = ws.find(str(req_id))
        if cell:
            r = cell.row
            hdrs = ws.row_values(1)
            
            def upd(col_name, val):
                if col_name in hdrs:
                    ws.update_cell(r, hdrs.index(col_name)+1, val)

            upd("حالة_الطلب", status)
            upd("رد_المدير", f"{note} ({mgr_name})")
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            upd("وقت_الرد", now_str)
            
            # حساب الوقت
            try:
                req_time_idx = hdrs.index("وقت_الطلب") + 1
                req_val = ws.cell(r, req_time_idx).value
                t1 = datetime.strptime(str(req_val), "%Y-%m-%d %H:%M:%S")
                t2 = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
                hrs = round((t2-t1).total_seconds()/3600, 2)
                upd("مدة_الإجراء_ساعة", hrs)
            except: pass
            return True
    except: return False
    return False

# --- 5. الجلسة والدخول ---
if 'page' not in st.session_state: st.session_state['page'] = 'login'
if 'user' not in st.session_state: st.session_state['user'] = None

def login_page():
    st.markdown("<br><br><h1 style='text-align: center; color:#2980b9;'>🔐 بوابة الموظفين</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("log"):
            uid = st.text_input("رقم الموظف")
            pwd = st.text_input("كلمة المرور", type="password")
            is_mgr = st.checkbox("دخول كمدير / مسؤول")
            if st.form_submit_button("دخول"):
                role = "Manager" if is_mgr else "Employee"
                dept = "المشتريات" 
                # توحيد اسم المفاتيح: 'اسم الموظف' (بمسافة)
                st.session_state['user'] = {
                    'رقم الموظف': uid,
                    'اسم الموظف': f"المستخدم {uid}", 
                    'الهيكل الإداري': dept,
                    'الصلاحية': role
                }
                st.session_state['page'] = 'dashboard'
                st.rerun()

if st.session_state['user']:
    u = st.session_state['user']
    with st.sidebar:
        st.header(f"👤 {u['اسم الموظف']}")
        st.info(f"الصلاحية: {u['الصلاحية']}")
        st.markdown("---")
        if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.rerun()
        if u['الصلاحية'] == 'Manager':
            if st.button("✅ اعتماد الطلبات"): st.session_state['page']='approvals'; st.rerun()
        if st.button("🚪 خروج"): st.session_state['user']=None; st.session_state['page']='login'; st.rerun()

# --- 6. الصفحات ---
def dashboard_page():
    u = st.session_state['user']
    st.title(f"مرحباً، {u['اسم الموظف']}")
    if u['الصلاحية'] == 'Manager':
        st.warning("🔔 أنت في وضع المدير: يمكنك اعتماد الطلبات من القائمة الجانبية.")
    
    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 إجازات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب إجازة"): nav("leave")
        st.markdown('<div class="service-card"><h3>🛒 مشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): nav("purchase")
    with c2:
        st.markdown('<div class="service-card"><h3>💰 سلف</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): nav("loan")
        st.markdown('<div class="service-card"><h3>✈️ رحلات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب رحلة"): nav("travel")
    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ استئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"): nav("perm")
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("متابعة الطلبات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

def approvals_page():
    st.title("✅ لوحة الاعتماد")
    df = get_all_requests()
    
    if df.empty:
        st.info("لا توجد طلبات مسجلة في النظام.")
        return

    pending = df[df['حالة_الطلب'] == 'تحت المراجعة']
    
    if pending.empty:
        st.success("🎉 لا توجد طلبات معلقة.")
        return

    st.write(f"يوجد ({len(pending)}) طلبات تنتظر الاعتماد:")
    
    for i, row in pending.iterrows():
        card_title = f"#{row['رقم_الطلب']} | {row['اسم_الموظف']} | {row['نوع_الخدمة']}"
        
        with st.expander(card_title, expanded=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"**القسم:** {row['القسم']}")
                st.markdown(f"**التفاصيل:** {row['شرح_الطلب']}")
                st.markdown(f"**الوقت:** {row['وقت_الطلب']}")
                if 'المرفقات' in row and str(row['المرفقات']).strip() != "":
                    st.info(f"📎 مرفق: {row['المرفقات']}")
                if int(row.get('المبلغ', 0) or 0) > 0: st.write(f"💰 المبلغ: {row['المبلغ']}")

            with c2:
                st.markdown("### قرارك:")
                note = st.text_input("ملاحظة", key=f"n_{row['رقم_الطلب']}")
                col_ok, col_no = st.columns(2)
                
                # التصحيح هنا: نستخدم المفتاح الصحيح 'اسم الموظف'
                mgr_name = st.session_state['user']['اسم الموظف']
                
                if col_ok.button("✅ اعتماد", key=f"ok_{row['رقم_الطلب']}"):
                    if update_status(row['رقم_الطلب'], "مقبول", note, mgr_name):
                        st.success("تم!"); time.sleep(1); st.rerun()
                        
                if col_no.button("❌ رفض", key=f"no_{row['رقم_الطلب']}"):
                    if update_status(row['رقم_الطلب'], "مرفوض", note, mgr_name):
                        st.error("رفض!"); time.sleep(1); st.rerun()

def my_requests_page():
    st.title("📂 طلباتي")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    df = get_all_requests()
    if not df.empty:
        uid = str(st.session_state['user']['رقم الموظف'])
        my_df = df[df['رقم_الموظف'].astype(str) == uid]
        if not my_df.empty:
            cols = ['رقم_الطلب', 'نوع_الخدمة', 'حالة_الطلب', 'رد_المدير', 'وقت_الرد']
            final_cols = [c for c in cols if c in my_df.columns]
            st.dataframe(my_df[final_cols], use_container_width=True, hide_index=True)
        else: st.info("سجلك فارغ.")
    else: st.info("جاري التحميل...")

def form_page():
    svc = st.session_state['service']
    if st.button("🔙 إلغاء"): st.session_state['page']='dashboard'; st.rerun()
    st.write("---")
    
    up_file = st.file_uploader("📎 مرفقات (صورة/PDF)", type=['png','jpg','pdf'])
    fname = up_file.name if up_file else ""

    if svc=='leave':
        st.header("🌴 إجازة")
        with st.form("f"):
            t=st.selectbox("النوع",["سنوية","اضطرارية"]); c1,c2=st.columns(2)
            d1=c1.date_input("من"); d2=c2.date_input("إلى"); dy=st.number_input("أيام",1); r=st.text_area("سبب")
            if st.form_submit_button("إرسال"): sub("إجازة",t,r,0,dy,fname,d1,d2)
            
    elif svc=='loan':
        st.header("💰 سلفة")
        with st.form("f"):
            a=st.number_input("مبلغ",500); m=st.slider("أقساط",1,12,3); r=st.text_area("غرض")
            if st.form_submit_button("إرسال"): sub("سلفة",f"{m} أشهر",r,a,0,fname)

    elif svc=='perm':
        st.header("⏱️ استئذان")
        with st.form("f"):
            d=st.date_input("تاريخ"); c1,c2=st.columns(2); t1=c1.time_input("من"); t2=c2.time_input("إلى"); r=st.text_area("سبب")
            if st.form_submit_button("إرسال"): sub("استئذان","ساعي",r,0,0,fname,d,d,f"{t1}-{t2}")

    elif svc=='purchase':
        st.header("🛒 شراء")
        with st.form("f"):
            i=st.text_input("سلعة"); p=st.number_input("سعر",0); r=st.text_area("سبب")
            if st.form_submit_button("إرسال"): sub("مشتريات",i,r,p,0,fname)

    elif svc=='travel':
        st.header("✈️ رحلة")
        with st.form("f"):
            ds=st.text_input("وجهة"); c1,c2=st.columns(2); d1=c1.date_input("ذهاب"); d2=c2.date_input("عودة"); r=st.text_area("هدف")
            if st.form_submit_button("إرسال"): sub("رحلة عمل",ds,r,0,(d2-d1).days,fname,d1,d2)

def sub(s,sub,det,a,d,fn,sd="-",ed="-",tm="-"):
    u=st.session_state['user']
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # توحيد المفاتيح: 'اسم الموظف' (بمسافة)
    data = {
        "رقم_الطلب": int(time.time()), "وقت_الطلب": ts, "رقم_الموظف": u['رقم الموظف'],
        "اسم_الموظف": u['اسم الموظف'], "القسم": u['الهيكل الإداري'], "نوع_الخدمة": s,
        "التفاصيل": sub, "شرح_الطلب": det, "المبلغ": a, "الأيام": d,
        "تاريخ_البداية": str(sd), "تاريخ_النهاية": str(ed), "وقت_الاستئذان": str(tm),
        "حالة_الطلب": "تحت المراجعة", "رد_المدير": "-", "وقت_الرد": "-", 
        "مدة_الإجراء_ساعة": "-", "المرفقات": fn, "توصية_AI": "تحليل..."
    }
    if save_to_sheet(data):
        st.balloons(); st.success("✅ تم الإرسال!"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
    else: st.error("خطأ في الحفظ!")

# --- 7. الموجه ---
if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
