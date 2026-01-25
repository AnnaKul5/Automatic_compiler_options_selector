import streamlit as st
import pandas as pd
import numpy as np
from backend.analysis import generate_orthogonal_array  # Измененный импорт
from db.database import insert_score, get_flags, delete_all_scores, delete_all_combinations

st.set_page_config(
    page_title="Критерии и показатели - Оптимизация компиляции",
    layout="wide"
)

st.title("Результаты экспериментов")

# Инициализация ключей для сброса виджетов
if 'uploader_key_results' not in st.session_state:
    st.session_state.uploader_key_results = 0

# -------------------------------------------------
# Критерии с настройками
# -------------------------------------------------

st.markdown(
"""
### Добавление критериев с настройками анализа
"""
)

# Инициализируем структуру для хранения настроек критериев
if "criteria_settings" not in st.session_state:
    st.session_state.criteria_settings = {}

if "criteria" not in st.session_state:
    st.session_state.criteria = ["Score"]

# 1. Кнопка добавления критерия с настройками
col_add, col_del = st.columns(2)

with col_add:
    with st.expander("Добавить критерий"):
        new_criterion = st.text_input("Введите название критерия:", key="new_criterion_input")
        
        # Настройки для нового критерия
        col_rank, col_alpha = st.columns(2)
        
        with col_rank:
            new_criterion_rank_type = st.radio(
                "Тип ранжирования:",
                ["По возрастанию (ascending)", "По убыванию (descending)"],
                index=1,
                key="new_criterion_rank_type",
                help="ascending: меньшие значения лучше\n descending: большие значения лучше"
            )
        
        with col_alpha:
            new_criterion_alpha = st.text_input(
                "Уровень доверия (α):",
                value="0.05",
                key="new_criterion_alpha",
                help="Введите число от 0 до 1 (например: 0.05, 0.01). По умолчанию: 0.05"
            )
        
        if st.button("Добавить") and new_criterion.strip():
            if new_criterion.strip() not in st.session_state.criteria:
                # Добавляем критерий
                st.session_state.criteria.append(new_criterion.strip())
                
                # Сохраняем настройки критерия
                rank_type_value = "descending" if "убыванию" in new_criterion_rank_type else "ascending"
                
                # Валидация уровня доверия
                alpha_value = 0.05
                if new_criterion_alpha:
                    try:
                        alpha_value = float(new_criterion_alpha.replace(',', '.'))
                        if not (0 < alpha_value < 1):
                            st.warning("Уровень доверия должен быть в диапазоне от 0 до 1. Используется значение по умолчанию: 0.05")
                            alpha_value = 0.05
                    except ValueError:
                        st.warning("Некорректное значение уровня доверия. Используется значение по умолчанию: 0.05")
                        alpha_value = 0.05
                
                st.session_state.criteria_settings[new_criterion.strip()] = {
                    "rank_type": rank_type_value,
                    "alpha": alpha_value
                }
                
                # Добавляем новый критерий в results с нулевыми значениями
                if 'results' not in st.session_state:
                    st.session_state.results = {}
                
                # Инициализируем новый критерий нулевыми значениями для всех комбинаций
                st.session_state.results[new_criterion.strip()] = {}
                
                st.success(f"Критерий '{new_criterion}' добавлен")
                st.rerun()
            else:
                st.warning("Критерий с таким названием уже существует")

with col_del:
    # 2. Кнопка удаления критериев
    with st.expander("Удалить критерии"):
        if st.session_state.criteria:
            selected_criteria = st.multiselect(
                "Выберите критерии для удаления:",
                st.session_state.criteria
            )
            
            if st.button("Удалить выбранные", type="secondary"):
                for crit in selected_criteria:
                    if crit in st.session_state.criteria:
                        st.session_state.criteria.remove(crit)
                    
                    # Удаляем настройки критерия
                    if crit in st.session_state.criteria_settings:
                        del st.session_state.criteria_settings[crit]
                
                # Удаляем данные этих критериев из results
                if 'results' in st.session_state:
                    for crit in selected_criteria:
                        if crit in st.session_state.results:
                            del st.session_state.results[crit]
                
                st.success(f"Удалено {len(selected_criteria)} критериев")
                st.rerun()
        else:
            st.info("Нет критериев для удаления")

# -------------------------------------------------
# Редактирование настроек существующих критериев
# -------------------------------------------------

st.markdown("### Редактирование настроек критериев")

if st.session_state.criteria:
    for crit in st.session_state.criteria:
        with st.expander(f"Настройки критерия: {crit}", expanded=False):
            col_set1, col_set2 = st.columns(2)
            
            with col_set1:
                # Определяем текущий тип ранжирования
                current_rank_type = st.session_state.criteria_settings.get(crit, {}).get("rank_type", "descending")
                current_rank_index = 1 if current_rank_type == "descending" else 0
                
                updated_rank_type = st.radio(
                    "Тип ранжирования:",
                    ["По возрастанию (ascending)", "По убыванию (descending)"],
                    index=current_rank_index,
                    key=f"rank_{crit}",
                    help="ascending: меньшие значения лучше\n descending: большие значения лучше"
                )
            
            with col_set2:
                # Определяем текущий уровень доверия
                current_alpha = st.session_state.criteria_settings.get(crit, {}).get("alpha", 0.05)
                
                updated_alpha = st.text_input(
                    "Уровень доверия (α):",
                    value=str(current_alpha),
                    key=f"alpha_{crit}",
                    help="Введите число от 0 до 1 (например: 0.05, 0.01). По умолчанию: 0.05"
                )
            
            # Кнопка сохранения изменений
            if st.button(f"Сохранить настройки для '{crit}'", key=f"save_{crit}"):
                # Обновляем тип ранжирования
                rank_type_value = "descending" if "убыванию" in updated_rank_type else "ascending"
                st.session_state.criteria_settings[crit] = {
                    "rank_type": rank_type_value
                }
                
                # Валидация и обновление уровня доверия
                if updated_alpha:
                    try:
                        alpha_value = float(updated_alpha.replace(',', '.'))
                        if 0 < alpha_value < 1:
                            st.session_state.criteria_settings[crit]["alpha"] = alpha_value
                            st.success(f"Настройки для критерия '{crit}' обновлены")
                        else:
                            st.warning(f"Уровень доверия должен быть в диапазоне от 0 до 1. Используется предыдущее значение: {current_alpha}")
                            st.session_state.criteria_settings[crit]["alpha"] = current_alpha
                    except ValueError:
                        st.warning(f"Некорректное значение уровня доверия. Используется предыдущее значение: {current_alpha}")
                        st.session_state.criteria_settings[crit]["alpha"] = current_alpha
                else:
                    # Если поле пустое, используем значение по умолчанию
                    st.session_state.criteria_settings[crit]["alpha"] = 0.05
                    st.info(f"Установлено значение по умолчанию α=0.05 для критерия '{crit}'")
                
                st.rerun()
else:
    st.info("Нет критериев для редактирования. Добавьте критерии.")

criteria = st.session_state.criteria

st.markdown(
"""
### Введите значения метрик для каждой комбинации флагов или загрузите файл с результатами
"""
)

# -------------------------------------------------
# Получаем флаги и комбинации
# -------------------------------------------------

flags = st.session_state.get("flags", get_flags())

if not flags:
    st.error("Сначала необходимо задать флаги компилятора")
    st.stop()

binary_matrix, option_sets = generate_orthogonal_array(flags)

if "option_sets" not in st.session_state:
    st.session_state.option_sets = option_sets
    st.session_state.binary_matrix = binary_matrix

option_sets = st.session_state.option_sets
binary_matrix = st.session_state.binary_matrix

# -------------------------------------------------
# Сворачиваемый раздел ручного ввода
# -------------------------------------------------

with st.expander("Ввести значения вручную", expanded=False):
    # Инициализируем results для всех текущих критериев
    if 'results' not in st.session_state:
        st.session_state.results = {}
    
    # Убедимся, что все текущие критерии есть в results
    for crit in criteria:
        if crit not in st.session_state.results:
            st.session_state.results[crit] = {}
    
    # Временное хранилище для ввода (не сохраняется в session_state до нажатия кнопки)
    temp_results = {}
    for crit in criteria:
        temp_results[crit] = {}
        # Копируем текущие значения или используем 0
        for comb in option_sets:
            temp_results[crit][comb] = st.session_state.results.get(crit, {}).get(comb, 0.0)
    
    for idx, comb in enumerate(option_sets):
        st.markdown(f"**Комбинация {idx+1}**")
        
        # Получаем бинарную строку для этой комбинации
        binary_row = binary_matrix[idx]
        
        # Находим какие флаги включены
        enabled_flags = []
        for i, val in enumerate(binary_row):
            if val == 1:
                enabled_flags.append(flags[i])
        
        if enabled_flags:
            for flag in enabled_flags:
                st.markdown(f"- `{flag}`")
        else:
            st.markdown("- (без флагов)")
        
        # Поля ввода для каждого критерия
        cols = st.columns(len(criteria))
        
        for col_idx, (col, crit) in enumerate(zip(cols, criteria)):
            # Создаем уникальный ключ
            key = f"{crit}_{idx}"
            
            # Получаем текущее значение из временного хранилища
            current_value = temp_results[crit].get(comb, 0.0)
            
            # Создаем поле ввода
            value = col.number_input(
                crit,
                value=float(current_value),
                key=key,
                format="%.3f"
            )
            
            # Сохраняем значение во временное хранилище
            temp_results[crit][comb] = value
        
        st.markdown("---")
    
    # Кнопка для сохранения введенных значений
    if st.button("Установить заданные значения", type="primary"):
        # Очищаем старые данные из БД
        delete_all_scores()
        delete_all_combinations()
        
        # Обновляем session_state.results временными значениями
        for crit in criteria:
            if crit not in st.session_state.results:
                st.session_state.results[crit] = {}
            for comb in option_sets:
                st.session_state.results[crit][comb] = temp_results[crit].get(comb, 0.0)
        
        # Сохраняем результаты в БД
        for idx, comb in enumerate(option_sets):
            for crit in criteria:
                value = temp_results[crit].get(comb, 0.0)
                insert_score(comb, crit, value)
        
        st.success(f"Значения сохранены для {len(option_sets)} комбинаций")
        st.rerun()

# -------------------------------------------------
# Загрузка файла с результатами
# -------------------------------------------------

st.subheader("Загрузка результатов из файла")

uploaded = st.file_uploader(
    "Загрузить файл с результатами",
    type=["csv", "xlsx"],
    key=f"results_uploader_{st.session_state.uploader_key_results}",
    help=f"Формат: файл должен содержать {len(criteria)} столбцов (критериев) и {len(option_sets)} строк (комбинаций)"
)

if uploaded is not None:
    try:
        # Загружаем файл
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded, decimal=',')
        else:  # Excel
            df = pd.read_excel(uploaded)
            
        # Проверка и преобразование данных
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
        
        st.write(f"**Загружен файл:** {uploaded.name}")
        st.write(f"**Размер файла:** {df.shape[0]} строк × {df.shape[1]} столбцов")
        
        # ПРОВЕРКА 1: Количество критериев должно совпадать
        if df.shape[1] != len(criteria):
            st.error(f"Ошибка: Файл содержит {df.shape[1]} столбцов, а ожидается {len(criteria)} (по количеству критериев)")
            st.write("**Текущие критерии:**", ", ".join(criteria))
        
        # ПРОВЕРКА 2: Количество строк должно совпадать с количеством комбинаций
        n_combinations = len(option_sets)
        
        st.write(f"**Проверка:**")
        st.write(f"- Строк в файле: {df.shape[0]}")
        st.write(f"- Ожидается строк (комбинаций): {n_combinations}")
        
        if df.shape[0] != n_combinations:
            st.error(f"Ошибка: Количество строк в файле ({df.shape[0]}) должно совпадать с количеством комбинаций ({n_combinations})")
        else:
            st.success("Количество строк соответствует количеству комбинаций")
            
            if df.shape[1] == len(criteria):
                # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - загружаем данные
                
                # Получаем названия критериев из заголовков столбцов
                loaded_criteria = df.columns.tolist()
                
                # Обновляем критерии в session_state, если названия отличаются
                if loaded_criteria != criteria:
                    st.info(f"Обновлены названия критериев: {', '.join(loaded_criteria)}")
                    st.session_state.criteria = loaded_criteria
                    criteria = loaded_criteria
                    
                    # Для новых критериев устанавливаем настройки по умолчанию
                    for crit in loaded_criteria:
                        if crit not in st.session_state.criteria_settings:
                            st.session_state.criteria_settings[crit] = {
                                "rank_type": "descending",
                                "alpha": 0.05
                            }
                
                # Очищаем БД
                delete_all_scores()
                delete_all_combinations()
                
                # Очищаем и заполняем результаты
                st.session_state.results = {}
                
                # Заполняем результаты из DataFrame
                for idx, comb in enumerate(option_sets):
                    for crit in criteria:
                        if idx < len(df[crit]):
                            value = float(df[crit].iloc[idx])
                            if crit not in st.session_state.results:
                                st.session_state.results[crit] = {}
                            st.session_state.results[crit][comb] = value
                            insert_score(comb, crit, value)
                
                # Увеличиваем ключ для сброса загрузчика
                st.session_state.uploader_key_results += 1
                
                st.success(f"Данные успешно загружены: {len(option_sets)} комбинаций × {len(criteria)} критериев")
                st.rerun()
                
    except Exception as e:
        st.error(f"Ошибка при загрузке файла: {e}")

# -------------------------------------------------
# Информация о формате файла
# -------------------------------------------------

with st.expander("Информация о формате файла"):
    st.markdown(f"""
    **Требования к файлу с результатами:**
    
    1. **Формат:** CSV или Excel (.xlsx)
    2. **Структура:**
       - Первая строка: названия критериев
       - Каждая следующая строка: значения для одной комбинации флагов
    3. **Количество:**
       - Столбцов: должно совпадать с количеством критериев ({len(criteria)})
       - Строк: должно быть ровно {len(option_sets)} (по количеству комбинаций)
    
    **Настройки критериев:**
    - Тип ранжирования и уровень доверия (α) настраиваются отдельно для каждого критерия
    - После загрузки файла можно отредактировать настройки для каждого критерия
    """)

# -------------------------------------------------
# Таблица текущих значений критериев 
# -------------------------------------------------

st.subheader("Текущие значения критериев")

# Проверяем, что results существует и содержит данные
if 'results' in st.session_state and criteria:
    # Создаем DataFrame для отображения
    display_data = []
    
    # Проходим по всем комбинациям
    for i, comb in enumerate(option_sets):
        row = {"№": i+1, "Комбинация": comb if comb else "(без флагов)"}
        
        # Добавляем значение для каждого критерия
        for crit in criteria:
            # Берем значение из results, если оно есть, иначе 0
            value = st.session_state.results.get(crit, {}).get(comb, 0.0)
            row[crit] = float(value)
        
        display_data.append(row)
    
    if display_data:
        df_current = pd.DataFrame(display_data)
        # Устанавливаем индекс как столбец № и убираем столбец с индексом 0
        df_current.set_index("№", inplace=True)
        st.dataframe(df_current, width='stretch', height=400)
    else:
        st.info("Нет данных для отображения")
else:
    st.info("Введите значения критериев вручную или загрузите файл")

# -------------------------------------------------
# Кнопка "Очистить всё"
# -------------------------------------------------

if st.button("Очистить всё", type="secondary"):
    try:
        # Очищаем результаты из БД
        deleted_scores = delete_all_scores()
        deleted_combinations = delete_all_combinations()
        
        # Очищаем критерии (оставляем только "Score" по умолчанию)
        st.session_state.criteria = ["Score"]
        
        # Сбрасываем настройки критериев
        st.session_state.criteria_settings = {
            "Score": {"rank_type": "descending", "alpha": 0.05}
        }
        
        # Очищаем результаты в session_state (только Score с нулевыми значениями)
        st.session_state.results = {"Score": {}}
        
        # Увеличиваем ключ для сброса загрузчика файла
        st.session_state.uploader_key_results += 1
        
        st.success(f"Очищено {deleted_scores} результатов, {deleted_combinations} комбинаций. Критерии сброшены к исходным.")
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка при очистке: {e}")

# -------------------------------------------------
# Сохранение и переход дальше
# -------------------------------------------------

if st.button("Далее", type="primary"):
    # Проверяем, есть ли данные
    has_data = False
    if 'results' in st.session_state:
        for crit in criteria:
            if crit in st.session_state.results and st.session_state.results[crit]:
                has_data = True
                break
    
    if not has_data:
        st.warning("Нет данных для анализа. Введите значения или загрузите файл.")
    else:
        # Проверяем, что для всех критериев есть настройки
        for crit in criteria:
            if crit not in st.session_state.criteria_settings:
                st.session_state.criteria_settings[crit] = {
                    "rank_type": "descending",
                    "alpha": 0.05
                }
        
        # Сохраняем настройки критериев в session_state для использования в аналитике
        st.session_state.criteria_settings_all = st.session_state.criteria_settings.copy()
        
        # Преобразуем результаты в правильный формат
        results_numpy = {}
        
        for crit in criteria:
            values = []
            for comb in option_sets:
                value = st.session_state.results.get(crit, {}).get(comb, 0.0)
                values.append(float(value))
            
            try:
                arr = np.array(values, dtype=np.float64)
                results_numpy[crit] = arr
            except Exception as e:
                st.error(f"Ошибка преобразования критерия {crit}: {e}")
                results_numpy[crit] = np.zeros(len(option_sets))
        
        # Сохраняем в session_state
        st.session_state.combinations = binary_matrix
        st.session_state.option_sets = option_sets
        st.session_state.results = results_numpy
        st.session_state.flags = flags

        st.success(f"Подготовлено данных для анализа: {len(option_sets)} комбинаций × {len(criteria)} критериев")
        st.switch_page("pages/analitics.py")