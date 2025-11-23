# src/utils/db.py
# Helpers for Supabase connection and basic DB operations

from supabase import create_client
import streamlit as st
from datetime import datetime

@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"خطأ في إعداد الاتصال بقاعدة البيانات: {e}")
        return None

def now_iso():
    return datetime.utcnow().isoformat()