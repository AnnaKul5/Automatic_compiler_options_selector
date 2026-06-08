import streamlit as st
import pandas as pd
import sqlite3
import tempfile
from db.database import insert_flag, get_flags, delete_all_flags, delete_flag

st.set_page_config(
    page_title="Флаги компиляции - Оптимизация компиляции",
    layout="wide"
)

# Инициализация ключей для сброса виджетов
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'flag_input_key' not in st.session_state:
    st.session_state.flag_input_key = 0

st.markdown(
"""
### Введите флаги вручную **или** загрузите файл

Поддерживаемые форматы:
- **CSV** — один столбец с флагами  
- **Excel (.xlsx)** — первый столбец  
- **SQLite (.db)** — таблица `compiler_flags(name)`
""")

# Ручной ввод 

with st.form("add_flag_form"):
    flag = st.text_input("Введите флаг компилятора (например: -O3)", 
                        key=f"flag_input_{st.session_state.flag_input_key}")
    
    submitted = st.form_submit_button("Добавить флаг")
    if submitted and flag.strip():
        insert_flag(flag.strip())
        st.session_state.flag_input_key += 1
        st.rerun()

# Загрузка файла 

uploaded = st.file_uploader(
    "Загрузить файл с флагами",
    type=["csv", "xlsx", "db"],
    key=f"flags_uploader_{st.session_state.uploader_key}"
)

if uploaded is not None:
    try:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded, header=None)
            flags_to_add = df.iloc[:, 0].dropna().astype(str).str.strip()
            for f in flags_to_add:
                if f:
                    insert_flag(f)

        elif uploaded.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded, header=None)
            flags_to_add = df.iloc[:, 0].dropna().astype(str).str.strip()
            for f in flags_to_add:
                if f:
                    insert_flag(f)

        elif uploaded.name.endswith(".db"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            conn = sqlite3.connect(tmp_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM compiler_flags")
            rows = cur.fetchall()
            for (f,) in rows:
                if f and str(f).strip():
                    insert_flag(str(f).strip())
            conn.close()

        st.success(f"Успешно загружено флагов из файла")
        st.session_state.uploader_key += 1
        st.rerun()

    except sqlite3.DatabaseError:
        st.error(
            "Загруженный файл .db не является корректной SQLite-базой "
            "или не содержит таблицу compiler_flags(name)"
        )
    except Exception as e:
        st.error(f"Ошибка при загрузке файла: {e}")

# Отображение флагов 

flags = get_flags()

if len(flags) > 0:
    st.subheader("Текущий список флагов")
    
    # Преобразуем флаги в список для отображения
    display_flags = []
    
    for flag_item in flags:
        if isinstance(flag_item, dict):
            flag_name = None
            if 'flag_name' in flag_item:
                flag_name = flag_item['flag_name']
            elif 'name' in flag_item:
                flag_name = flag_item['name']
            elif flag_item:
                for key, value in flag_item.items():
                    if isinstance(value, str) and value:
                        flag_name = value
                        break
            if flag_name:
                display_flags.append(flag_name)
        elif isinstance(flag_item, str):
            display_flags.append(flag_item)
    
    if display_flags: 
        flag_data = []
        for idx, flag in enumerate(display_flags):
            flag_data.append({
                "Флаг": flag
            })
        
        df_flags = pd.DataFrame(flag_data)
        df_flags.index = range(1, len(df_flags) + 1)
        st.dataframe(df_flags, use_container_width=True)
        
        # Кнопка удаления отдельных флагов
        with st.expander("Удалить флаги компиляции"):
            selected_flag_names = st.multiselect(
                "Выберите флаги для удаления:",
                display_flags
            )
            
            col_del1, col_del2 = st.columns(2)
            
            with col_del1:
                if st.button("Удалить выбранные флаги", type="secondary"):
                    if selected_flag_names:
                        deleted_count = 0
                        for flag_name in selected_flag_names:
                            try:
                                if delete_flag(flag_name):
                                    deleted_count += 1
                            except Exception as e:
                                st.error(f"Ошибка при удалении флага '{flag_name}': {str(e)}")
                        
                        if deleted_count > 0:
                            st.success(f"Удалено {deleted_count} флагов")
                            st.rerun()
                    else:
                        st.warning("Выберите хотя бы один флаг для удаления")
            
            with col_del2:
                if st.button("Очистить весь список флагов компиляции", type="secondary"):
                    try:
                        deleted_count = delete_all_flags()
                        if deleted_count > 0:
                            st.success(f"Удалено {deleted_count} флагов")
                    
                        if 'flags' in st.session_state:
                            del st.session_state.flags
                        
                        st.session_state.uploader_key += 1
                        st.session_state.flag_input_key += 1
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка при очистке флагов: {e}")

    # Кнопка перехода
    st.markdown("---")
    
    if st.button("Далее", type="primary", use_container_width=True):
        st.session_state.flags = display_flags
        st.switch_page("pages/experiments_results.py")

else:
    st.info("Флаги ещё не добавлены. Добавьте флаги вручную или загрузите файл.")

# ---------------- Информация ----------------

with st.sidebar:
    st.info("""
    **Инструкция:**
    1. Введите флаги вручную или загрузите файл.
    2. Флаги сохраняются в базе данных.
    3. Нажмите "Далее" для перехода к экспериментам.
    """)