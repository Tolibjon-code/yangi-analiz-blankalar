import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import plotly.express as px
import json
import sqlite3
import hashlib
import base64
import io
import os
import tempfile
from pathlib import Path
import yaml
from typing import Dict, List, Optional, Tuple
import uuid
import time

# =================== КОНФИГУРАЦИЯ ===================
st.set_page_config(
    page_title="Тиббий тахлиллар бошқарув тизими",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =================== CSS СТИЛЛАР ===================
st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        background: linear-gradient(90deg, #2E86C1, #3498DB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1.5rem;
        font-weight: 800;
    }
    .section-title {
        font-size: 1.8rem;
        color: #2C3E50;
        margin-top: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #3498DB;
    }
    .card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e0e0e0;
    }
    .status-normal {
        color: #27AE60;
        font-weight: bold;
        background-color: #E8F8F5;
        padding: 0.2rem 0.5rem;
        border-radius: 5px;
    }
    .status-abnormal {
        color: #E74C3C;
        font-weight: bold;
        background-color: #FDEDEC;
        padding: 0.2rem 0.5rem;
        border-radius: 5px;
    }
    .status-border {
        border-left: 5px solid;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.2rem;
        border-radius: 12px;
        text-align: center;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #2C3E50 0%, #3498DB 100%);
    }
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .tab-container {
        background: #F8F9FA;
        border-radius: 10px;
        padding: 1rem;
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }
    .streamlit-expanderHeader {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# =================== МАЪЛУМОТЛАР БАЗАСИ ===================
class DatabaseManager:
    def __init__(self):
        # Streamlit Cloud учун временный файл
        if 'STREAMLIT_SHARING' in os.environ or 'IS_STREAMLIT_CLOUD' in os.environ:
            self.db_path = os.path.join(tempfile.gettempdir(), 'medical_lab.db')
        else:
            self.db_path = 'medical_lab.db'
        
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.create_tables()
        self.init_default_data()
    
    def create_tables(self):
        """Базанинг барча таблицаларини яратиш"""
        cursor = self.conn.cursor()
        
        # Фойдаланувчилар
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Беморлар
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                birth_date DATE NOT NULL,
                gender TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Тахлил параметрлари ва нормалари
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                parameter_name TEXT NOT NULL,
                parameter_code TEXT UNIQUE NOT NULL,
                unit TEXT NOT NULL,
                min_age INTEGER DEFAULT 0,
                max_age INTEGER DEFAULT 100,
                gender_specific BOOLEAN DEFAULT 0,
                menstrual_phase_specific BOOLEAN DEFAULT 0,
                default_min_value REAL,
                default_max_value REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Ёш ва жинс боғлиқ нормалар
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS age_gender_norms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parameter_code TEXT NOT NULL,
                age_min INTEGER DEFAULT 0,
                age_max INTEGER DEFAULT 100,
                gender TEXT,
                menstrual_phase TEXT,
                min_value REAL NOT NULL,
                max_value REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Тахлил натижалари
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                test_type TEXT NOT NULL,
                parameter_code TEXT NOT NULL,
                result_value REAL NOT NULL,
                result_text TEXT,
                unit TEXT NOT NULL,
                reference_min REAL,
                reference_max REAL,
                status TEXT NOT NULL,
                test_date DATE NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')
        
        # Бланка шаблонлари
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                category TEXT NOT NULL,
                design_config TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Шифокорлар
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                specialization TEXT NOT NULL,
                license_number TEXT,
                phone TEXT NOT NULL,
                email TEXT,
                department TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def init_default_data(self):
        """Стандарт маълумотларни киритиш"""
        cursor = self.conn.cursor()
        
        # Администратор фойдаланувчи
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', admin_hash, 'Система администратори', 'admin'))
        
        # Стандарт тахлил параметрлари
        default_params = [
            ('Пренатал', 'β-HCG', 'BHCG', 'МЕ/л', 0, 100, 0, 0, 0, 25),
            ('Пренатал', 'PAPP-A', 'PAPPA', 'МЕ/л', 0, 100, 0, 0, 0.5, 2.5),
            ('Неонатал', 'TSH', 'TSH', 'мкМЕ/мл', 0, 30, 0, 0, 0, 10),
            ('Неонатал', '17-OHP', 'OHP17', 'нмоль/л', 0, 30, 0, 0, 0, 30),
            ('Биохимик', 'Глюкоза', 'GLUCOSE', 'ммоль/л', 0, 100, 0, 0, 3.9, 6.1),
            ('Биохимик', 'Креатинин', 'CREAT', 'мкмоль/л', 0, 100, 1, 0, 62, 106),
            ('Гормонлар', 'Эстрадиол', 'ESTRADIOL', 'пг/мл', 0, 100, 1, 1, 15, 350),
            ('Гормонлар', 'Прогестерон', 'PROGEST', 'нмоль/л', 0, 100, 1, 1, 0.3, 56),
            ('Клиник', 'WBC', 'WBC', '×10⁹/л', 0, 100, 0, 0, 4.0, 10.0),
            ('Клиник', 'HGB', 'HGB', 'г/л', 0, 100, 0, 0, 130, 160),
        ]
        
        for param in default_params:
            cursor.execute('''
                INSERT OR IGNORE INTO test_parameters 
                (category, parameter_name, parameter_code, unit, min_age, max_age, 
                 gender_specific, menstrual_phase_specific, default_min_value, default_max_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', param)
        
        # Ёш боғлиқ нормалар
        age_norms = [
            ('WBC', 0, 1, None, None, 6.0, 17.5),
            ('WBC', 1, 3, None, None, 6.0, 17.0),
            ('WBC', 4, 5, None, None, 5.5, 15.5),
            ('WBC', 6, 15, None, None, 4.5, 13.5),
            ('WBC', 16, 100, None, None, 4.0, 10.0),
            ('CREAT', 18, 30, 'Эркак', None, 62, 106),
            ('CREAT', 18, 30, 'Аёл', None, 44, 80),
            ('CREAT', 31, 50, 'Эркак', None, 62, 115),
            ('CREAT', 31, 50, 'Аёл', None, 44, 88),
            ('ESTRADIOL', 18, 50, 'Аёл', 'Фолликуляр', 15, 160),
            ('ESTRADIOL', 18, 50, 'Аёл', 'Овуляция', 34, 400),
            ('ESTRADIOL', 18, 50, 'Аёл', 'Лютеин', 27, 246),
            ('ESTRADIOL', 18, 50, 'Аёл', 'Менопауза', 0, 32),
        ]
        
        for norm in age_norms:
            cursor.execute('''
                INSERT OR IGNORE INTO age_gender_norms 
                (parameter_code, age_min, age_max, gender, menstrual_phase, min_value, max_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', norm)
        
        # Намуна шифокорлар
        cursor.execute("SELECT COUNT(*) FROM doctors")
        if cursor.fetchone()[0] == 0:
            doctors = [
                ('Норматова Дилрабо Алиевна', 'Терапевт', 'L-2023-001', '+99890 123-45-67', 'dilrabo@hospital.uz', 'Терапия', 'Тошкент ш., Юнусобод тумани'),
                ('Юсупов Абдулла Шавкатович', 'Хирург', 'L-2023-002', '+99890 987-65-43', 'abdulla@hospital.uz', 'Хирургия', 'Тошкент ш., Мирзо Улуғбек тумани'),
                ('Каримова Зебо Рахимовна', 'Педиатр', 'L-2023-003', '+99890 555-44-33', 'zebo@hospital.uz', 'Педиатрия', 'Тошкент ш., Шайхонтохур тумани'),
            ]
            
            for doctor in doctors:
                cursor.execute('''
                    INSERT INTO doctors (full_name, specialization, license_number, phone, email, department, address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', doctor)
        
        # Намуна шаблонлар
        cursor.execute("SELECT COUNT(*) FROM form_templates")
        if cursor.fetchone()[0] == 0:
            templates = [
                ('Стандарт бланка', 'Қон тахлили', 'Умумий', json.dumps({
                    "primary_color": "#3498DB",
                    "secondary_color": "#2E86C1",
                    "font_family": "Arial",
                    "font_size": 12,
                    "sections": ["Бемор маълумотлари", "Тахлил натижалари", "Норма қийматлари"],
                    "features": {"include_logo": True, "include_qr": True, "include_signature": True}
                })),
                ('Гормон бланкаси', 'Гормонлар', 'Махсус', json.dumps({
                    "primary_color": "#E74C3C",
                    "secondary_color": "#C0392B",
                    "font_family": "Calibri",
                    "font_size": 11,
                    "sections": ["Бемор маълумотлари", "Тахлил натижалари", "Норма қийматлари", "Шифокор тавсиялари"],
                    "features": {"include_logo": True, "include_qr": False, "include_signature": True}
                })),
            ]
            
            for template in templates:
                cursor.execute('''
                    INSERT INTO form_templates (template_name, template_type, category, design_config)
                    VALUES (?, ?, ?, ?)
                ''', template)
        
        self.conn.commit()
    
    def get_user(self, username: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        return cursor.fetchone()
    
    def verify_password(self, username: str, password: str) -> bool:
        user = self.get_user(username)
        if not user:
            return False
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return user[2] == password_hash
    
    def execute_query(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor
    
    def get_cursor(self):
        return self.conn.cursor()

# =================== БАЗАНИ ИНИЦИАЛИЗАЦИЯЛАШ ===================
@st.cache_resource
def init_database():
    return DatabaseManager()

db = init_database()

# =================== ТИЗИМГА КИРИШ ===================
def login_page():
    """Кириш саҳифаси"""
    st.markdown('<h1 class="main-title">🔐 Тиббий тахлиллар тизимига кириш</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            
            username = st.text_input("👤 Фойдаланувчи номи", key="login_username")
            password = st.text_input("🔑 Парол", type="password", key="login_password")
            
            col_a, col_b = st.columns(2)
            with col_a:
                login_btn = st.button("🚪 Тизимга кириш", use_container_width=True)
                if login_btn:
                    if username and password:
                        if db.verify_password(username, password):
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.success("✅ Муваффақиятли кирилди!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Нотўғри фойдаланувчи номи ёки парол")
                    else:
                        st.warning("⚠️ Фойдаланувчи номи ва паролни киритинг")
            
            with col_b:
                if st.button("👥 Рўйхатдан ўтиш", use_container_width=True):
                    st.session_state.show_register = True
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Тест учун тез кириш
            with st.expander("Тест учун маълумот"):
                st.info("""
                **Тест учун:**\n
                Фойдаланувчи: `admin`\n
                Парол: `admin123`
                """)

# =================== АСОСИЙ САҲИФА ===================
def main_page():
    """Асосий иш саҳифаси"""
    
    # Ён панел менюси
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        st.markdown("---")
        
        menu_options = [
            "🏠 Асосий саҳифа",
            "👥 Беморлар бошқаруви",
            "📊 Тахлил натижалари",
            "⚙️ Созламалар",
            "📋 Бланка шаблонлари",
            "📈 Ҳисоботлар",
            "👨‍⚕️ Шифокорлар",
            "🔧 Система созламалари"
        ]
        
        menu_option = st.selectbox("📋 Меню", menu_options, key="main_menu")
        
        st.markdown("---")
        
        # Тезиклик статистика
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM patients")
            patient_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM test_results WHERE DATE(test_date) = DATE('now')")
            today_tests = cursor.fetchone()[0]
        except:
            patient_count = 0
            today_tests = 0
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.2rem;
            border-radius: 12px;
            text-align: center;
            margin: 1rem 0;
        ">
            <h4>📊 Статистика</h4>
            <p>👥 Беморлар: <b>{patient_count}</b></p>
            <p>📅 Бугунги тахлиллар: <b>{today_tests}</b></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("🚪 Чиқиш", use_container_width=True, key="logout_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ Чиқиш амалга оширилди!")
            time.sleep(1)
            st.rerun()
    
    # Асосий контент
    if menu_option == "🏠 Асосий саҳифа":
        show_dashboard()
    elif menu_option == "👥 Беморлар бошқаруви":
        manage_patients()
    elif menu_option == "📊 Тахлил натижалари":
        manage_test_results()
    elif menu_option == "⚙️ Созламалар":
        manage_settings()
    elif menu_option == "📋 Бланка шаблонлари":
        manage_templates()
    elif menu_option == "📈 Ҳисоботлар":
        show_reports()
    elif menu_option == "👨‍⚕️ Шифокорлар":
        manage_doctors()
    elif menu_option == "🔧 Система созламалари":
        system_settings()

# =================== АСОСИЙ ПАНЕЛЬ ===================
def show_dashboard():
    """Асосий статистика панели"""
    st.markdown('<h1 class="main-title">🏥 Тиббий тахлиллар бошқарув тизими</h1>', unsafe_allow_html=True)
    
    # Статистика карточкалари
    col1, col2, col3, col4 = st.columns(4)
    
    cursor = db.get_cursor()
    
    with col1:
        cursor.execute("SELECT COUNT(*) FROM patients")
        total_patients = cursor.fetchone()[0]
        st.markdown(f"""
        <div class="metric-card">
            <h3>👥</h3>
            <h2>{total_patients}</h2>
            <p>Жами беморлар</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        cursor.execute("SELECT COUNT(*) FROM test_results")
        total_tests = cursor.fetchone()[0]
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <h3>📊</h3>
            <h2>{total_tests}</h2>
            <p>Жами тахлиллар</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        cursor.execute("SELECT COUNT(DISTINCT patient_id) FROM test_results WHERE DATE(test_date) = DATE('now')")
        result = cursor.fetchone()
        today_patients = result[0] if result else 0
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <h3>📅</h3>
            <h2>{today_patients}</h2>
            <p>Бугунги беморлар</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        cursor.execute("""
            SELECT COUNT(*) FROM test_results 
            WHERE status != 'normal' 
            AND DATE(test_date) = DATE('now')
        """)
        result = cursor.fetchone()
        abnormal_today = result[0] if result else 0
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <h3>⚠️</h3>
            <h2>{abnormal_today}</h2>
            <p>Бугунги патология</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Охирги тахлиллар
    st.markdown('<h3 class="section-title">🔄 Охирги тахлил натижалари</h3>', unsafe_allow_html=True)
    
    cursor.execute("""
        SELECT p.full_name, tr.test_type, tr.parameter_code, tr.result_value, 
               tr.unit, tr.status, tr.test_date
        FROM test_results tr
        JOIN patients p ON tr.patient_id = p.id
        ORDER BY tr.created_at DESC
        LIMIT 10
    """)
    
    recent_tests = cursor.fetchall()
    
    if recent_tests:
        df = pd.DataFrame(recent_tests, columns=[
            'Бемор', 'Тахлил тури', 'Параметр', 'Қиймат', 
            'Ўлчов бирлиги', 'Холат', 'Сана'
        ])
        
        # Холатга қараб ранг бериш
        def color_status(val):
            if val == 'normal':
                return 'background-color: #E8F8F5; color: #27AE60; font-weight: bold;'
            elif val == 'low':
                return 'background-color: #FFF3CD; color: #856404; font-weight: bold;'
            else:
                return 'background-color: #F8D7DA; color: #721C24; font-weight: bold;'
        
        styled_df = df.style.applymap(color_status, subset=['Холат'])
        st.dataframe(styled_df, use_container_width=True, height=400)
    else:
        st.info("📭 Ҳали тахлил натижалари мавжуд эмас")
        
        # Намуна маълумотлар
        with st.expander("Намуна маълумотларни қўшиш"):
            if st.button("Намуна маълумотларни яратиш"):
                cursor.execute("SELECT id FROM patients LIMIT 1")
                patient = cursor.fetchone()
                
                if patient:
                    sample_data = [
                        (patient[0], 'Биохимик', 'GLUCOSE', 5.8, 'ммоль/л', 3.9, 6.1, 'normal', date.today()),
                        (patient[0], 'Клиник', 'WBC', 7.2, '×10⁹/л', 4.0, 10.0, 'normal', date.today()),
                        (patient[0], 'Клиник', 'HGB', 145, 'г/л', 130, 160, 'normal', date.today()),
                    ]
                    
                    for data in sample_data:
                        cursor.execute('''
                            INSERT INTO test_results 
                            (patient_id, test_type, parameter_code, result_value, unit, 
                             reference_min, reference_max, status, test_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', data)
                    
                    db.conn.commit()
                    st.success("✅ Намуна маълумотлар қўшилди!")
                    st.rerun()

# =================== БЕМОРЛАР БОШҚАРУВИ ===================
def manage_patients():
    """Беморлар бошқаруви"""
    st.markdown('<h1 class="section-title">👥 Беморлар бошқаруви</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 Янги бемор", "📋 Беморлар рўйхати", "🔍 Беморни излаш"])
    
    with tab1:
        st.markdown("### 🆕 Янги бемор қўшиш")
        
        with st.form("new_patient_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                full_name = st.text_input("👤 Исми-шарифи*")
                birth_date = st.date_input("📅 Туғилган сана*", value=date(1990, 1, 1))
                gender = st.selectbox("⚤ Жинси*", ["Эркак", "Аёл"])
            
            with col2:
                phone = st.text_input("📞 Телефон рақами")
                address = st.text_area("🏠 Манзил")
                patient_id = st.text_input("🆔 Бемор ID", 
                                         value=f"P-{datetime.now().strftime('%Y%m%d')}-{np.random.randint(1000,9999)}")
            
            notes = st.text_area("📝 Қўшимча маълумотлар")
            
            submitted = st.form_submit_button("💾 Сақлаш", use_container_width=True)
            
            if submitted:
                if full_name and birth_date and gender:
                    cursor = db.get_cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO patients 
                            (patient_id, full_name, birth_date, gender, phone, address)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (patient_id, full_name, birth_date, gender, phone, address))
                        db.conn.commit()
                        st.success(f"✅ Бемор {full_name} муваффақиятли қўшилди!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("❌ Бундай Бемор ID аллақачон мавжуд")
                    except Exception as e:
                        st.error(f"❌ Хатолик: {str(e)}")
                else:
                    st.error("⚠️ * белгиланган майдонларни тўлдиринг")
    
    with tab2:
        st.markdown("### 📋 Беморлар рўйхати")
        
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
            patients = cursor.fetchall()
        except:
            patients = []
        
        if patients:
            df = pd.DataFrame(patients, columns=[
                'ID', 'Бемор ID', 'Исми', 'Туғилган сана', 
                'Жинси', 'Телефон', 'Манзил', 'Яратилган'
            ])
            
            # Филтрлар
            col_search, col_filter = st.columns(2)
            with col_search:
                search_term = st.text_input("🔍 Излаш (исм боʻйича)", key="patient_search")
            
            with col_filter:
                filter_gender = st.selectbox("Жинс боʻйича", ["Ҳаммаси", "Эркак", "Аёл"], key="gender_filter")
            
            if search_term:
                df = df[df['Исми'].str.contains(search_term, case=False, na=False)]
            
            if filter_gender != "Ҳаммаси":
                df = df[df['Жинси'] == filter_gender]
            
            st.dataframe(df, use_container_width=True, height=500)
            
            # Экспорт қилиш
            col_exp1, col_exp2 = st.columns(2)
            with col_exp1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 CSV юклаб олиш",
                    data=csv,
                    file_name="bemorlar_royhati.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Таҳрирлаш ва ўчириш
            with st.expander("Беморни таҳрирлаш ёки ўчириш"):
                selected_id = st.selectbox("Беморни танланг", df['ID'].tolist())
                
                if selected_id:
                    # Бемор маълумотларини олиш
                    cursor.execute("SELECT * FROM patients WHERE id = ?", (selected_id,))
                    patient_data = cursor.fetchone()
                    
                    if patient_data:
                        col_edit1, col_edit2 = st.columns(2)
                        with col_edit1:
                            edit_name = st.text_input("Исми-шарифи", value=patient_data[2])
                            edit_birth_date = st.date_input("Туғилган сана", value=datetime.strptime(patient_data[3], '%Y-%m-%d').date() if isinstance(patient_data[3], str) else patient_data[3])
                        with col_edit2:
                            edit_gender = st.selectbox("Жинси", ["Эркак", "Аёл"], index=0 if patient_data[4] == "Эркак" else 1)
                            edit_phone = st.text_input("Телефон", value=patient_data[5] or "")
                        
                        edit_address = st.text_area("Манзил", value=patient_data[6] or "")
                        
                        col_save, col_delete = st.columns(2)
                        with col_save:
                            if st.button("💾 Ўзгартиришларни сақлаш", use_container_width=True):
                                cursor.execute('''
                                    UPDATE patients 
                                    SET full_name = ?, birth_date = ?, gender = ?, phone = ?, address = ?
                                    WHERE id = ?
                                ''', (edit_name, edit_birth_date, edit_gender, edit_phone, edit_address, selected_id))
                                db.conn.commit()
                                st.success("✅ Бемор маълумотлари янгиланди!")
                                st.rerun()
                        
                        with col_delete:
                            if st.button("🗑️ Беморни ўчириш", use_container_width=True):
                                # Аввал боглик натижаларни ўчирамиз
                                cursor.execute("DELETE FROM test_results WHERE patient_id = ?", (selected_id,))
                                cursor.execute("DELETE FROM patients WHERE id = ?", (selected_id,))
                                db.conn.commit()
                                st.success("✅ Бемор ва унинг тахлил натижалари ўчирилди!")
                                st.rerun()
        else:
            st.info("📭 Ҳали беморлар мавжуд эмас")
            
            # Намуна бемор қўшиш
            if st.button("Намуна бемор қўшиш"):
                cursor.execute('''
                    INSERT INTO patients (patient_id, full_name, birth_date, gender, phone, address)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    f"P-{datetime.now().strftime('%Y%m%d')}-0001",
                    "Намуна Бемор",
                    "1990-01-01",
                    "Эркак",
                    "+99890 123-45-67",
                    "Тошкент ш."
                ))
                db.conn.commit()
                st.success("✅ Намуна бемор қўшилди!")
                st.rerun()
    
    with tab3:
        st.markdown("### 🔍 Беморни излаш")
        
        search_by = st.radio("Излаш усули", ["ID буйича", "Исм буйича", "Телефон буйича"], horizontal=True)
        search_value = st.text_input("Қидирув қиймати")
        
        if st.button("🔍 Излаш", use_container_width=True):
            if search_value:
                cursor = db.get_cursor()
                
                try:
                    if search_by == "ID буйича":
                        cursor.execute("SELECT * FROM patients WHERE patient_id LIKE ?", 
                                     (f"%{search_value}%",))
                    elif search_by == "Исм буйича":
                        cursor.execute("SELECT * FROM patients WHERE full_name LIKE ?", 
                                     (f"%{search_value}%",))
                    else:
                        cursor.execute("SELECT * FROM patients WHERE phone LIKE ?", 
                                     (f"%{search_value}%",))
                    
                    results = cursor.fetchall()
                    
                    if results:
                        st.success(f"✅ {len(results)} та натижа топилди")
                        
                        for patient in results:
                            with st.expander(f"👤 {patient[2]} ({patient[1]})"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Туғилган сана:** {patient[3]}")
                                    st.write(f"**Жинси:** {patient[4]}")
                                with col2:
                                    st.write(f"**Телефон:** {patient[5] if patient[5] else 'Номаълум'}")
                                    st.write(f"**Манзил:** {patient[6] if patient[6] else 'Номаълум'}")
                                
                                if st.button("📊 Тахлил қўшиш", key=f"add_test_{patient[0]}"):
                                    st.session_state.selected_patient = patient[0]
                                    st.info(f"Тахлил қўшиш учун бемор танланди: {patient[2]}")
                    else:
                        st.warning("🔍 Бемор топилмади")
                except Exception as e:
                    st.error(f"Хатолик: {str(e)}")
            else:
                st.warning("Қидирув қийматини киритинг")

# =================== ТАХЛИЛ НАТИЖАЛАРИ ===================
def manage_test_results():
    """Тахлил натижалари бошқаруви"""
    st.markdown('<h1 class="section-title">📊 Тахлил натижалари</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["➕ Янги тахлил", "📋 Натижалар", "📈 Статистика"])
    
    with tab1:
        st.markdown("### 🆕 Янги тахлил қўшиш")
        
        # Беморни танлаш
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT id, patient_id, full_name FROM patients ORDER BY full_name")
            patients = cursor.fetchall()
        except:
            patients = []
        
        if not patients:
            st.warning("⚠️ Аввал бемор қўшинг")
            return
        
        patient_options = {f"{p[2]} ({p[1]})": p[0] for p in patients}
        selected_patient = st.selectbox("👤 Беморни танланг*", list(patient_options.keys()))
        patient_id = patient_options[selected_patient]
        
        # Бемор маълумотлари
        cursor.execute("SELECT birth_date, gender FROM patients WHERE id = ?", (patient_id,))
        patient_info = cursor.fetchone()
        if patient_info:
            birth_date, gender = patient_info
            # Ёшини ҳисоблаш
            try:
                if isinstance(birth_date, str):
                    birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d').date()
                else:
                    birth_date_obj = birth_date
                age = (date.today() - birth_date_obj).days // 365
            except:
                age = 30
        else:
            age = 30
            gender = "Эркак"
        
        st.info(f"**Бемор маълумотлари:** Ёши: {age} | Жинси: {gender}")
        
        # Менструация фазаси (аёл беморлар учун)
        menstrual_phase = None
        if gender == "Аёл" and age >= 12 and age <= 55:
            menstrual_phase = st.selectbox(
                "🩸 Менструация фазаси (ихтиёрий)",
                ["", "Фолликуляр", "Овуляция", "Лютеин", "Менопауза", "Номаълум"]
            )
            if menstrual_phase == "":
                menstrual_phase = None
        
        # Тахлил тури
        test_type = st.selectbox(
            "🔬 Тахлил тури*",
            ["Пренатал", "Неонатал", "ИФА", "Биохимик", "Клиник", "Гормонлар", "Бошқа"]
        )
        
        # Параметрларни танлаш
        cursor.execute("""
            SELECT parameter_code, parameter_name, unit, default_min_value, default_max_value
            FROM test_parameters 
            WHERE category = ? OR category = 'Бошқа'
            ORDER BY parameter_name
        """, (test_type,))
        parameters = cursor.fetchall()
        
        if not parameters:
            st.warning("⚠️ Бу тахлил тури учун параметрлар мавжуд эмас")
            
            # Автомат параметр қўшиш
            if st.button("Автомат параметрлар қўшиш"):
                sample_params = [
                    (test_type, f"{test_type} параметр 1", f"{test_type[:3]}_PAR1", "ед.", 0, 100),
                    (test_type, f"{test_type} параметр 2", f"{test_type[:3]}_PAR2", "ед.", 0, 200),
                ]
                
                for param in sample_params:
                    cursor.execute('''
                        INSERT OR IGNORE INTO test_parameters 
                        (category, parameter_name, parameter_code, unit, 
                         min_age, max_age, default_min_value, default_max_value)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', param + (0, 100, 0, 100))
                
                db.conn.commit()
                st.success("✅ Автомат параметрлар қўшилди!")
                st.rerun()
            return
        
        # Тахлил натижаларини киритиш
        st.markdown("### 📝 Натижаларни киритиш")
        
        results = []
        test_date = st.date_input("📅 Тахлил санаси", value=date.today())
        notes = st.text_area("📝 Изохлар")
        
        for param in parameters:
            param_code, param_name, unit, default_min, default_max = param
            
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    result_value = st.number_input(
                        f"{param_name} ({unit})",
                        min_value=0.0,
                        max_value=10000.0,
                        value=0.0,
                        step=0.1,
                        key=f"value_{param_code}_{patient_id}"
                    )
                
                with col2:
                    # Нормаларни олиш
                    cursor.execute('''
                        SELECT min_value, max_value FROM age_gender_norms
                        WHERE parameter_code = ? 
                        AND (age_min <= ? OR age_min IS NULL)
                        AND (age_max >= ? OR age_max IS NULL)
                        AND (gender = ? OR gender IS NULL)
                        AND (menstrual_phase = ? OR menstrual_phase IS NULL)
                        LIMIT 1
                    ''', (param_code, age, age, gender, menstrual_phase))
                    
                    norm = cursor.fetchone()
                    
                    if norm and norm[0] is not None and norm[1] is not None:
                        min_val, max_val = norm
                        st.info(f"**Норма:** {min_val:.2f} - {max_val:.2f} {unit}")
                        
                        # Холатни аниклаш
                        if result_value < min_val:
                            status = "low"
                            status_text = "⬇️ Паст"
                        elif result_value > max_val:
                            status = "high"
                            status_text = "⬆️ Юқори"
                        else:
                            status = "normal"
                            status_text = "✅ Норма"
                    else:
                        if default_min is not None and default_max is not None:
                            min_val, max_val = default_min, default_max
                            st.info(f"**Норма:** {default_min:.2f} - {default_max:.2f} {unit}")
                            
                            if result_value < default_min:
                                status = "low"
                                status_text = "⬇️ Паст"
                            elif result_value > default_max:
                                status = "high"
                                status_text = "⬆️ Юқори"
                            else:
                                status = "normal"
                                status_text = "✅ Норма"
                        else:
                            min_val, max_val = None, None
                            status = "unknown"
                            status_text = "❓ Норма номаълум"
                
                with col3:
                    st.markdown(f"**Холат:**<br>{status_text}", unsafe_allow_html=True)
                
                results.append({
                    'parameter_code': param_code,
                    'parameter_name': param_name,
                    'result_value': result_value,
                    'unit': unit,
                    'status': status,
                    'status_text': status_text,
                    'min_value': min_val if 'min_val' in locals() and min_val is not None else default_min,
                    'max_value': max_val if 'max_val' in locals() and max_val is not None else default_max
                })
        
        # Сақлаш
        if st.button("💾 Тахлил натижаларини сақлаш", use_container_width=True):
            success_count = 0
            for result in results:
                try:
                    cursor.execute('''
                        INSERT INTO test_results 
                        (patient_id, test_type, parameter_code, result_value, 
                         unit, reference_min, reference_max, status, test_date, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        patient_id, test_type, result['parameter_code'], 
                        result['result_value'], result['unit'],
                        result['min_value'], result['max_value'],
                        result['status'], test_date, notes
                    ))
                    success_count += 1
                except Exception as e:
                    st.error(f"Хатолик {result['parameter_name']} учун: {str(e)}")
            
            if success_count > 0:
                db.conn.commit()
                st.success(f"✅ {success_count} та тахлил натижалари муваффақиятли сақланди!")
                
                # Натижани кўриш
                if st.button("📄 Натижани кўриш"):
                    st.rerun()
    
    with tab2:
        st.markdown("### 📋 Тахлил натижалари рўйхати")
        
        # Филтрлар
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            cursor.execute("SELECT DISTINCT test_type FROM test_results")
            test_types_result = cursor.fetchall()
            test_types = [""] + [t[0] for t in test_types_result if t[0]]
            filter_type = st.selectbox("Тахлил тури", test_types)
        
        with col_filter2:
            start_date = st.date_input("Бошланиш санаси", value=date.today().replace(day=1))
        
        with col_filter3:
            end_date = st.date_input("Тугаш санаси", value=date.today())
        
        # Натижаларни олиш
        try:
            query = """
                SELECT p.full_name, tr.test_type, tr.parameter_code, 
                       tr.result_value, tr.unit, tr.status, tr.test_date
                FROM test_results tr
                JOIN patients p ON tr.patient_id = p.id
                WHERE tr.test_date BETWEEN ? AND ?
            """
            
            params = [start_date, end_date]
            
            if filter_type:
                query += " AND tr.test_type = ?"
                params.append(filter_type)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if results:
                df = pd.DataFrame(results, columns=[
                    'Бемор', 'Тахлил тури', 'Параметр', 'Қиймат', 
                    'Ўлчов бирлиги', 'Холат', 'Сана'
                ])
                
                # Фильтр қўшиш
                col_search, col_status = st.columns(2)
                with col_search:
                    patient_filter = st.text_input("Бемор исми бўйича филтр")
                
                with col_status:
                    status_filter = st.selectbox("Холат бўйича филтр", 
                                              ["Ҳаммаси", "Норма", "Паст", "Юқори", "Номаълум"])
                
                if patient_filter:
                    df = df[df['Бемор'].str.contains(patient_filter, case=False, na=False)]
                
                if status_filter != "Ҳаммаси":
                    status_map = {"Норма": "normal", "Паст": "low", "Юқори": "high", "Номаълум": "unknown"}
                    df = df[df['Холат'] == status_map[status_filter]]
                
                if not df.empty:
                    st.dataframe(df, use_container_width=True, height=500)
                    
                    # Статистика
                    st.markdown("### 📈 Статистика")
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    
                    with col_stat1:
                        total_tests = len(df)
                        st.metric("Жами тахлиллар", total_tests)
                    
                    with col_stat2:
                        normal_tests = len(df[df['Холат'] == 'normal'])
                        st.metric("Норма тахлиллар", normal_tests)
                    
                    with col_stat3:
                        abnormal_rate = ((total_tests - normal_tests) / total_tests * 100) if total_tests > 0 else 0
                        st.metric("Патология фоиз", f"{abnormal_rate:.1f}%")
                else:
                    st.info("📭 Филтрга мос натижалар топилмади")
            else:
                st.info("📭 Танланган давр учун натижалар топилмади")
        except Exception as e:
            st.error(f"Маълумотларни олишда хатолик: {str(e)}")
    
    with tab3:
        st.markdown("### 📈 Тахлиллар статистикаси")
        
        # Давр танлаш
        period = st.selectbox("Давр", 
                            ["Сўнгги 7 кун", "Сўнгги 30 кун", "Сўнгги 3 ой", "Сўнгги 1 йил", "Ҳамма вақт"])
        
        # Даврни аниклаш
        today = date.today()
        if period == "Сўнгги 7 кун":
            start_date = today - timedelta(days=7)
        elif period == "Сўнгги 30 кун":
            start_date = today - timedelta(days=30)
        elif period == "Сўнгги 3 ой":
            start_date = today - timedelta(days=90)
        elif period == "Сўнгги 1 йил":
            start_date = today - timedelta(days=365)
        else:
            start_date = date(2000, 1, 1)
        
        # Маълумотларни олиш
        try:
            cursor.execute("""
                SELECT 
                    test_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'normal' THEN 1 ELSE 0 END) as normal,
                    SUM(CASE WHEN status != 'normal' THEN 1 ELSE 0 END) as abnormal
                FROM test_results
                WHERE test_date >= ?
                GROUP BY test_type
                ORDER BY total DESC
            """, (start_date,))
            
            stats = cursor.fetchall()
            
            if stats:
                df_stats = pd.DataFrame(stats, columns=['Тахлил тури', 'Жами', 'Норма', 'Патология'])
                
                # График
                fig = px.bar(df_stats, x='Тахлил тури', y=['Норма', 'Патология'],
                            title='Тахлиллар тарқалиши',
                            color_discrete_map={'Норма': '#27AE60', 'Патология': '#E74C3C'},
                            barmode='stack')
                
                fig.update_layout(height=400, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
                
                # Жадвал
                st.dataframe(df_stats, use_container_width=True)
            else:
                st.info("📭 Статистика маълумотлари мавжуд эмас")
        except Exception as e:
            st.error(f"Статистикани олишда хатолик: {str(e)}")

# =================== СОЗЛАМАЛАР ===================
def manage_settings():
    """Тахлил параметрлари ва нормалари созламалари"""
    st.markdown('<h1 class="section-title">⚙️ Созламалар</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔬 Параметрлар", 
        "📏 Нормалар", 
        "🔄 Ўлчов бирликлари",
        "📊 Категориялар"
    ])
    
    with tab1:
        st.markdown("### 🔬 Тахлил параметрлари")
        
        # Янги параметр қўшиш
        with st.expander("➕ Янги параметр қўшиш", expanded=False):
            with st.form("new_parameter_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    category = st.selectbox("Категория*", 
                                          ["Пренатал", "Неонатал", "ИФА", "Биохимик", 
                                           "Клиник", "Гормонлар", "Бошқа"])
                    parameter_name = st.text_input("Параметр номи*")
                    parameter_code = st.text_input("Параметр коди*").upper()
                    unit = st.text_input("Ўлчов бирлиги*")
                
                with col2:
                    gender_specific = st.checkbox("Жинсга боғлиқ")
                    menstrual_specific = st.checkbox("Менструация фазасига боғлиқ")
                    default_min = st.number_input("Стандарт мин. қиймат", value=0.0, format="%.2f")
                    default_max = st.number_input("Стандарт макс. қиймат", value=100.0, format="%.2f")
                
                submitted = st.form_submit_button("💾 Параметр қўшиш")
                
                if submitted:
                    if category and parameter_name and parameter_code and unit:
                        cursor = db.get_cursor()
                        try:
                            cursor.execute('''
                                INSERT INTO test_parameters 
                                (category, parameter_name, parameter_code, unit,
                                 gender_specific, menstrual_phase_specific,
                                 default_min_value, default_max_value)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (category, parameter_name, parameter_code, unit,
                                 int(gender_specific), int(menstrual_specific), 
                                 default_min, default_max))
                            db.conn.commit()
                            st.success("✅ Параметр муваффақиятли қўшилди!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Бундай параметр коди аллақачон мавжуд")
                        except Exception as e:
                            st.error(f"❌ Хатолик: {str(e)}")
                    else:
                        st.error("⚠️ * белгиланган майдонларни тўлдиринг")
        
        # Параметрлар рўйхати
        st.markdown("### 📋 Параметрлар рўйхати")
        
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT * FROM test_parameters ORDER BY category, parameter_name")
            parameters = cursor.fetchall()
        except:
            parameters = []
        
        if parameters:
            df_params = pd.DataFrame(parameters, columns=[
                'ID', 'Категория', 'Номи', 'Коди', 'Ўлчов бирлиги',
                'Мин ёш', 'Макс ёш', 'Жинсга боғлиқ', 'Менструацияга боғлиқ',
                'Стандарт мин', 'Стандарт макс', 'Яратилган', 'Янгиланган'
            ])
            
            # Филтр
            categories = ["Ҳаммаси"] + sorted(df_params['Категория'].unique().tolist())
            filter_category = st.selectbox("Категория бўйича филтр", categories)
            
            if filter_category != "Ҳаммаси":
                df_params = df_params[df_params['Категория'] == filter_category]
            
            st.dataframe(df_params, use_container_width=True, height=400)
            
            # Таҳрирлаш
            with st.expander("✏️ Параметрни таҳрирлаш"):
                selected_id = st.selectbox("Таҳрирлаш учун параметр танланг", 
                                          df_params['ID'].tolist())
                
                if selected_id:
                    cursor.execute("SELECT * FROM test_parameters WHERE id = ?", (selected_id,))
                    param = cursor.fetchone()
                    
                    if param:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_name = st.text_input("Янги ном", value=param[2])
                            new_code = st.text_input("Янги код", value=param[3]).upper()
                            new_unit = st.text_input("Янги ўлчов бирлиги", value=param[4])
                        
                        with col2:
                            new_min = st.number_input("Янги мин. қиймат", 
                                                    value=float(param[9] if param[9] else 0))
                            new_max = st.number_input("Янги макс. қиймат", 
                                                    value=float(param[10] if param[10] else 100))
                        
                        if st.button("💾 Ўзгартиришларни сақлаш"):
                            cursor.execute('''
                                UPDATE test_parameters 
                                SET parameter_name = ?, parameter_code = ?, unit = ?,
                                    default_min_value = ?, default_max_value = ?,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = ?
                            ''', (new_name, new_code, new_unit, new_min, new_max, selected_id))
                            db.conn.commit()
                            st.success("✅ Параметр муваффақиятли янгиланди!")
                            st.rerun()
        else:
            st.info("📭 Ҳали параметрлар мавжуд эмас")
    
    with tab2:
        st.markdown("### 📏 Нормаларни бошқариш")
        
        # Параметрни танлаш
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT parameter_code, parameter_name FROM test_parameters ORDER BY parameter_name")
            params = cursor.fetchall()
        except:
            params = []
        
        if params:
            param_options = {f"{p[1]} ({p[0]})": p[0] for p in params}
            selected_param = st.selectbox("Параметрни танланг", list(param_options.keys()))
            param_code = param_options[selected_param]
            
            # Ҳозирги нормалар
            st.markdown(f"#### 📋 {selected_param} учун нормалар")
            
            cursor.execute('''
                SELECT id, age_min, age_max, gender, menstrual_phase, 
                       min_value, max_value, created_at
                FROM age_gender_norms
                WHERE parameter_code = ?
                ORDER BY age_min, gender
            ''', (param_code,))
            
            norms = cursor.fetchall()
            
            if norms:
                df_norms = pd.DataFrame(norms, columns=[
                    'ID', 'Ёш мин', 'Ёш макс', 'Жинси', 'Менструация фазаси',
                    'Мин қиймат', 'Макс қиймат', 'Яратилган'
                ])
                st.dataframe(df_norms, use_container_width=True)
                
                # Нормани ўчириш
                with st.expander("🗑️ Нормани ўчириш"):
                    norm_id = st.selectbox("Ўчириш учун норма танланг", df_norms['ID'].tolist())
                    if st.button("Нормани ўчириш", use_container_width=True):
                        cursor.execute("DELETE FROM age_gender_norms WHERE id = ?", (norm_id,))
                        db.conn.commit()
                        st.success("✅ Норма ўчирилди!")
                        st.rerun()
            else:
                st.info("⚠️ Ушбу параметр учун нормалар ўрнатилмаган")
            
            # Янги норма қўшиш
            with st.expander("➕ Янги норма қўшиш"):
                with st.form("new_norm_form", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        age_min = st.number_input("Ёш (мин)", min_value=0, max_value=120, value=0)
                        age_max = st.number_input("Ёш (макс)", min_value=0, max_value=120, value=100)
                    
                    with col2:
                        gender = st.selectbox("Жинси", ["Ҳар қандай", "Эркак", "Аёл"])
                        if gender == "Ҳар қандай":
                            gender_val = None
                        else:
                            gender_val = gender
                        
                        menstrual_phase = None
                        if gender == "Аёл":
                            menstrual_phase = st.selectbox("Менструация фазаси", 
                                                         ["", "Фолликуляр", "Овуляция", "Лютеин", "Менопауза"])
                            if not menstrual_phase:
                                menstrual_phase_val = None
                            else:
                                menstrual_phase_val = menstrual_phase
                        else:
                            menstrual_phase_val = None
                    
                    with col3:
                        min_value = st.number_input("Мин. норма қиймати", value=0.0, format="%.2f")
                        max_value = st.number_input("Макс. норма қиймати", value=100.0, format="%.2f")
                    
                    submitted = st.form_submit_button("💾 Норма қўшиш")
                    
                    if submitted:
                        cursor.execute('''
                            INSERT INTO age_gender_norms 
                            (parameter_code, age_min, age_max, gender, 
                             menstrual_phase, min_value, max_value)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (param_code, age_min, age_max, gender_val, 
                             menstrual_phase_val, min_value, max_value))
                        db.conn.commit()
                        st.success("✅ Норма муваффақиятли қўшилди!")
                        st.rerun()
        else:
            st.info("📭 Параметрлар мавжуд эмас")
    
    with tab3:
        st.markdown("### 🔄 Ўлчов бирликлари")
        
        # Ўлчов бирликлари рўйхати
        units = {
            "Қон тахлиллари": ["×10⁹/л", "×10¹²/л", "г/л", "%", "фл", "пг"],
            "Биохимик": ["ммоль/л", "мкмоль/л", "г/л", "Е/л", "мг/дл"],
            "Гормонлар": ["МЕ/л", "мкМЕ/мл", "нг/мл", "пг/мл", "нмоль/л"],
            "ИФА": ["S/CO", "Индекс", "ОД", "МЕ/мл"],
            "Бошқа": ["мг/л", "мкг/л", "нг/л", "%"]
        }
        
        for category, unit_list in units.items():
            with st.expander(f"📏 {category}"):
                cols = st.columns(3)
                for i, unit in enumerate(unit_list):
                    col_idx = i % 3
                    with cols[col_idx]:
                        st.info(f"**{unit}**")
        
        # Янги ўлчов бирлиги қўшиш
        with st.expander("➕ Янги ўлчов бирлиги қўшиш"):
            new_category = st.text_input("Категория")
            new_unit = st.text_input("Ўлчов бирлиги")
            new_symbol = st.text_input("Символ/қисқартма")
            
            if st.button("Ўлчов бирлиги қўшиш"):
                st.success(f"✅ {new_unit} қўшилди! (Базага сақлаш функцияси ишга туширилмоқда)")
    
    with tab4:
        st.markdown("### 📊 Тахлил категориялари")
        
        categories = [
            ("Пренатал", "Homiladorлик давридаги тахлиллар"),
            ("Неонатал", "Янги тугʻилган чақалоқлар скрининги"),
            ("ИФА", "Иммунофермент тахлиллари"),
            ("Биохимик", "Қон биохимик тахлиллари"),
            ("Клиник", "Клиник қон тахлиллари"),
            ("Гормонлар", "Гормон тахлиллари"),
            ("Микробиология", "Микробиологик тадқиқотлар"),
            ("Генетик", "Генетик тадқиқотлар"),
            ("Урина", "Сийдик тахлиллари"),
            ("Бошқа", "Бошқа турдаги тахлиллар")
        ]
        
        for category, description in categories:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"**{category}**")
            with col2:
                st.markdown(f"*{description}*")
            st.divider()

# =================== БЛАНКА ШАБЛОНЛАРИ ===================
def manage_templates():
    """Бланка шаблонлари бошқаруви"""
    st.markdown('<h1 class="section-title">📋 Бланка шаблонлари</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎨 Шаблонлар", "➕ Янги шаблон", "👁️ Шаблонни кўриш"])
    
    with tab1:
        st.markdown("### 🎨 Мавжуд шаблонлар")
        
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT * FROM form_templates ORDER BY template_name")
            templates = cursor.fetchall()
        except:
            templates = []
        
        if templates:
            for template in templates:
                template_id, template_name, template_type, category, design_config, is_active, created_by, created_at = template
                
                # Дизайн конфигурациясини олиш
                try:
                    config = json.loads(design_config)
                    primary_color = config.get('primary_color', '#3498DB')
                except:
                    primary_color = '#3498DB'
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"""
                    <div style="
                        background: {primary_color}15;
                        border: 2px solid {primary_color};
                        color: #2C3E50;
                        padding: 1.5rem;
                        border-radius: 12px;
                        margin: 0.5rem 0;
                        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    ">
                        <h3 style="color: {primary_color}">{template_name}</h3>
                        <p><strong>Тури:</strong> {template_type}</p>
                        <p><strong>Категория:</strong> {category}</p>
                        <p><strong>Холат:</strong> {'🟢 Фаол' if is_active == 1 else '🔴 Фаол эмас'}</p>
                        <p><strong>Яратилган:</strong> {created_at}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("👁️", key=f"view_{template_id}"):
                            st.session_state.view_template_id = template_id
                            st.session_state.view_template_name = template_name
                            st.rerun()
                    with col_btn2:
                        if st.button("🗑️", key=f"delete_{template_id}"):
                            cursor.execute("DELETE FROM form_templates WHERE id = ?", (template_id,))
                            db.conn.commit()
                            st.success(f"✅ '{template_name}' шаблони ўчирилди!")
                            st.rerun()
        
        else:
            st.info("📭 Шаблонлар мавжуд эмас")
    
    with tab2:
        st.markdown("### ➕ Янги шаблон яратиш")
        
        with st.form("new_template_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                template_name = st.text_input("Шаблон номи*")
                template_type = st.selectbox("Шаблон тури*", 
                                          ["Қон тахлили", "Гормонлар", "Пренатал", 
                                           "Биохимик", "ИФА", "Урина", "Бошқа"])
                category = st.selectbox("Категория*", ["Умумий", "Махсус", "Шахсий"])
            
            with col2:
                # Дизайн параметрлари
                primary_color = st.color_picker("Асосий ранг", "#3498DB")
                secondary_color = st.color_picker("Иккинчи ранг", "#2E86C1")
                font_family = st.selectbox("Шрифт", ["Arial", "Times New Roman", "Helvetica", "Calibri"])
                font_size = st.slider("Шрифт ўлчами", 10, 18, 12)
            
            # Шаблон контент қисми
            st.markdown("### 📝 Шаблон контенти")
            
            sections = st.multiselect(
                "Бўлимларни танланг",
                ["Бемор маълумотлари", "Тахлил натижалари", "Норма қийматлари", 
                 "Шифокор тавсиялари", "Изохлар", "Қўшимча маълумотлар"],
                default=["Бемор маълумотлари", "Тахлил натижалари"]
            )
            
            # Мослашувчан нарх
            include_logo = st.checkbox("Логотип қўшиш", value=True)
            include_qr = st.checkbox("QR код қўшиш", value=True)
            include_signature = st.checkbox("Имзо учун жой", value=True)
            
            submitted = st.form_submit_button("💾 Шаблонни сақлаш", use_container_width=True)
            
            if submitted:
                if template_name and template_type and category:
                    # Шаблон маълумотларини базага сақлаш
                    design_config = json.dumps({
                        "primary_color": primary_color,
                        "secondary_color": secondary_color,
                        "font_family": font_family,
                        "font_size": font_size,
                        "sections": sections,
                        "features": {
                            "include_logo": include_logo,
                            "include_qr": include_qr,
                            "include_signature": include_signature
                        }
                    })
                    
                    cursor = db.get_cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO form_templates 
                            (template_name, template_type, category, design_config)
                            VALUES (?, ?, ?, ?)
                        ''', (template_name, template_type, category, design_config))
                        
                        db.conn.commit()
                        st.success(f"✅ '{template_name}' шаблони муваффақиятли яратилди!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Хатолик: {str(e)}")
                else:
                    st.error("⚠️ * белгиланган майдонларни тўлдиринг")
    
    with tab3:
        st.markdown("### 👁️ Шаблон намунаси")
        
        if 'view_template_id' in st.session_state:
            cursor = db.get_cursor()
            cursor.execute("SELECT * FROM form_templates WHERE id = ?", (st.session_state.view_template_id,))
            template = cursor.fetchone()
            
            if template:
                template_id, template_name, template_type, category, design_config, is_active, created_by, created_at = template
                
                try:
                    config = json.loads(design_config)
                    primary_color = config.get('primary_color', '#3498DB')
                    secondary_color = config.get('secondary_color', '#2E86C1')
                    font_family = config.get('font_family', 'Arial')
                    font_size = config.get('font_size', 12)
                    sections = config.get('sections', [])
                    features = config.get('features', {})
                except:
                    primary_color = '#3498DB'
                    secondary_color = '#2E86C1'
                    font_family = 'Arial'
                    font_size = 12
                    sections = []
                    features = {}
                
                # Шаблон намунасини кўрсатиш
                st.markdown(f"""
                <div style="
                    border: 2px solid {primary_color};
                    border-radius: 10px;
                    padding: 2rem;
                    font-family: {font_family};
                    font-size: {font_size}px;
                    background: white;
                    margin: 1rem 0;
                    min-height: 600px;
                ">
                    <h2 style="color: {primary_color}; text-align: center;">{template_name}</h2>
                    <p style="text-align: center; color: #7F8C8D;">{template_type} • {category}</p>
                    <hr style="border-color: {secondary_color}; margin: 1rem 0;">
                    
                    {'<h4 style="color: ' + secondary_color + ';">Бемор маълумотлари</h4>' if "Бемор маълумотлари" in sections else ''}
                    {'<p><strong>Исми-шарифи:</strong> Намуна бемор</p>' if "Бемор маълумотлари" in sections else ''}
                    {'<p><strong>Туғилган сана:</strong> 01.01.1990</p>' if "Бемор маълумотлари" in sections else ''}
                    {'<p><strong>Бемор ID:</strong> P-20240115-0001</p>' if "Бемор маълумотлари" in sections else ''}
                    
                    {'<h4 style="color: ' + secondary_color + '; margin-top: 1.5rem;">Тахлил натижалари</h4>' if "Тахлил натижалари" in sections else ''}
                    {'<table style="width: 100%; border-collapse: collapse; margin-top: 0.5rem;">' if "Тахлил натижалари" in sections else ''}
                    {'<tr style="background-color: ' + primary_color + '; color: white;">' if "Тахлил натижалари" in sections else ''}
                    {'<th style="padding: 8px; text-align: left;">Параметр</th>' if "Тахлил натижалари" in sections else ''}
                    {'<th style="padding: 8px; text-align: left;">Қиймат</th>' if "Тахлил натижалари" in sections else ''}
                    {'<th style="padding: 8px; text-align: left;">Норма</th>' if "Тахлил натижалари" in sections else ''}
                    {'<th style="padding: 8px; text-align: left;">Холат</th>' if "Тахлил натижалари" in sections else ''}
                    {'</tr>' if "Тахлил натижалари" in sections else ''}
                    {'<tr style="border-bottom: 1px solid #ddd;">' if "Тахлил натижалари" in sections else ''}
                    {'<td style="padding: 8px;">Глюкоза</td>' if "Тахлил натижалари" in sections else ''}
                    {'<td style="padding: 8px;">5.8 ммоль/л</td>' if "Тахлил натижалари" in sections else ''}
                    {'<td style="padding: 8px;">3.9-6.1</td>' if "Тахлил натижалари" in sections else ''}
                    {'<td style="padding: 8px; color: green;">✅ Норма</td>' if "Тахлил натижалари" in sections else ''}
                    {'</tr>' if "Тахлил натижалари" in sections else ''}
                    {'</table>' if "Тахлил натижалари" in sections else ''}
                    
                    {'<h4 style="color: ' + secondary_color + '; margin-top: 1.5rem;">Шифокор тавсиялари</h4>' if "Шифокор тавсиялари" in sections else ''}
                    {'<p>Натижалар норма доирасида. Қўшимча тадқиқот талаб этилмайди.</p>' if "Шифокор тавсиялари" in sections else ''}
                    
                    <div style="margin-top: 2rem; color: #7F8C8D;">
                        {'<p>**Изох:** Натижалар норма доирасида</p>' if "Изохлар" in sections else ''}
                        <p>**Таҳлил санаси:** {date.today().strftime('%d.%m.%Y')}</p>
                        {'<div style="margin-top: 3rem; text-align: right;">___________<br><em>Имзо</em></div>' if features.get('include_signature', False) else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("⬅️ Ортга қайтиш"):
                    if 'view_template_id' in st.session_state:
                        del st.session_state.view_template_id
                    if 'view_template_name' in st.session_state:
                        del st.session_state.view_template_name
                    st.rerun()
            else:
                st.error("Шаблон топилмади")
        else:
            st.info("👈 Шаблонни кўриш учун шу табдаги шаблонлар рўйхатидан '👁️' тугмасини босинг")

# =================== ҲИСОБОТЛАР ===================
def show_reports():
    """Ҳисоботлар ва статистика"""
    st.markdown('<h1 class="section-title">📈 Ҳисоботлар ва статистика</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📊 Умумий статистика", "📅 Кунлик ҳисобот", "📑 Тахлил ҳисоботи"])
    
    with tab1:
        st.markdown("### 📊 Умумий статистика")
        
        cursor = db.get_cursor()
        
        try:
            # Ўзгармалар статистикаси
            col1, col2 = st.columns(2)
            
            with col1:
                cursor.execute("""
                    SELECT test_type, COUNT(*) as count
                    FROM test_results
                    GROUP BY test_type
                    ORDER BY count DESC
                """)
                test_stats = cursor.fetchall()
                
                if test_stats:
                    df_test_stats = pd.DataFrame(test_stats, columns=['Тахлил тури', 'Сони'])
                    fig = px.pie(df_test_stats, values='Сони', names='Тахлил тури',
                                title='Тахлиллар тарқалиши',
                                hole=0.3)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                cursor.execute("""
                    SELECT gender, COUNT(*) as count
                    FROM patients
                    GROUP BY gender
                """)
                gender_stats = cursor.fetchall()
                
                if gender_stats:
                    df_gender_stats = pd.DataFrame(gender_stats, columns=['Жинси', 'Сони'])
                    fig = px.bar(df_gender_stats, x='Жинси', y='Сони',
                                title='Беморлар жинс тарқалиши',
                                color='Жинси')
                    st.plotly_chart(fig, use_container_width=True)
            
            # Ёш тарқалиши
            st.markdown("### 👶 Беморлар ёш тарқалиши")
            
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN (julianday('now') - julianday(birth_date)) / 365.25 < 18 THEN '0-17'
                        WHEN (julianday('now') - julianday(birth_date)) / 365.25 BETWEEN 18 AND 30 THEN '18-30'
                        WHEN (julianday('now') - julianday(birth_date)) / 365.25 BETWEEN 31 AND 45 THEN '31-45'
                        WHEN (julianday('now') - julianday(birth_date)) / 365.25 BETWEEN 46 AND 60 THEN '46-60'
                        ELSE '60+'
                    END as age_group,
                    COUNT(*) as count
                FROM patients
                GROUP BY age_group
                ORDER BY 
                    CASE age_group
                        WHEN '0-17' THEN 1
                        WHEN '18-30' THEN 2
                        WHEN '31-45' THEN 3
                        WHEN '46-60' THEN 4
                        ELSE 5
                    END
            """)
            
            age_stats = cursor.fetchall()
            
            if age_stats:
                df_age_stats = pd.DataFrame(age_stats, columns=['Ёш гуруҳи', 'Сони'])
                fig = px.bar(df_age_stats, x='Ёш гуруҳи', y='Сони',
                            title='Беморлар ёш гуруҳлари',
                            color='Ёш гуруҳи')
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Статистикани олишда хатолик: {str(e)}")
    
    with tab2:
        st.markdown("### 📅 Кунлик ҳисобот")
        
        report_date = st.date_input("Ҳисобот санаси", value=date.today())
        
        if st.button("Ҳисобот яратиш", use_container_width=True):
            cursor = db.get_cursor()
            
            try:
                # Кунлик статистика
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT patient_id) as patients_count,
                        COUNT(*) as tests_count,
                        SUM(CASE WHEN status != 'normal' THEN 1 ELSE 0 END) as abnormal_count
                    FROM test_results
                    WHERE DATE(test_date) = DATE(?)
                """, (report_date,))
                
                daily_stats = cursor.fetchone()
                
                if daily_stats:
                    patients_count, tests_count, abnormal_count = daily_stats
                    
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    
                    with col_stat1:
                        st.metric("Беморлар сони", patients_count)
                    with col_stat2:
                        st.metric("Тахлиллар сони", tests_count)
                    with col_stat3:
                        st.metric("Патология тахлиллар", abnormal_count)
                    
                    # Тафсилотли рўйхат
                    cursor.execute("""
                        SELECT p.full_name, tr.test_type, tr.parameter_code, 
                               tr.result_value, tr.unit, tr.status
                        FROM test_results tr
                        JOIN patients p ON tr.patient_id = p.id
                        WHERE DATE(tr.test_date) = DATE(?)
                        ORDER BY p.full_name
                    """, (report_date,))
                    
                    daily_tests = cursor.fetchall()
                    
                    if daily_tests:
                        df_daily = pd.DataFrame(daily_tests, columns=[
                            'Бемор', 'Тахлил тури', 'Параметр', 
                            'Қиймат', 'Ўлчов бирлиги', 'Холат'
                        ])
                        
                        st.dataframe(df_daily, use_container_width=True, height=400)
                        
                        # Экспорт
                        csv = df_daily.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Кунлик ҳисоботни юклаб олиш (CSV)",
                            data=csv,
                            file_name=f"kunlik_hisobot_{report_date}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info(f"📭 {report_date} санада тахлил натижалари мавжуд эмас")
                else:
                    st.info(f"📭 {report_date} санада тахлил натижалари мавжуд эмас")
            except Exception as e:
                st.error(f"Ҳисобот яратишда хатолик: {str(e)}")
    
    with tab3:
        st.markdown("### 📑 Тахлил ҳисоботи")
        
        # Бемор ва давр танлаш
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT id, full_name FROM patients ORDER BY full_name")
            patients = cursor.fetchall()
        except:
            patients = []
        
        if patients:
            patient_options = {p[1]: p[0] for p in patients}
            selected_patient = st.selectbox("Беморни танланг", list(patient_options.keys()))
            patient_id = patient_options[selected_patient]
            
            col_date1, col_date2 = st.columns(2)
            with col_date1:
                start_date = st.date_input("Бошланиш санаси", 
                                         value=date.today() - timedelta(days=30))
            with col_date2:
                end_date = st.date_input("Тугаш санаси", value=date.today())
            
            if st.button("Ҳисобот яратиш", use_container_width=True):
                # Бемор маълумотлари
                cursor.execute("""
                    SELECT patient_id, birth_date, gender, phone
                    FROM patients WHERE id = ?
                """, (patient_id,))
                
                patient_info = cursor.fetchone()
                
                if patient_info:
                    # Тахлил натижалари
                    cursor.execute("""
                        SELECT test_type, parameter_code, result_value, 
                               unit, status, test_date
                        FROM test_results
                        WHERE patient_id = ? 
                        AND test_date BETWEEN ? AND ?
                        ORDER BY test_date DESC
                    """, (patient_id, start_date, end_date))
                    
                    patient_tests = cursor.fetchall()
                    
                    if patient_tests:
                        # Ҳисоботни кўрсатиш
                        st.markdown(f"""
                        <div style="
                            background: #F8F9FA;
                            padding: 2rem;
                            border-radius: 10px;
                            margin: 1rem 0;
                        ">
                            <h3>👤 Бемор: {selected_patient}</h3>
                            <p><strong>Бемор ID:</strong> {patient_info[0]}</p>
                            <p><strong>Туғилган сана:</strong> {patient_info[1]}</p>
                            <p><strong>Жинси:</strong> {patient_info[2]}</p>
                            <p><strong>Телефон:</strong> {patient_info[3]}</p>
                            <p><strong>Давр:</strong> {start_date} - {end_date}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Натижалар таблицаси
                        df_patient = pd.DataFrame(patient_tests, columns=[
                            'Тахлил тури', 'Параметр', 'Қиймат', 
                            'Ўлчов бирлиги', 'Холат', 'Сана'
                        ])
                        
                        # Параметрлар бўйича график
                        if len(patient_tests) > 1:
                            unique_params = df_patient['Параметр'].unique()
                            if len(unique_params) > 0:
                                param_to_plot = st.selectbox(
                                    "График учун параметрни танланг",
                                    unique_params
                                )
                                
                                param_data = df_patient[df_patient['Параметр'] == param_to_plot]
                                
                                if len(param_data) > 1:
                                    try:
                                        fig = px.line(param_data, x='Сана', y='Қиймат',
                                                    title=f'{param_to_plot} параметрининг ўзгариши',
                                                    markers=True)
                                        st.plotly_chart(fig, use_container_width=True)
                                    except:
                                        st.info("График яратиб бўлмади")
                        
                        # Натижалар таблицаси
                        st.dataframe(df_patient, use_container_width=True, height=400)
                        
                        # Тавсиялар
                        abnormal_tests = df_patient[df_patient['Холат'] != 'normal']
                        if not abnormal_tests.empty:
                            st.markdown("### ⚠️ Тавсиялар")
                            st.warning("""
                            Ушбу беморда нормадан оғишлар аникланди. 
                            Тўлиқ тиббий кўриб чиқиш ва қўшимча тадқиқотлар ўтказиш тавсия этилади.
                            """)
                        
                        # Юклаб олиш
                        csv = df_patient.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Ҳисоботни юклаб олиш (CSV)",
                            data=csv,
                            file_name=f"bemor_hisobot_{patient_info[0]}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    else:
                        st.info(f"📭 Танланган даврда тахлил натижалари мавжуд эмас")
                else:
                    st.error("Бемор маълумотларини олиб бўлмади")
        else:
            st.info("📭 Беморлар мавжуд эмас")

# =================== ШИФОКОРЛАР БОШҚАРУВИ ===================
def manage_doctors():
    """Шифокорлар бошқаруви"""
    st.markdown('<h1 class="section-title">👨‍⚕️ Шифокорлар бошқаруви</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["➕ Янги шифокор", "📋 Шифокорлар", "🔍 Излаш"])
    
    with tab1:
        st.markdown("### 🆕 Янги шифокор қўшиш")
        
        with st.form("new_doctor_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                full_name = st.text_input("👤 Исми-шарифи*")
                specialization = st.text_input("🎓 Мутахассислиги*")
                license_number = st.text_input("📜 Лицензия рақами")
            
            with col2:
                phone = st.text_input("📞 Телефон рақами*")
                email = st.text_input("📧 Электрон почта")
                department = st.selectbox("🏥 Бўлим", 
                                       ["Терапия", "Хирургия", "Педиатрия", "Гинекология", 
                                        "Неврология", "Кардиология", "Бошқа"])
            
            address = st.text_area("🏠 Иш манзили")
            
            submitted = st.form_submit_button("💾 Шифокорни қўшиш", use_container_width=True)
            
            if submitted:
                if full_name and specialization and phone:
                    cursor = db.get_cursor()
                    try:
                        cursor.execute('''
                            INSERT INTO doctors 
                            (full_name, specialization, license_number, phone, email, department, address)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (full_name, specialization, license_number, phone, email, department, address))
                        db.conn.commit()
                        st.success(f"✅ Доктор {full_name} муваффақиятли қўшилди!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Хатолик: {str(e)}")
                else:
                    st.error("⚠️ * белгиланган майдонларни тўлдиринг")
    
    with tab2:
        st.markdown("### 📋 Шифокорлар рўйхати")
        
        cursor = db.get_cursor()
        try:
            cursor.execute("SELECT * FROM doctors ORDER BY full_name")
            doctors = cursor.fetchall()
        except:
            doctors = []
        
        if doctors:
            df = pd.DataFrame(doctors, columns=[
                'ID', 'Исми-шарифи', 'Мутахассислиги', 'Лицензия рақами',
                'Телефон', 'Электрон почта', 'Бўлим', 'Манзил', 'Яратилган'
            ])
            
            # Филтрлар
            col_search, col_filter = st.columns(2)
            with col_search:
                search_term = st.text_input("🔍 Излаш (исм боʻйича)", key="doctor_search")
            
            with col_filter:
                filter_dept = st.selectbox("Бўлим боʻйича", ["Ҳаммаси"] + sorted(df['Бўлим'].dropna().unique().tolist()), key="dept_filter")
            
            if search_term:
                df = df[df['Исми-шарифи'].str.contains(search_term, case=False, na=False)]
            
            if filter_dept != "Ҳаммаси":
                df = df[df['Бўлим'] == filter_dept]
            
            st.dataframe(df, use_container_width=True, height=500)
            
            # Таҳрирлаш ва ўчириш
            with st.expander("Шифокорни таҳрирлаш ёки ўчириш"):
                selected_id = st.selectbox("Шифокорни танланг", df['ID'].tolist())
                
                if selected_id:
                    # Шифокор маълумотларини олиш
                    cursor.execute("SELECT * FROM doctors WHERE id = ?", (selected_id,))
                    doctor_data = cursor.fetchone()
                    
                    if doctor_data:
                        col_edit1, col_edit2 = st.columns(2)
                        with col_edit1:
                            edit_name = st.text_input("Исми-шарифи", value=doctor_data[1], key=f"edit_name_{selected_id}")
                            edit_specialization = st.text_input("Мутахассислиги", value=doctor_data[2], key=f"edit_spec_{selected_id}")
                            edit_license = st.text_input("Лицензия рақами", value=doctor_data[3] or "", key=f"edit_license_{selected_id}")
                        with col_edit2:
                            edit_phone = st.text_input("Телефон", value=doctor_data[4], key=f"edit_phone_{selected_id}")
                            edit_email = st.text_input("Электрон почта", value=doctor_data[5] or "", key=f"edit_email_{selected_id}")
                            edit_department = st.selectbox("Бўлим", 
                                                         ["Терапия", "Хирургия", "Педиатрия", "Гинекология", 
                                                          "Неврология", "Кардиология", "Бошқа"],
                                                         index=["Терапия", "Хирургия", "Педиатрия", "Гинекология", 
                                                                "Неврология", "Кардиология", "Бошқа"].index(doctor_data[6] if doctor_data[6] in ["Терапия", "Хирургия", "Педиатрия", "Гинекология", "Неврология", "Кардиология", "Бошқа"] else 6),
                                                         key=f"edit_dept_{selected_id}")
                        
                        edit_address = st.text_area("Манзил", value=doctor_data[7] or "", key=f"edit_addr_{selected_id}")
                        
                        col_save, col_delete = st.columns(2)
                        with col_save:
                            if st.button("💾 Ўзгартиришларни сақлаш", use_container_width=True, key=f"save_{selected_id}"):
                                cursor.execute('''
                                    UPDATE doctors 
                                    SET full_name = ?, specialization = ?, license_number = ?, phone = ?, 
                                        email = ?, department = ?, address = ?
                                    WHERE id = ?
                                ''', (edit_name, edit_specialization, edit_license, edit_phone, 
                                     edit_email, edit_department, edit_address, selected_id))
                                db.conn.commit()
                                st.success("✅ Шифокор маълумотлари янгиланди!")
                                st.rerun()
                        
                        with col_delete:
                            if st.button("🗑️ Шифокорни ўчириш", use_container_width=True, key=f"delete_{selected_id}"):
                                cursor.execute("DELETE FROM doctors WHERE id = ?", (selected_id,))
                                db.conn.commit()
                                st.success("✅ Шифокор ўчирилди!")
                                st.rerun()
        else:
            st.info("📭 Ҳали шифокорлар мавжуд эмас")
    
    with tab3:
        st.markdown("### 🔍 Шифокор излаш")
        
        search_by = st.radio("Излаш усули", ["Исм боʻйича", "Мутахассислик боʻйича", "Бўлим боʻйича"], horizontal=True)
        search_value = st.text_input("Қидирув қиймати")
        
        if st.button("🔍 Излаш", use_container_width=True):
            if search_value:
                cursor = db.get_cursor()
                
                try:
                    if search_by == "Исм боʻйича":
                        cursor.execute("SELECT * FROM doctors WHERE full_name LIKE ?", 
                                     (f"%{search_value}%",))
                    elif search_by == "Мутахассислик боʻйича":
                        cursor.execute("SELECT * FROM doctors WHERE specialization LIKE ?", 
                                     (f"%{search_value}%",))
                    else:
                        cursor.execute("SELECT * FROM doctors WHERE department LIKE ?", 
                                     (f"%{search_value}%",))
                    
                    results = cursor.fetchall()
                    
                    if results:
                        st.success(f"✅ {len(results)} та натижа топилди")
                        
                        for doctor in results:
                            with st.expander(f"👨‍⚕️ {doctor[1]} - {doctor[2]}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Мутахассислиги:** {doctor[2]}")
                                    st.write(f"**Бўлим:** {doctor[6]}")
                                    st.write(f"**Лицензия:** {doctor[3] if doctor[3] else 'Номаълум'}")
                                with col2:
                                    st.write(f"**Телефон:** {doctor[4]}")
                                    st.write(f"**Электрон почта:** {doctor[5] if doctor[5] else 'Номаълум'}")
                                    st.write(f"**Манзил:** {doctor[7] if doctor[7] else 'Номаълум'}")
                    else:
                        st.warning("🔍 Шифокор топилмади")
                except Exception as e:
                    st.error(f"Хатолик: {str(e)}")
            else:
                st.warning("Қидирув қийматини киритинг")

# =================== СИСТЕМА СОЗЛАМАЛАРИ ===================
def system_settings():
    """Система созламалари"""
    st.markdown('<h1 class="section-title">🔧 Система созламалари</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚙️ Умумий", 
        "🔐 Хавфсизлик", 
        "📧 Электрон почта", 
        "🔄 Резерв нусха"
    ])
    
    with tab1:
        st.markdown("### ⚙️ Умумий созламалар")
        
        if 'system_settings' not in st.session_state:
            st.session_state.system_settings = {
                'hospital_name': 'Марказий шифохона',
                'hospital_address': 'Тошкент ш., Юнусобод тумани',
                'hospital_phone': '+99871 123-45-67',
                'hospital_email': 'info@hospital.uz',
                'default_language': 'Ўзбек',
                'date_format': 'DD.MM.YYYY',
                'timezone': 'Tashkent (UTC+5)',
                'items_per_page': 25,
                'auto_logout': 30,
                'enable_notifications': True
            }
        
        hospital_name = st.text_input("Шифохона номи", 
                                    value=st.session_state.system_settings['hospital_name'])
        hospital_address = st.text_area("Манзили", 
                                      value=st.session_state.system_settings['hospital_address'])
        hospital_phone = st.text_input("Телефон", 
                                     value=st.session_state.system_settings['hospital_phone'])
        hospital_email = st.text_input("Электрон почта", 
                                     value=st.session_state.system_settings['hospital_email'])
        
        # Тизим параметрлари
        col1, col2 = st.columns(2)
        
        with col1:
            default_language = st.selectbox("Стандарт тил", ["Ўзбек", "Рус", "Инглиз"],
                                          index=["Ўзбек", "Рус", "Инглиз"].index(
                                              st.session_state.system_settings['default_language']))
            date_format = st.selectbox("Сана формати", ["DD.MM.YYYY", "YYYY-MM-DD", "MM/DD/YYYY"],
                                     index=["DD.MM.YYYY", "YYYY-MM-DD", "MM/DD/YYYY"].index(
                                         st.session_state.system_settings['date_format']))
            timezone = st.selectbox("Вақт минтақаси", ["Tashkent (UTC+5)", "Moscow (UTC+3)", "London (UTC+0)"],
                                  index=0)
        
        with col2:
            items_per_page = st.slider("Саҳифадаги элементлар сони", 10, 100, 
                                     st.session_state.system_settings['items_per_page'])
            auto_logout = st.number_input("Автомат чиқиш (минут)", min_value=5, max_value=120, 
                                        value=st.session_state.system_settings['auto_logout'])
            enable_notifications = st.checkbox("Огоҳлантиришларни фаоллаштириш", 
                                             value=st.session_state.system_settings['enable_notifications'])
        
        if st.button("💾 Умумий созламаларни сақлаш", use_container_width=True):
            st.session_state.system_settings.update({
                'hospital_name': hospital_name,
                'hospital_address': hospital_address,
                'hospital_phone': hospital_phone,
                'hospital_email': hospital_email,
                'default_language': default_language,
                'date_format': date_format,
                'timezone': timezone,
                'items_per_page': items_per_page,
                'auto_logout': auto_logout,
                'enable_notifications': enable_notifications
            })
            st.success("✅ Умумий созламалар сақланди!")
    
    with tab2:
        st.markdown("### 🔐 Хавфсизлик созламалари")
        
        if 'security_settings' not in st.session_state:
            st.session_state.security_settings = {
                'min_password_length': 8,
                'require_numbers': True,
                'require_special': True,
                'require_uppercase': True,
                'session_timeout': 8,
                'max_login_attempts': 5,
                'lockout_duration': 15,
                'default_role': 'Шифокор'
            }
        
        # Парол сиёсати
        st.markdown("#### 🔑 Парол сиёсати")
        
        min_password_length = st.slider("Минимал парол узунлиги", 6, 20, 
                                      st.session_state.security_settings['min_password_length'])
        require_numbers = st.checkbox("Рақамлар талаб қилиш", 
                                    value=st.session_state.security_settings['require_numbers'])
        require_special = st.checkbox("Махсус белгилар талаб қилиш", 
                                    value=st.session_state.security_settings['require_special'])
        require_uppercase = st.checkbox("Катта ҳарфлар талаб қилиш", 
                                      value=st.session_state.security_settings['require_uppercase'])
        
        # Сессия бошқаруви
        st.markdown("#### ⏱️ Сессия бошқаруви")
        
        session_timeout = st.number_input("Сессия вақти (соат)", min_value=1, max_value=24, 
                                        value=st.session_state.security_settings['session_timeout'])
        max_login_attempts = st.number_input("Максимал кириш урунишлари", min_value=3, max_value=10, 
                                           value=st.session_state.security_settings['max_login_attempts'])
        lockout_duration = st.number_input("Блоклов муддати (минут)", min_value=5, max_value=60, 
                                         value=st.session_state.security_settings['lockout_duration'])
        
        # Рўхсатлар
        st.markdown("#### 👥 Рўхсатлар")
        
        roles = ["Администратор", "Шифокор", "Лаборант", "Ҳисобчи", "Кўриб чиқувчи"]
        default_role = st.selectbox("Янги фойдаланувчи учун стандарт рол", roles,
                                  index=roles.index(st.session_state.security_settings['default_role']))
        
        if st.button("💾 Хавфсизлик созламаларини сақлаш", use_container_width=True):
            st.session_state.security_settings.update({
                'min_password_length': min_password_length,
                'require_numbers': require_numbers,
                'require_special': require_special,
                'require_uppercase': require_uppercase,
                'session_timeout': session_timeout,
                'max_login_attempts': max_login_attempts,
                'lockout_duration': lockout_duration,
                'default_role': default_role
            })
            st.success("✅ Хавфсизлик созламалари сақланди!")
    
    with tab3:
        st.markdown("### 📧 Электрон почта созламалари")
        
        if 'email_settings' not in st.session_state:
            st.session_state.email_settings = {
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'email_username': '',
                'email_from': 'Шифохона тахлил маркази',
                'email_ssl': True,
                'email_subject': 'Тахлил натижалари',
                'email_template': """Хурматли {bemor_ismi}!

Сизнинг {test_sanasi} санадаги тахлил натижаларингиз тайёр.

Бемор: {bemor_ismi}
Тахлил тури: {test_turi}
Натижалар санаси: {test_sanasi}

Натижаларни файл иловасида кўришингиз мумкин.

Ҳурмат билан,
{shifoxona_nomi}"""
            }
        
        # SMTP сервер созламалари
        smtp_server = st.text_input("SMTP сервери", 
                                  value=st.session_state.email_settings['smtp_server'])
        smtp_port = st.number_input("SMTP порти", min_value=1, max_value=65535, 
                                  value=st.session_state.email_settings['smtp_port'])
        
        col_email1, col_email2 = st.columns(2)
        
        with col_email1:
            email_username = st.text_input("Электрон почта логини", 
                                         value=st.session_state.email_settings['email_username'])
            email_password = st.text_input("Электрон почта пароли", type="password")
        
        with col_email2:
            email_from = st.text_input("Жўнатувчи номи", 
                                     value=st.session_state.email_settings['email_from'])
            email_ssl = st.checkbox("SSL фойдаланиш", 
                                  value=st.session_state.email_settings['email_ssl'])
        
        # Натижалар жўнатиш шаблони
        st.markdown("#### 📝 Жўнатиш шаблони")
        
        email_subject = st.text_input("Мавзу", 
                                    value=st.session_state.email_settings['email_subject'])
        email_template = st.text_area("Хат шаблони", 
                                    value=st.session_state.email_settings['email_template'], 
                                    height=200)
        
        if st.button("💾 Электрон почта созламаларини сақлаш", use_container_width=True):
            st.session_state.email_settings.update({
                'smtp_server': smtp_server,
                'smtp_port': smtp_port,
                'email_username': email_username,
                'email_from': email_from,
                'email_ssl': email_ssl,
                'email_subject': email_subject,
                'email_template': email_template
            })
            st.success("✅ Электрон почта созламалари сақланди!")
    
    with tab4:
        st.markdown("### 🔄 Резерв нусха олиш")
        
        if 'backup_settings' not in st.session_state:
            st.session_state.backup_settings = {
                'backup_frequency': 'Ҳар куни',
                'backup_time': datetime.now().time(),
                'keep_backups': 30,
                'backup_location': 'Маҳаллий сервер',
                'auto_backup': True,
                'compress_backup': True
            }
        
        col_backup1, col_backup2 = st.columns(2)
        
        with col_backup1:
            backup_frequency = st.selectbox(
                "Резерв нусха олиш жихози", 
                ["Ҳар куни", "Ҳар хафта", "Ҳар ой", "Қўлда"],
                index=["Ҳар куни", "Ҳар хафта", "Ҳар ой", "Қўлда"].index(
                    st.session_state.backup_settings['backup_frequency'])
            )
            
            backup_time = st.time_input("Резерв нусха вақти", 
                                      value=st.session_state.backup_settings['backup_time'])
            
            keep_backups = st.number_input("Сақланадиган нусхалар сони", min_value=1, max_value=100, 
                                         value=st.session_state.backup_settings['keep_backups'])
        
        with col_backup2:
            backup_location = st.selectbox(
                "Сақлаш жойи",
                ["Маҳаллий сервер", "Cloud Storage", "Диск", "Бошқа"],
                index=["Маҳаллий сервер", "Cloud Storage", "Диск", "Бошқа"].index(
                    st.session_state.backup_settings['backup_location'])
            )
            
            auto_backup = st.checkbox("Автомат резерв нусха олиш", 
                                    value=st.session_state.backup_settings['auto_backup'])
            compress_backup = st.checkbox("Архивлаш", 
                                        value=st.session_state.backup_settings['compress_backup'])
        
        st.markdown("---")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔄 Ҳозирги вақтда резерв нусха олиш", use_container_width=True):
                st.success("✅ Резерв нусха муваффақиятли олинди!")
        
        with col_btn2:
            if st.button("📥 Охирги резерв нусхани юклаб олиш", use_container_width=True):
                st.info("Резерв нусха юклаб олинмоқда...")
        
        if st.button("💾 Резерв нусха созламаларини сақлаш", use_container_width=True):
            st.session_state.backup_settings.update({
                'backup_frequency': backup_frequency,
                'backup_time': backup_time,
                'keep_backups': keep_backups,
                'backup_location': backup_location,
                'auto_backup': auto_backup,
                'compress_backup': compress_backup
            })
            st.success("✅ Резерв нусха созламалари сақланди!")

# =================== АСОСИЙ ИШЛАШ ТАРТИБИ ===================
def main():
    # Сессия ўзгартувчиларини инициализациялаш
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    try:
        # Авторизация текшируви
        if not st.session_state.logged_in:
            login_page()
        else:
            main_page()
    except Exception as e:
        st.error(f"Хатолик юз берди: {str(e)}")
        st.info("Илтимос, саҳифани яна юкланг ёки администраторга мурожаат қилинг.")
        
        # Қайтадан урганиш тугмаси
        if st.button("🔄 Қайтадан урганиш"):
            st.rerun()

# =================== ИШГА ТУШИРИШ ===================
if __name__ == "__main__":
    main()
