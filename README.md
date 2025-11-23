# HR CRM — Repo Notes

هذا المستودع يحوي نسخة مبدئية لنظام HR CRM متكامل. المكونات المقترحة:
- db/init_supabase.sql: مخطط قاعدة البيانات
- app.py: نقطة الدخول (Streamlit)
- src/utils: أدوات الربط وقاعدة البيانات
- src/modules: وحدات النظام (إجازات، موافقات، ...)

خطوات الإعداد السريعة:
1. إنشاء مشروع Supabase ووضع اتصال في `st.secrets`:
   - supabase.url
   - supabase.key
2. تنفيذ SQL في ملف `db/init_supabase.sql` على قاعدة Supabase.
3. تشغيل التطبيق: `streamlit run app.py`
4. تكوين سياسات RLS وحماية المفاتيح السرية.

التكاملات المستقبلية:
- واتساب (Business API) أو Twilio لإرسال إشعارات
- خدمة البريد الإلكتروني
- نموذج AI: خدمة مستقلة (Cloud Function) لتحليل الطلبات

----