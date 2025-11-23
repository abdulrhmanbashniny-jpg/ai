def generate_pdf_html(r):
    """نسخة محسنة ومبسطة لتوليد PDF"""
    # استخدام خطوط النظام الافتراضية لتجنب مشاكل المسارات
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 2cm; }}
            body {{ font-family: sans-serif; }}
            .box {{ border: 1px solid #333; padding: 10px; margin-bottom: 10px; }}
            td {{ padding: 5px; }}
        </style>
    </head>
    <body>
        <h2 style="text-align:center;">نموذج إجازة (Leave Form)</h2>
        <div class="box">
            <table>
                <tr><td><strong>الاسم:</strong> {r['emp_name']}</td><td><strong>الرقم:</strong> {r['emp_id']}</td></tr>
                <tr><td><strong>القسم:</strong> {r['dept']}</td><td><strong>الوظيفة:</strong> {r.get('job_title','-')}</td></tr>
            </table>
        </div>
        
        <div class="box">
            <p><strong>نوع الإجازة:</strong> {r.get('sub_type')}</p>
            <p><strong>المدة:</strong> {r.get('days')} أيام (من {r.get('start_date')} إلى {r.get('end_date')})</p>
            <p><strong>البديل:</strong> {r.get('substitute_name', 'لا يوجد')}</p>
        </div>

        <div style="background:#eee; padding:10px; font-size:10px;">
            <strong>إقرار:</strong> أقر أنا {r['emp_name']} بصحة البيانات والالتزام بالأنظمة...
        </div>
        
        <br><br>
        <table style="width:100%; text-align:center;">
            <tr>
                <td>توقيع الموظف<br>{r['emp_name']}</td>
                <td>المدير المباشر<br>✅ {r.get('manager_note','موافق')}</td>
                <td>الموارد البشرية<br>✅ {r.get('hr_note','موافق')}</td>
            </tr>
        </table>
    </body>
    </html>
    """
    result = BytesIO()
    pisa.CreatePDF(BytesIO(html.encode("UTF-8")), result)
    return result.getvalue()
