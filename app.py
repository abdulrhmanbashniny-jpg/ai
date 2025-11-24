# --- استيراد المكتبات الجديدة ---
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# --- تسجيل خط عربي (هام جداً) ---
# سنستخدم خط DejaVuSans لأنه متوفر غالباً في سيرفرات لينكس، أو نحمله إذا لم يوجد
try:
    pdfmetrics.registerFont(TTFont('Arabic', 'DejaVuSans.ttf')) # محاولة 1
except:
    try:
        # محاولة تحميل الخط من مسار النظام
        pdfmetrics.registerFont(TTFont('Arabic', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
    except:
        st.warning("تحذير: لم يتم العثور على خط عربي، قد تظهر النصوص مقلوبة.")

def reshape_text(text):
    """دالة مساعدة لتصحيح النص العربي"""
    if not text: return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def generate_pdf(r, salary, annual_days, last_calc_date, allowance):
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # إعداد الخط
    try:
        c.setFont("Arabic", 16)
    except:
        c.setFont("Helvetica-Bold", 16)

    # العنوان
    title = reshape_text("نموذج طلب إجازة / Leave Request")
    c.drawCentredString(width/2, height - 2*cm, title)
    c.line(1*cm, height - 2.3*cm, width - 1*cm, height - 2.3*cm)
    
    # البيانات الأساسية
    y = height - 3*cm
    c.setFont("Arabic", 10) if 'Arabic' in pdfmetrics.getRegisteredFontNames() else c.setFont("Helvetica", 10)
    
    # تجهيز النصوص العربية
    lines = [
        f"{reshape_text('اسم الموظف')}: {reshape_text(r['emp_name'])}",
        f"{reshape_text('الرقم الوظيفي')}: {r['emp_id']}",
        f"{reshape_text('القسم')}: {reshape_text(r['dept'])}",
        f"{reshape_text('المسمى')}: {reshape_text(r.get('job_title', '-'))}",
        f"{reshape_text('تاريخ التقديم')}: {r.get('submission_date', 'N/A')[:10]}",
        "",
        f"{reshape_text('نوع الإجازة')}: {reshape_text(r.get('sub_type', '-'))}",
        f"{reshape_text('المدة')}: {r.get('days')} {reshape_text('أيام')}",
        f"{reshape_text('من')}: {r.get('start_date')} {reshape_text('إلى')}: {r.get('end_date')}",
    ]
    
    for line in lines:
        c.drawRightString(width - 2*cm, y, line) # محاذاة لليمين
        y -= 0.5*cm
    
    # الإقرار
    y -= 1*cm
    c.setFont("Arabic", 11)
    c.drawRightString(width - 2*cm, y, reshape_text("الإقرار:"))
    y -= 0.5*cm
    c.setFont("Arabic", 9)
    
    decl_text = "أقر أنا الموقع أدناه بأنني سأتمتع بإجازتي في موعدها المحدد أعلاه، ولن أتجاوز المدة إلا بخطاب رسمي..."
    # تقسيم النص الطويل
    words = reshape_text(decl_text).split()
    line_buffer = []
    for word in words:
        line_buffer.append(word)
        if len(" ".join(line_buffer)) > 80: # تقريباً
            c.drawRightString(width - 2*cm, y, " ".join(line_buffer))
            y -= 0.4*cm
            line_buffer = []
    if line_buffer:
        c.drawRightString(width - 2*cm, y, " ".join(line_buffer))
    
    # قسم الحسابات
    y -= 2*cm
    c.line(1*cm, y, width - 1*cm, y)
    y -= 0.5*cm
    c.setFont("Arabic", 12)
    c.drawRightString(width - 2*cm, y, reshape_text("تفاصيل مستحقات الإجازة"))
    y -= 0.8*cm
    
    c.setFont("Arabic", 10)
    calc_lines = [
        f"{reshape_text('الراتب الإجمالي')}: {salary} {reshape_text('ريال')}",
        f"{reshape_text('رصيد الإجازة السنوية')}: {annual_days} {reshape_text('يوم')}",
        f"{reshape_text('مبلغ البدل المستحق')}: {allowance} {reshape_text('ريال')}",
    ]
    
    for line in calc_lines:
        c.drawRightString(width - 2*cm, y, line)
        y -= 0.5*cm
        
    # التواقيع
    y -= 2*cm
    c.drawString(3*cm, y, reshape_text("المدير العام"))
    c.drawString(width/2, y, reshape_text("المدير المالي"))
    c.drawString(width - 4*cm, y, reshape_text("المحاسب"))
    
    c.save()
    buffer.seek(0)
    return buffer
