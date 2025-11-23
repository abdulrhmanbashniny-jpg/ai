import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import urllib.parse

# --- 1. إعدادات الصفحة والتصميم (CSS) ---
st.set_page_config(page_title="نظام الموارد البشرية المتكامل", layout="wide", page_icon="🏢")

st.markdown("""
<style>
    /* تصميم البطاقات */
    .service-card {
        background-color: white; padding: 25px; border-radius: 15px;
        border: 1px solid #e0e0e0; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: 0.3s; cursor: pointer; margin-bottom: 15px;
    }
    .service-card:hover { transform: translateY(-5px); border-color: #3498db; box-shadow: 0 8px 15px rgba(0,0,0,0.1); }
    
    /* تحسين الخطوط والأزرار */
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 8px; height: 45px; font-weight: bold; font-size: 16px; }
    
    /* تصميم شريط التتبع */
    .step { display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 0.85em; margin: 2px; border: 1px solid #ddd; background: #f8f9fa; color: #666; }
    .step-done { background: #d4edda; color: #155724; border-color: #c3e6cb; }
    .step-wait { background: #fff3cd; color: #856404; border-color: #ffeeba; }
    .step-active { background: #cce5ff; color: #004085; border-color: #b8daff; font-weight: bold; }
    
    /* صندوق الإقرار */
    .declaration-box {
        background-color: #fffbf2; border: 1px solid #f0e6ce; padding: 15px;
        border-radius: 8px; color: #5a4a2d; font-size: 0.95em; line-height: 1.6;
        margin: 15px 0; text-align: justify;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. الاتصال بقاعدة البيانات (Supabase) ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
        return None

supabase = init_supabase()

# --- 3. دوال التعامل مع البيانات ---

def get_user(uid):
    """جلب بيانات الموظف"""
    if not supabase: return None
    try:
        res = supabase.table("employees").select("*").eq("emp_id", uid).execute()
        if res.data: return res.data[0]
    except: pass
    return None

def get_tasks(role, uid, dept):
    """جلب المهام حسب الدور (بديل / مدير / HR)"""
    if not supabase: return []
    tasks = []
    
    try:
        # 1. مهام الموظف البديل (بغض النظر عن دوره الوظيفي)
        sub_res = supabase.table("requests").select("*").eq("substitute_id", uid).eq("status_substitute", "Pending").execute()
        for r in sub_res.data:
            r['task_type'] = 'Substitute'
            tasks.append(r)

        # 2. مهام المدير (فقط للمدراء)
        if role == "Manager":
            # المدير يرى الطلبات التي (ليس لها بديل OR البديل وافق) AND (المدير لم يوافق بعد)
            # ملاحظة: في Supabase الفلترة المعقدة تحتاج منطق، هنا سنبسطها:
            # نجلب طلبات القسم المعلقة عند المدير، ثم نستبعد التي تنتظر بديل
            mgr_res = supabase.table("requests").select("*").eq("dept", dept).eq("status_manager", "Pending").execute()
            for r in mgr_res.data:
                # شرط: يجب أن يكون البديل (إن وجد) قد وافق، أو لا يوجد بديل أصلاً
                if r['status_substitute'] in ['Approved', 'Not Required']:
                    r['task_type'] = 'Manager'
                    tasks.append(r)

        # 3. مهام الموارد البشرية
        if role == "HR":
            hr_res = supabase.table("requests").select("*").eq("status_manager", "Approved").eq("status_hr", "Pending").execute()
            for r in hr_res.data:
                r['task_type'] = 'HR'
                tasks.append(r)
                
    except Exception as e:
        st.error(f"خطأ في جلب المهام: {e}")
        
    return tasks

def submit_request(data):
    """إرسال طلب جديد"""
    if not supabase: return False
    try:
        supabase.table("requests").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"فشل الحفظ: {e}")
        return False

def update_req_status(req_id, field, status, note, user_name):
    """تحديث حالة الطلب"""
    if not supabase: return False
    try:
        data = {
            field: status,
            f"{field.replace('status_', '')}_note": note,
            f"{field.replace('status_', '')}_action_at": datetime.now().isoformat()
        }
        # منطق الحالة النهائية
        if status == "Rejected":
            data["final_status"] = "Rejected"
        elif field == "status_hr" and status == "Approved":
            data["final_status"] = "Approved"
        
        supabase.table("requests").update(data).eq("id", req_id).execute()
        return True
    except: return False

# --- 4. صفحات النظام ---

# أ. تسجيل الدخول
def login_page():
    st.markdown("<br><br><h1 style='text-align: center; color:#2980b9;'>🔐 بوابة الخدمات الذكية</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.form("login_form"):
            uid = st.text_input("رقم الموظف", placeholder="مثال: 1011")
            pwd = st.text_input("كلمة المرور", type="password")
            if st.form_submit_button("تسجيل الدخول"):
                user = get_user(uid)
                if user and user.get('password') == pwd:
                    st.session_state['user'] = user
                    st.session_state['page'] = 'dashboard'
                    st.rerun()
                else:
                    st.error("بيانات الدخول غير صحيحة")

# ب. لوحة التحكم (Dashboard)
def dashboard_page():
    u = st.session_state['user']
    st.title(f"👋 أهلاً بك، {u['name']}")
    
    # عداد المهام
    tasks = get_tasks(u['role'], u['emp_id'], u['dept'])
    if tasks:
        st.warning(f"🔔 لديك ({len(tasks)}) مهام تتطلب اتخاذ إجراء. انتقل لصفحة الموافقات.")

    st.write("---")
    
    # شبكة الخدمات
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="service-card"><h3>🌴 الإجازات</h3></div>', unsafe_allow_html=True)
        if st.button("تقديم طلب إجازة"): nav("leave")
        
        st.markdown('<div class="service-card"><h3>🛒 المشتريات</h3></div>', unsafe_allow_html=True)
        if st.button("طلب شراء"): nav("purchase")
        
    with c2:
        st.markdown('<div class="service-card"><h3>💰 السلف المالية</h3></div>', unsafe_allow_html=True)
        if st.button("طلب سلفة"): nav("loan")
        
        st.markdown('<div class="service-card"><h3>✈️ رحلات العمل</h3></div>', unsafe_allow_html=True)
        if st.button("طلب انتداب"): nav("travel")

    with c3:
        st.markdown('<div class="service-card"><h3>⏱️ الاستئذان</h3></div>', unsafe_allow_html=True)
        if st.button("تسجيل استئذان"): nav("perm")
        
        st.markdown('<div class="service-card" style="border-color:#f39c12;"><h3>📂 متابعة طلباتي</h3></div>', unsafe_allow_html=True)
        if st.button("سجل المعاملات"): st.session_state['page']='my_requests'; st.rerun()

def nav(s): st.session_state['service']=s; st.session_state['page']='form'; st.rerun()

# ج. صفحة النماذج (Forms)
def form_page():
    u = st.session_state['user']
    svc = st.session_state['service']
    
    if st.button("🔙 عودة للقائمة"): st.session_state['page']='dashboard'; st.rerun()
    st.write("---")
    
    # --- نموذج الإجازة (المطور) ---
    if svc == 'leave':
        st.header("🌴 طلب إجازة جديد")
        
        # معلومات الموظف (للقراءة فقط)
        c1, c2, c3 = st.columns(3)
        c1.text_input("الاسم", u['name'], disabled=True)
        c2.text_input("القسم", u['dept'], disabled=True)
        c3.text_input("الرقم الوظيفي", u['emp_id'], disabled=True)
        
        st.divider()
        
        # تفاصيل الإجازة
        col_type, col_bal = st.columns([2, 1])
        l_type = col_type.selectbox("نوع الإجازة", ["سنوية (Yearly)", "مرضية (Sick)", "بدون راتب (Unpaid)"])
        
        # التواريخ والحساب التلقائي
        c_d1, c_d2 = st.columns(2)
        d1 = c_d1.date_input("تاريخ البداية", datetime.today())
        d2 = c_d2.date_input("تاريخ النهاية", datetime.today())
        
        days = 0
        if d2 >= d1:
            days = (d2 - d1).days + 1
            st.info(f"📅 مدة الإجازة: **{days} أيام**")
            
            # التحقق من القواعد
            if l_type.startswith("مرضية") and days > 60:
                st.error("❌ عذراً: الإجازة المرضية لا تتجاوز 60 يوماً حسب النظام.")
                days = -1
            elif l_type.startswith("بدون") and days > 10:
                st.error("❌ عذراً: الإجازة بدون راتب لا تتجاوز 10 أيام.")
                days = -1
        else:
            st.error("⚠️ تاريخ النهاية يجب أن يكون بعد البداية.")
            days = -1
            
        # الموظف البديل
        st.write("### بيانات الموظف البديل")
        sub_id = st.text_input("رقم الموظف البديل (اختياري)", placeholder="أدخل الرقم الوظيفي للبديل")
        sub_name = None
        if sub_id:
            sub_user = get_user(sub_id)
            if sub_user:
                st.success(f"✅ تم اختيار البديل: {sub_user['name']}")
                sub_name = sub_user['name']
            else:
                st.warning("⚠️ رقم الموظف غير صحيح")
                sub_id = None # إلغاء الرقم الخاطئ

        # سبب الإجازة
        reason = st.text_area("سبب الإجازة / الملاحظات")

        # الإقرار (النص الكامل)
        st.markdown(f"""
        <div class="declaration-box">
        <strong>(( إقــرار وتعهــد ))</strong><br>
        أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، كما أنني لن أتجاوز مدة الإجازة المطلوبة إلا عند إرسال <strong>خطاب رسمي</strong> لتمديد الإجازة والموافقة عليها خطياً من قبل رئيسي المباشر. 
        كما أعتبر نفسي منذراً بالفصل النهائي عند تجاوز مدة الغياب حسب المدة المحددة في نظام العمل والعمال، وذلك دون الحاجة لإنذاري رسمياً على عنواني في بلدي. 
        وأنني سأقوم بإجازتي في التاريخ المبين أعلاه، وبذلك ألتزم وعلى ذلك أوقع إلكترونياً.
        </div>
        """, unsafe_allow_html=True)
        
        agree = st.checkbox("✅ أوافق وألتزم بما ورد في الإقرار أعلاه")
        
        if st.button("🚀 اعتماد وإرسال الطلب", type="primary"):
            if not agree:
                st.toast("⚠️ يجب الموافقة على الإقرار أولاً")
            elif days <= 0:
                st.toast("⚠️ تحقق من التواريخ والمدة")
            else:
                # تجهيز البيانات
                req_data = {
                    "emp_id": u['emp_id'], "emp_name": u['name'], "dept": u['dept'],
                    "service_type": "إجازة", "sub_type": l_type, "details": reason,
                    "start_date": str(d1), "end_date": str(d2), "days": days,
                    "substitute_id": sub_id, "substitute_name": sub_name,
                    "status_substitute": "Pending" if sub_id else "Not Required",
                    "declaration_agreed": True,
                    "phone": u['phone'] # مهم للواتساب
                }
                if submit_request(req_data):
                    st.balloons()
                    st.success("تم إرسال طلبك بنجاح!")
                    time.sleep(2)
                    st.session_state['page']='dashboard'
                    st.rerun()

    # --- نماذج الطلبات الأخرى ---
    elif svc == 'loan':
        st.header("💰 طلب سلفة")
        amt = st.number_input("المبلغ المطلوب", min_value=500, step=500)
        rsn = st.text_area("الغرض من السلفة")
        if st.button("إرسال الطلب"):
            if submit_request({"emp_id": u['emp_id'], "service_type": "سلفة", "amount": amt, "details": rsn}):
                st.success("تم الإرسال"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

    elif svc == 'purchase':
        st.header("🛒 طلب شراء")
        item = st.text_input("اسم الصنف")
        rsn = st.text_area("مبررات الشراء")
        if st.button("إرسال الطلب"):
            if submit_request({"emp_id": u['emp_id'], "service_type": "مشتريات", "details": f"{item} - {rsn}"}):
                st.success("تم الإرسال"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()
                
    elif svc == 'perm':
        st.header("⏱️ استئذان")
        d = st.date_input("التاريخ")
        tm = st.time_input("وقت الاستئذان")
        rsn = st.text_area("السبب")
        if st.button("إرسال الطلب"):
            if submit_request({"emp_id": u['emp_id'], "service_type": "استئذان", "start_date": str(d), "details": f"{tm} - {rsn}"}):
                st.success("تم الإرسال"); time.sleep(1); st.session_state['page']='dashboard'; st.rerun()

# د. صفحة الموافقات (Approvals)
def approvals_page():
    u = st.session_state['user']
    st.title("✅ مهام الاعتماد")
    
    tasks = get_tasks(u['role'], u['emp_id'], u['dept'])
    
    if not tasks:
        st.info("🎉 لا توجد مهام معلقة حالياً.")
        return
        
    for r in tasks:
        task_type = r.get('task_type', 'Manager')
        label = "موافقة بديل" if task_type == 'Substitute' else "اعتماد مدير" if task_type == 'Manager' else "اعتماد موارد بشرية"
        border_color = "#f1c40f" if task_type == 'Substitute' else "#3498db"
        
        with st.expander(f"[{label}] {r['service_type']} - {r['emp_name']}", expanded=True):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**نوع الخدمة:** {r['sub_type'] or r['service_type']}")
                if r.get('days'): st.write(f"**المدة:** {r['days']} أيام (من {r['start_date']} إلى {r['end_date']})")
                st.write(f"**التفاصيل:** {r['details']}")
                
                if task_type == 'Substitute':
                    st.warning("⚠️ هذا الزميل اختارك لتكون بديلاً له أثناء فترة غيابه.")
            
            with c2:
                note = st.text_input("ملاحظات الاعتماد", key=f"note_{r['id']}")
                col_ok, col_no = st.columns(2)
                
                # أزرار الإجراءات
                if task_type == 'Substitute':
                    if col_ok.button("✅ أقبل", key=f"ok_{r['id']}"):
                        update_req_status(r['id'], "status_substitute", "Approved", note, u['name'])
                        st.rerun()
                    if col_no.button("❌ أعتذر", key=f"no_{r['id']}"):
                        update_req_status(r['id'], "status_substitute", "Rejected", note, u['name'])
                        st.rerun()
                        
                elif task_type == 'HR':
                    # اعتماد الـ HR + واتساب
                    if col_ok.button("✅ اعتماد نهائي", key=f"ok_{r['id']}"):
                        update_req_status(r['id'], "status_hr", "Approved", note, u['name'])
                        
                        # رابط واتساب
                        if r.get('phone'):
                            ph = r['phone'].replace('0', '966', 1)
                            msg = f"عزيزي {r['emp_name']}، تم اعتماد إجازتك ({r['sub_type']}) لمدة {r['days']} أيام.\nنتمنى لك إجازة سعيدة!"
                            wa_link = f"https://wa.me/{ph}?text={urllib.parse.quote(msg)}"
                            st.markdown(f"### [📲 اضغط هنا لإرسال إشعار واتساب للموظف]({wa_link})")
                        st.success("تم الاعتماد!")
                        
                    if col_no.button("❌ رفض", key=f"no_{r['id']}"):
                        update_req_status(r['id'], "status_hr", "Rejected", note, u['name'])
                        st.rerun()
                        
                else: # Manager
                    if col_ok.button("✅ موافقة", key=f"ok_{r['id']}"):
                        update_req_status(r['id'], "status_manager", "Approved", note, u['name'])
                        st.rerun()
                    if col_no.button("❌ رفض", key=f"no_{r['id']}"):
                        update_req_status(r['id'], "status_manager", "Rejected", note, u['name'])
                        st.rerun()

# هـ. متابعة الطلبات
def my_requests_page():
    st.title("📂 سجل معاملاتي")
    if st.button("🔙 عودة"): st.session_state['page']='dashboard'; st.rerun()
    
    u = st.session_state['user']
    if not supabase: return
    
    reqs = supabase.table("requests").select("*").eq("emp_id", u['emp_id']).order("created_at", desc=True).execute().data
    
    if not reqs:
        st.info("لا توجد معاملات سابقة.")
        return
        
    for r in reqs:
        with st.container():
            # شريط الحالة (Timeline)
            s_sub = "step-done" if r['status_substitute'] in ['Approved','Not Required'] else "step-active" if r['status_substitute']=='Pending' else "step-wait"
            s_mgr = "step-done" if r['status_manager']=='Approved' else "step-active" if (s_sub=='step-done' and r['status_manager']=='Pending') else "step-wait"
            s_hr = "step-done" if r['status_hr']=='Approved' else "step-active" if (s_mgr=='step-done' and r['status_hr']=='Pending') else "step-wait"
            
            st.markdown(f"### {r['service_type']} - {r['created_at'][:10]}")
            
            # عرض الشريط
            st.markdown(f"""
            <div>
                <span class="step {s_sub}">1. البديل</span>
                <span class="step {s_mgr}">2. المدير</span>
                <span class="step {s_hr}">3. الموارد البشرية</span>
                {'<span class="step step-done">✅ معتمد</span>' if r['final_status']=='Approved' else ''}
                {'<span class="step" style="background:#f8d7da;color:red;">❌ مرفوض</span>' if r['final_status']=='Rejected' else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # زر الطباعة (عند الاعتماد النهائي فقط)
            if r['final_status'] == 'Approved':
                if st.button("🖨️ طباعة القرار", key=f"pr_{r['id']}"):
                    print_form(r)
            
            st.divider()

def print_form(r):
    st.markdown(f"""
    <div style="border:3px double black; padding:30px; background:white; color:black; font-family:'Traditional Arabic', serif; direction:rtl; text-align:right;">
        <h2 style="text-align:center;">قرار إجازة</h2>
        <hr>
        <p><strong>الاسم:</strong> {r['emp_name']} &nbsp;&nbsp;&nbsp; <strong>الرقم:</strong> {r['emp_id']} &nbsp;&nbsp;&nbsp; <strong>القسم:</strong> {r['dept']}</p>
        <p>بناءً على الطلب المقدم، تمت الموافقة على منح الموظف المذكور أعلاه إجازة ({r['sub_type']}) لمدة ({r['days']}) أيام.</p>
        <p><strong>تاريخ البداية:</strong> {r['start_date']} &nbsp;&nbsp; <strong>تاريخ العودة:</strong> {r['end_date']}</p>
        <p><strong>الموظف البديل:</strong> {r['substitute_name'] or 'لا يوجد'}</p>
        <br>
        <div style="border:1px solid #000; padding:10px; font-size:0.9em;">
            <strong>الإقــرار:</strong><br>
            أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد... (تمت الموافقة الرقمية)
        </div>
        <br><br>
        <table style="width:100%; text-align:center;">
            <tr><td>المدير المباشر<br><strong>موافق ✅</strong></td><td>الموارد البشرية<br><strong>موافق ✅</strong></td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

# --- 5. التوجيه الرئيسي ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'page' not in st.session_state: st.session_state['page'] = 'login'

if st.session_state['user']:
    with st.sidebar:
        st.header(f"👤 {st.session_state['user']['name']}")
        if st.button("🏠 الرئيسية"): st.session_state['page']='dashboard'; st.rerun()
        
        # زر الموافقات يظهر فقط لأصحاب الصلاحية
        if st.session_state['user']['role'] in ['Manager', 'HR'] or True: # True هنا لكي يظهر لأي شخص قد يكون بديلاً
            if st.button("✅ المهام والموافقات"): st.session_state['page']='approvals'; st.rerun()
            
        st.markdown("---")
        if st.button("🚪 تسجيل خروج"): st.session_state.clear(); st.rerun()

if st.session_state['page'] == 'login': login_page()
elif st.session_state['page'] == 'dashboard': dashboard_page()
elif st.session_state['page'] == 'form': form_page()
elif st.session_state['page'] == 'approvals': approvals_page()
elif st.session_state['page'] == 'my_requests': my_requests_page()
