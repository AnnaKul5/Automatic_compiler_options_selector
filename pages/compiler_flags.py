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

st.title("Укажите список булевых флагов компилятора")


st.markdown(
"""
### Введите флаги вручную **или** загрузите файл.

Поддерживаемые форматы:
- **CSV** — один столбец с флагами  
- **Excel (.xlsx)** — первый столбец  
- **SQLite (.db)** — таблица `compiler_flags(name)`
""")

# ---------------- Ручной ввод ----------------

# Используем форму для ручного ввода флага
with st.form("add_flag_form"):
    flag = st.text_input("Введите флаг компилятора (например: -O3)", 
                        key=f"flag_input_{st.session_state.flag_input_key}")
    
    submitted = st.form_submit_button("Добавить флаг")
    if submitted and flag.strip():
        insert_flag(flag.strip())
        # Увеличиваем ключ для сброса поля ввода при следующем рендере
        st.session_state.flag_input_key += 1
        st.rerun()

# ---------------- Загрузка файла ----------------

uploaded = st.file_uploader(
    "Загрузить файл с флагами",
    type=["csv", "xlsx", "db"],
    key=f"flags_uploader_{st.session_state.uploader_key}"
)

if uploaded is not None:
    try:
        if uploaded.name.endswith(".csv"):
            # Читаем CSV без пропуска строк, header=None чтобы не считать первую строку заголовком
            df = pd.read_csv(uploaded, header=None)
            # Берем все строки из первого столбца
            flags_to_add = df.iloc[:, 0].dropna().astype(str).str.strip()
            for f in flags_to_add:
                if f:  # Проверяем, что строка не пустая
                    insert_flag(f)

        elif uploaded.name.endswith(".xlsx"):
            # Читаем Excel без пропуска строк, header=None
            df = pd.read_excel(uploaded, header=None)
            # Берем все строки из первого столбца
            flags_to_add = df.iloc[:, 0].dropna().astype(str).str.strip()
            for f in flags_to_add:
                if f:  # Проверяем, что строка не пустая
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
                if f and str(f).strip():  # Проверяем, что флаг не пустой
                    insert_flag(str(f).strip())

            conn.close()

        st.success(f"Успешно загружено флагов из файла")
        # Увеличиваем ключ для сброса загрузчика
        st.session_state.uploader_key += 1
        st.rerun()

    except sqlite3.DatabaseError:
        st.error(
            "Загруженный файл .db не является корректной SQLite-базой "
            "или не содержит таблицу compiler_flags(name)"
        )
    except Exception as e:
        st.error(f"Ошибка при загрузке файла: {e}")

# ---------------- Отображение флагов ----------------

# Получаем флаги из базы данных
flags = get_flags()

if len(flags) > 0:
    st.subheader("Текущий список флагов")
    
    # Преобразуем флаги в список для отображения
    display_flags = []
    
    for flag_item in flags:
        if isinstance(flag_item, dict):
            # Извлекаем имя флага из словаря
            flag_name = None
            if 'flag_name' in flag_item:
                flag_name = flag_item['flag_name']
            elif 'name' in flag_item:
                flag_name = flag_item['name']
            elif flag_item:
                # Ищем первое строковое значение
                for key, value in flag_item.items():
                    if isinstance(value, str) and value:
                        flag_name = value
                        break
            
            if flag_name:
                display_flags.append(flag_name)
                
        elif isinstance(flag_item, str):
            display_flags.append(flag_item)
    
    if display_flags:
        df_flags = pd.DataFrame(display_flags, columns=["Флаг"])
        df_flags.index = range(1, len(df_flags) + 1)  
        df_flags.index.name = "№"
        
        st.table(df_flags)
        
        # Кнопка удаления отдельных флагов
        with st.expander("Удалить флаги компиляции"):
            selected_flag_names = st.multiselect(
                "Выберите флаги для удаления:",
                display_flags
            )
            
            # Создаем две кнопки в одной строке
            col_del1, col_del2 = st.columns(2)
            
            with col_del1:
                if st.button("Удалить выбранные флаги", type="secondary"):
                    if selected_flag_names:
                        deleted_count = 0
                        for flag_name in selected_flag_names:
                            # Удаляем флаг по имени (функция принимает имя, а не ID)
                            try:
                                if delete_flag(flag_name):  # Теперь передаем имя флага
                                    deleted_count += 1
                                    st.success(f"Флаг '{flag_name}' удален")
                                else:
                                    st.warning(f"Флаг '{flag_name}' не найден в базе данных")
                            except Exception as e:
                                st.error(f"Ошибка при удалении флага '{flag_name}': {str(e)}")
                        
                        if deleted_count > 0:
                            st.success(f"Удалено {deleted_count} флагов")
                            st.rerun()
                        else:
                            st.warning("Не удалось удалить ни одного флага")
                    else:
                        st.warning("Выберите хотя бы один флаг для удаления")
            
            with col_del2:
                if st.button("Очистить весь список флагов компиляции", type="secondary"):
                    # Удаляем все флаги из базы данных
                    try:
                        deleted_count = delete_all_flags()
                        if deleted_count > 0:
                            st.success(f"Удалено {deleted_count} флагов")
                        else:
                            st.info("Не было флагов для удаления")
                        
                        # Очищаем session_state
                        if 'flags' in st.session_state:
                            del st.session_state.flags
                        
                        # Увеличиваем ключи для сброса виджетов
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
    1. Введите флаги вручную ИЛИ загрузите файл
    2. Флаги сохраняются в базе данных
    3. Нажмите "Далее" для перехода к экспериментам
    
    **Параметры анализа:**
    - **Тип ранжирования:** ascending (меньше = лучше) или descending (больше = лучше)
    - **Уровень доверия (α):** число от 0 до 1 (0.05 = 95% доверительный интервал)
    
    **Очистка:**
    - "Очистить весь список флагов компиляции" - удаляет все флаги из БД
    - Для удаления отдельных флагов используйте расширенный режим
    """)