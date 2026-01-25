import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from backend.analysis import find_optimal_options_iterative
from backend.pareto import pareto_front
import scipy.stats as stats

st.set_page_config(
    page_title="Результаты и аналитика - Оптимизация компиляции",
    layout="wide"
)

st.title("Аналитика результатов оптимизации")

# Проверяем наличие необходимых данных
required_keys = ['flags', 'results', 'combinations']
missing_keys = [key for key in required_keys if key not in st.session_state]

if missing_keys:
    st.error(f"Не хватает данных: {', '.join(missing_keys)}")
    st.info("Вернитесь на страницу 'Критерии и показатели' и загрузите данные")
    st.stop()

# Получаем данные
flags = st.session_state.flags
raw_results = st.session_state.results
binary_matrix = st.session_state.combinations
option_sets = st.session_state.get('option_sets', [])

# Получаем параметры
rank_type = st.session_state.get("rank_type", "descending")
confidence_level = st.session_state.get("confidence_level", 0.05)

# Проверяем, нужно ли запускать анализ
if 'optimization_results' not in st.session_state:
    optimization_results = {}
    criteria_progress = st.progress(0)
    
    criteria_list = list(raw_results.keys())
    
    for idx, crit in enumerate(criteria_list):
        # Определяем тип ранжирования для критерия
        if crit.lower() in ["time", "execution_time", "latency", "duration", 
                          "size", "memory", "memory_usage", "energy", "power"]:
            crit_rank_type = "ascending"
        else:
            crit_rank_type = "descending"
        
        # Запускаем итеративный алгоритм
        with st.spinner(f"Анализирую критерий '{crit}'..."):
            try:
                opt_result = find_optimal_options_iterative(
                    combinations=binary_matrix,
                    scores=raw_results[crit],
                    options=np.array(flags),
                    rank_type=crit_rank_type,
                    alpha=confidence_level
                )
                
                # СОХРАНЯЕМ ВСЕ ОПЦИИ, КОТОРЫЕ БЫЛИ "УЛУЧШЕНИЕМ" НА ЛЮБОЙ ИТЕРАЦИИ
                all_improvements = set()
                
                # Собираем улучшения из истории удалений
                removed_options = opt_result.get("removed_options", [])
                for removed in removed_options:
                    if removed["reason"] == "improvement":
                        all_improvements.add(removed["option"])
                
                # Собираем улучшения из текущих опций (если остались)
                current_options = opt_result.get("optimal_options", [])
                current_z_values = opt_result.get("z_values", {})
                current_p_values = opt_result.get("p_values", {})
                
                for option in current_options:
                    if option in current_z_values and option in current_p_values:
                        z_val = current_z_values[option]
                        p_val = current_p_values[option]
                        
                        if p_val < confidence_level:
                            if (z_val > 0 and crit_rank_type == "descending") or \
                               (z_val < 0 and crit_rank_type == "ascending"):
                                all_improvements.add(option)
                
                # Обновляем список оптимальных флагов в результате
                opt_result["optimal_options"] = list(all_improvements)
                optimization_results[crit] = opt_result
                
                # Выводим информацию о найденных лучших опциях
                if all_improvements:
                    st.success(f"**Критерий: {crit}** ({'чем меньше, тем лучше' if crit_rank_type == 'ascending' else 'чем больше, тем лучше'})")
                    st.info(f"Найдено {len(all_improvements)} оптимальных флагов: {', '.join(sorted(all_improvements))}")
                else:
                    st.info(f"**Критерий: {crit}** - не найдено статистически значимых улучшающих флагов")
                
            except Exception as e:
                st.error(f"Ошибка при анализе критерия '{crit}': {e}")
                optimization_results[crit] = {"error": str(e)}
        
        # Обновляем прогресс
        criteria_progress.progress((idx + 1) / len(criteria_list))
    
    # Сохраняем результаты в session_state
    st.session_state.optimization_results = optimization_results
    st.success(f"Анализ завершен для {len(criteria_list)} критериев!")
else:
    optimization_results = st.session_state.optimization_results
    st.info("Использую ранее рассчитанные результаты")

# -------------------------------------------------
# ДЕТАЛЬНАЯ АНАЛИТИКА ПО КРИТЕРИЯМ И ИТЕРАЦИЯМ
# -------------------------------------------------

st.markdown("---")
st.subheader("Детальная аналитика по критериям")

for crit, opt_result in optimization_results.items():
    if "error" in opt_result:
        st.error(f"Ошибка в критерии '{crit}': {opt_result['error']}")
        continue
    
    with st.expander(f"Критерий: {crit} (тип: {opt_result.get('rank_type', 'N/A')})", expanded=False):
        
        iterations = opt_result.get("iterations", [])
        
        # Детальная таблица по итерациям
        if iterations:
            st.write("#### Статистика по итерациям")
            
            for iter_num, iter_info in enumerate(iterations):
                with st.expander(f"Итерация {iter_num + 1} ({len(iter_info['options'])} опций, {iter_info['n_combinations']} комбинаций)"):
                    
                    # Создаем таблицу с z и p значениями для каждой опции на этой итерации
                    iter_data = []
                    n_current = iter_info["n_combinations"]
                    exp_count = iter_info["exp_count"]
                    
                    for idx, option in enumerate(iter_info["options"]):
                        z_val = iter_info["z_values"][idx] if idx < len(iter_info["z_values"]) else 0
                        p_val = iter_info["p_values"][idx] if idx < len(iter_info["p_values"]) else 1.0
                        exp_cnt = exp_count[idx] if idx < len(exp_count) else 0
                        
                        # Вычисляем μ (mean) и σ (std) для текущей опции
                        control = n_current - exp_cnt
                        if exp_cnt > 0 and control > 0:
                            mean_val = exp_cnt * (n_current + 1) / 2
                            std_val = np.sqrt(exp_cnt * control * (n_current + 1) / 12)
                        else:
                            mean_val = 0
                            std_val = 0
                        
                        # Определяем статус
                        if p_val < confidence_level:
                            if (z_val > 0 and opt_result.get("rank_type") == "descending") or \
                               (z_val < 0 and opt_result.get("rank_type") == "ascending"):
                                status = "Регрессия"
                            else:
                                status = "Улучшение"
                        else:
                            status = "Нет эффекта"
                        
                        iter_data.append({
                            "№": idx + 1,
                            "Опция": option,
                            "z-статистика": f"{z_val:.4f}",
                            "p-значение": f"{p_val:.6f}",
                            "μ (среднее)": f"{mean_val:.2f}",
                            "σ (ст. отклонение)": f"{std_val:.2f}",
                            "Статус": status
                        })
                    
                    if iter_data:
                        df_iter = pd.DataFrame(iter_data)
                        st.dataframe(df_iter, width='stretch')
                    
                    # Информация об удалении опции на этой итерации
                    removed_on_iter = [r for r in opt_result.get("removed_options", []) 
                                     if r["iteration"] == iter_num + 1]
                    
                    if removed_on_iter:
                        st.write("**Опции, удаленные на этой итерации:**")
                        for removed in removed_on_iter:
                            reason_text = "улучшение" if removed["reason"] == "improvement" else "регрессия"
                            st.write(f"`{removed['option']}`: {reason_text} (p={removed['p_value']:.6f}, z={removed['z_value']:.4f})")
        
        # Итоговые статистики для всех опций
        st.write("#### Итоговые статистики для всех опций")
        
        if "z_values" in opt_result and "p_values" in opt_result:
            # Создаем таблицу с итоговыми значениями
            final_stats = []
            for flag in flags:
                if flag in opt_result["z_values"]:
                    z_val = opt_result["z_values"][flag]
                    p_val = opt_result["p_values"][flag]
                    
                    # Определяем статус
                    if p_val < confidence_level:
                        if (z_val > 0 and opt_result.get("rank_type") == "descending") or \
                           (z_val < 0 and opt_result.get("rank_type") == "ascending"):
                            status = "Регрессия"
                        else:
                            status = "Улучшение"
                    else:
                        status = "Нет эффекта"
                    
                    final_stats.append({
                        "Флаг": flag,
                        "z-статистика": f"{z_val:.4f}",
                        "p-значение": f"{p_val:.6f}",
                        "Статус": status
                    })
            
            if final_stats:
                df_final = pd.DataFrame(final_stats)
                st.dataframe(df_final, width='stretch', height=400)

# -------------------------------------------------
# МНОГОКРИТЕРИАЛЬНЫЙ АНАЛИЗ (если критериев 2 и больше)
# -------------------------------------------------

if len(optimization_results) >= 2:
    st.markdown("---")
    st.subheader("Многокритериальный анализ")
    
    criteria_list = list(optimization_results.keys())
    
    # a) Корреляционная таблица
    with st.expander("Корреляционная таблица по критериям"):
        # Создаем DataFrame с результатами всех критериев
        corr_data = {}
        for crit in criteria_list:
            if "error" not in optimization_results[crit]:
                # Получаем исходные значения для этого критерия
                if isinstance(raw_results[crit], dict):
                    # Если результаты в виде словаря
                    corr_data[crit] = list(raw_results[crit].values())
                elif isinstance(raw_results[crit], np.ndarray):
                    # Если результаты в виде массива
                    corr_data[crit] = raw_results[crit]
        
        if len(corr_data) >= 2:
            df_corr = pd.DataFrame(corr_data)
            
            # Вычисляем корреляционную матрицу
            correlation_matrix = df_corr.corr()
            
            # Визуализируем корреляционную матрицу
            fig_corr = px.imshow(
                correlation_matrix,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu",
                title="Корреляционная матрица критериев"
            )
            st.plotly_chart(fig_corr, use_container_width=True)
            
            # Таблица с числовыми значениями
            st.write("Числовые значения корреляции:")
            st.dataframe(correlation_matrix.style.format("{:.3f}"), width='stretch')
        else:
            st.info("Недостаточно данных для построения корреляционной матрицы")
    
    # b) Вариационные ряды
    with st.expander("Вариационные ряды по критериям"):
        if len(criteria_list) >= 2:
            selected_criteria = st.multiselect(
                "Выберите критерии для анализа:",
                criteria_list,
                default=criteria_list[:min(3, len(criteria_list))]
            )
            
            if len(selected_criteria) >= 2:
                # Создаем DataFrame с вариационными рядами
                var_data = {}
                for crit in selected_criteria:
                    if "error" not in optimization_results[crit]:
                        # Берем исходные значения
                        if isinstance(raw_results[crit], dict):
                            values = list(raw_results[crit].values())
                        elif isinstance(raw_results[crit], np.ndarray):
                            values = raw_results[crit]
                        else:
                            continue
                        
                        # Сортируем для вариационного ряда
                        var_data[crit] = np.sort(values)
                
                if len(var_data) >= 2:
                    # Нормализуем длины массивов для сравнения
                    min_len = min(len(v) for v in var_data.values())
                    normalized_data = {k: v[:min_len] for k, v in var_data.items()}
                    
                    # Создаем график
                    fig_var = go.Figure()
                    
                    for crit, values in normalized_data.items():
                        fig_var.add_trace(go.Scatter(
                            x=list(range(1, len(values) + 1)),
                            y=values,
                            mode='lines+markers',
                            name=crit,
                            marker=dict(size=6)
                        ))
                    
                    fig_var.update_layout(
                        title="Вариационные ряды критериев",
                        xaxis_title="Порядковый номер",
                        yaxis_title="Значение",
                        height=500
                    )
                    
                    st.plotly_chart(fig_var, use_container_width=True)
                    
                    # Статистики по вариационным рядам
                    stats_data = []
                    for crit, values in normalized_data.items():
                        stats_data.append({
                            "Критерий": crit,
                            "Минимум": f"{np.min(values):.3f}",
                            "Максимум": f"{np.max(values):.3f}",
                            "Среднее": f"{np.mean(values):.3f}",
                            "Медиана": f"{np.median(values):.3f}",
                            "Станд. отклонение": f"{np.std(values):.3f}",
                            "Размах": f"{np.max(values) - np.min(values):.3f}"
                        })
                    
                    if stats_data:
                        df_stats = pd.DataFrame(stats_data)
                        st.dataframe(df_stats, width='stretch')
    
    # c) График Парето-оптимальных значений
    with st.expander("Парето-оптимальные значения"):
        if len(criteria_list) >= 2:
            # Выбираем критерии для Парето-анализа
            pareto_criteria = st.multiselect(
                "Выберите критерии для Парето-анализа:",
                criteria_list,
                default=criteria_list[:min(2, len(criteria_list))]
            )
            
            if len(pareto_criteria) == 2:
                # Создаем точки для Парето-фронта
                points = {}
                
                # Получаем значения для каждой комбинации
                for comb_idx, comb in enumerate(option_sets):
                    point_values = []
                    for crit in pareto_criteria:
                        if isinstance(raw_results[crit], dict):
                            point_values.append(raw_results[crit].get(comb, 0))
                        elif isinstance(raw_results[crit], np.ndarray):
                            if comb_idx < len(raw_results[crit]):
                                point_values.append(raw_results[crit][comb_idx])
                            else:
                                point_values.append(0)
                    
                    # Добавляем только если есть оба значения
                    if len(point_values) == 2:
                        points[f"Комб {comb_idx+1}"] = point_values
                
                if len(points) >= 3:
                    # Находим Парето-оптимальные точки
                    pareto_points = pareto_front(points)
                    
                    # Подготавливаем данные для графика
                    x_vals = [points[key][0] for key in points.keys()]
                    y_vals = [points[key][1] for key in points.keys()]
                    
                    pareto_x = [points[key][0] for key in pareto_points]
                    pareto_y = [points[key][1] for key in pareto_points]
                    
                    # Создаем график
                    fig_pareto = go.Figure()
                    
                    # Все точки
                    fig_pareto.add_trace(go.Scatter(
                        x=x_vals,
                        y=y_vals,
                        mode='markers',
                        name='Все точки',
                        marker=dict(size=10, color='blue', opacity=0.6),
                        text=list(points.keys()),
                        hovertemplate='%{text}<br>%{x}, %{y}<extra></extra>'
                    ))
                    
                    # Парето-оптимальные точки
                    fig_pareto.add_trace(go.Scatter(
                        x=pareto_x,
                        y=pareto_y,
                        mode='markers+lines',
                        name='Парето-фронт',
                        marker=dict(size=12, color='red', symbol='star'),
                        line=dict(color='red', width=2),
                        text=pareto_points,
                        hovertemplate='%{text}<br>%{x}, %{y}<extra></extra>'
                    ))
                    
                    fig_pareto.update_layout(
                        title=f"Парето-оптимальные значения ({pareto_criteria[0]} vs {pareto_criteria[1]})",
                        xaxis_title=pareto_criteria[0],
                        yaxis_title=pareto_criteria[1],
                        height=600
                    )
                    
                    st.plotly_chart(fig_pareto, use_container_width=True)
                    
                    # Таблица Парето-оптимальных точек
                    if pareto_points:
                        st.write("**Парето-оптимальные комбинации:**")
                        pareto_table = []
                        for point in pareto_points:
                            idx = int(point.split()[1]) - 1
                            pareto_table.append({
                                "Комбинация": point,
                                pareto_criteria[0]: f"{points[point][0]:.3f}",
                                pareto_criteria[1]: f"{points[point][1]:.3f}",
                                "Флаги": option_sets[idx] if idx < len(option_sets) else "N/A"
                            })
                        
                        df_pareto = pd.DataFrame(pareto_table)
                        st.dataframe(df_pareto, width='stretch')
            else:
                st.info("Для построения графика Парето выберите ровно 2 критерия")

# -------------------------------------------------
# СВОДНАЯ ТАБЛИЦА ВСЕХ РЕЗУЛЬТАТОВ
# -------------------------------------------------

st.markdown("---")
st.subheader("Сводная таблица всех результатов")

summary_data = []
for crit, opt_result in optimization_results.items():
    if "error" not in opt_result:
        for flag in flags:
            if flag in opt_result.get("z_values", {}):
                z_val = opt_result["z_values"][flag]
                p_val = opt_result["p_values"][flag]
                
                # Определяем статус
                if p_val < confidence_level:
                    if (z_val > 0 and opt_result.get("rank_type") == "descending") or \
                       (z_val < 0 and opt_result.get("rank_type") == "ascending"):
                        status = "Регрессия"
                    else:
                        status = "Улучшение"
                else:
                    status = "Нет эффекта"
                
                summary_data.append({
                    "Критерий": crit,
                    "Тип": opt_result.get("rank_type", "N/A"),
                    "Флаг": flag,
                    "z-статистика": f"{z_val:.4f}",
                    "p-значение": f"{p_val:.6f}",
                    "Статус": status
                })

if summary_data:
    df_summary = pd.DataFrame(summary_data)
    
    # Сортируем по критерию и z-статистике
    df_summary = df_summary.sort_values(["Критерий", "z-статистика"], 
                                        ascending=[True, False])
    
    st.dataframe(df_summary, width='stretch', height=500)
    
    # Опции для фильтрации
    col1, col2 = st.columns(2)
    with col1:
        filter_crit = st.selectbox(
            "Фильтр по критерию:",
            ["Все"] + sorted(df_summary["Критерий"].unique())
        )
    with col2:
        filter_status = st.selectbox(
            "Фильтр по статусу:",
            ["Все", "Улучшение", "Регрессия", "Нет эффекта"]
        )
    
    # Применяем фильтры
    filtered_df = df_summary.copy()
    
    if filter_crit != "Все":
        filtered_df = filtered_df[filtered_df["Критерий"] == filter_crit]
    
    if filter_status != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == filter_status]
    
    if len(filtered_df) > 0:
        st.write(f"**Отфильтровано:** {len(filtered_df)} записей")
        # Убрана дополнительная таблица
else:
    st.info("Нет данных для сводной таблицы")

# -------------------------------------------------
# ИНФОРМАЦИЯ О МЕТОДЕ
# -------------------------------------------------

with st.expander("Пояснения к статистическим показателям"):
    st.markdown(f"""
    ### Метод Манна-Уитни: пояснения
    
    **Статистические показатели:**
    - **z-статистика:** показывает направление и силу эффекта флага
    - **p-значение:** вероятность случайного возникновения эффекта (p < {confidence_level} = статистически значимо)
    - **μ (среднее):** ожидаемое значение суммы рангов для группы
    - **σ (стандартное отклонение):** мера разброса экспериментальных данных
    
    **Интерпретация:**
    - **Улучшение:** флаг положительно влияет на критерий (p < {confidence_level})
    - **Регрессия:** флаг отрицательно влияет на критерий (p < {confidence_level})
    - **Нет эффекта:** влияние флага статистически незначимо (p ≥ {confidence_level})
    
    **Параметры анализа:**
    - Уровень значимости α = {confidence_level}
    - Тип ранжирования: {rank_type}
    """)