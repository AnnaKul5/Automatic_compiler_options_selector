import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from backend.analysis import find_optimal_options_iterative
from backend.decision_tree import DecisionTreeBuilder
import scipy.stats as stats

def color_status(val):
    if "Оптимальная" in str(val):
        return 'background-color: #C8E6C9'
    if "Улучшение" in str(val):
        return 'background-color: #C8E6C9'
    elif "Ухудшение" in str(val):
        return 'background-color: #FFCDD2'
    return ''

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

if 'criteria_settings_all' in st.session_state:
    criteria_settings = st.session_state.criteria_settings_all
else:
    criteria_settings = {}
    for crit in list(raw_results.keys()):
        criteria_settings[crit] = {
            "rank_type": "descending",
            "alpha": 0.05
        }

# Проверяем, нужно ли запускать анализ
if 'optimization_results' not in st.session_state:
    optimization_results = {}
    criteria_progress = st.progress(0)
    
    criteria_list = list(raw_results.keys())
    
    for idx, crit in enumerate(criteria_list):
        crit_settings = criteria_settings.get(crit, {})
        crit_rank_type = crit_settings.get("rank_type", "descending") 
        crit_alpha = crit_settings.get("alpha", 0.05)  
        
        with st.spinner(f"Выполняю анализ для '{crit}'..."):
            try:
                opt_result = find_optimal_options_iterative(
                    combinations=binary_matrix,
                    scores=raw_results[crit],
                    options=np.array(flags),
                    rank_type=crit_rank_type, 
                    alpha=crit_alpha          
                )
                
                all_significant_options = set()
                all_improvements = set()
                all_regressions = set()
                
                removed_options = opt_result.get("removed_options", [])
                for removed in removed_options:
                    option = removed["option"]
                    p_val = removed["p_value"]
                    if p_val <= crit_alpha:
                        all_significant_options.add(option)
                        if removed["reason"] == "improvement":
                            all_improvements.add(option)
                        else:
                            all_regressions.add(option)
                
                current_options_list = opt_result.get("optimal_options", [])
                current_u_values = opt_result.get("u_values", {})
                current_z_values = opt_result.get("z_values", {})
                current_p_values = opt_result.get("p_values", {})
                methods_used = opt_result.get("methods_used", {})
                iterations_data = opt_result.get("iterations", [])
                
                for option in flags:
                    if option in current_p_values:
                        p_val = current_p_values[option]
                        method = methods_used.get(option, "z_test")
                        
                        if p_val <= crit_alpha:
                            all_significant_options.add(option)
                            
                            if method == "u_test":
                                u_val = current_u_values.get(option, 0)
                                exp_cnt = 0
                                control_cnt = 0
                                for iter_info in iterations_data:
                                    if option in iter_info["options"]:
                                        idx_opt = iter_info["options"].index(option)
                                        if idx_opt < len(iter_info["exp_count"]):
                                            exp_cnt = iter_info["exp_count"][idx_opt]
                                            control_cnt = iter_info["n_combinations"] - exp_cnt
                                            break
                                
                                max_u = exp_cnt * control_cnt if exp_cnt > 0 and control_cnt > 0 else 1
                                
                                if crit_rank_type == "descending":
                                    if u_val >= 0.95 * max_u:
                                        all_improvements.add(option)
                                    elif u_val <= 0.05 * max_u:
                                        all_regressions.add(option)
                                else:
                                    if u_val <= 0.05 * max_u:
                                        all_improvements.add(option)
                                    elif u_val >= 0.95 * max_u:
                                        all_regressions.add(option)
                            else:
                                z_val = current_z_values.get(option, 0)
                                if (z_val > 0 and crit_rank_type == "descending") or \
                                   (z_val < 0 and crit_rank_type == "ascending"):
                                    all_improvements.add(option)
                                else:
                                    all_regressions.add(option)
                
                opt_result["significant_options"] = list(all_significant_options)
                opt_result["optimal_options"] = list(all_improvements)
                opt_result["regression_options"] = list(all_regressions)

                optimization_results[crit] = opt_result

            except Exception as e:
                st.error(f"Ошибка при анализе критерия '{crit}': {e}")
                optimization_results[crit] = {"error": str(e)}
        
        criteria_progress.progress((idx + 1) / len(criteria_list))
    
    st.session_state.optimization_results = optimization_results
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
    
    rank_type_text = (
        "максимизировать значения"
        if opt_result.get("rank_type", "descending") == "descending"
        else "минимизировать значения"
    )

    with st.expander(f"Критерий: {crit} ({rank_type_text})", expanded=False):

        iterations = opt_result.get("iterations", [])
        
        if iterations:
            st.write("#### Статистика по итерациям")
            rank_type_crit = opt_result.get("rank_type", "descending")
            
            for iter_num, iter_info in enumerate(iterations):
                with st.expander(f"Итерация {iter_num + 1}"):
                    
                    iter_data = []
                    n_current = iter_info["n_combinations"]
                    exp_count = iter_info["exp_count"]
                    methods_list = iter_info.get("methods_used", ["z_test"] * len(iter_info["options"]))
                    
                    for idx_opt, option in enumerate(iter_info["options"]):
                        p_val = iter_info["p_values"][idx_opt] if idx_opt < len(iter_info["p_values"]) else 1.0
                        u_val = iter_info["u_values"][idx_opt] if idx_opt < len(iter_info["u_values"]) else 0.0
                        z_val = iter_info["z_values"][idx_opt] if idx_opt < len(iter_info["z_values"]) else 0.0
                        method = methods_list[idx_opt] if idx_opt < len(methods_list) else "z_test"
                        exp_cnt = exp_count[idx_opt] if idx_opt < len(exp_count) else 0
                        control_cnt = n_current - exp_cnt
                        
                        max_u = exp_cnt * control_cnt if method == "u_test" and exp_cnt > 0 and control_cnt > 0 else 1
                        is_significant = p_val <= confidence_level
                        
                        if is_significant:
                            if method == "u_test":
                                if rank_type_crit == "descending":
                                    if u_val >= 0.95 * max_u:
                                        status = "Улучшение"
                                    elif u_val <= 0.05 * max_u:
                                        status = "Ухудшение"
                                    else:
                                        status = "Значимо"
                                else:
                                    if u_val <= 0.05 * max_u:
                                        status = "Улучшение"
                                    elif u_val >= 0.95 * max_u:
                                        status = "Ухудшение"
                                    else:
                                        status = "Значимо"
                            else:
                                if (z_val > 0 and rank_type_crit == "descending") or (z_val < 0 and rank_type_crit == "ascending"):
                                    status = "Улучшение"
                                else:
                                    status = "Ухудшение"
                        else:
                            status = "Нет эффекта"
                        
                        if method == "u_test":
                            iter_data.append({
                                "Опция": option,
                                "U-статистика": f"{u_val:.0f}",
                                "p-значение": f"{p_val:.2f}",
                                "Статус": status
                            })
                        else:
                            if exp_cnt > 0 and control_cnt > 0:
                                mean_val = exp_cnt * (n_current + 1) / 2
                                std_val = np.sqrt(exp_cnt * control_cnt * (n_current + 1) / 12)
                            else:
                                mean_val = 0
                                std_val = 0
                            
                            iter_data.append({
                                "Опция": option,
                                "z-статистика": f"{z_val:.4f}",
                                "p-значение": f"{p_val:.2f}",
                                "Среднее": f"{mean_val:.2f}",
                                "Ст. отклонение": f"{std_val:.2f}",
                                "Статус": status
                            })
                    
                    if iter_data:
                        df_iter = pd.DataFrame(iter_data)
                        df_iter.index = range(1, len(df_iter) + 1)
                        styled_iter = df_iter.style.applymap(color_status, subset=["Статус"] ) 
                        st.dataframe(styled_iter, width='stretch')

            st.divider()

            improvements = opt_result.get("optimal_options", [])
            regressions = opt_result.get("regression_options", [])

            if improvements:
                st.success(
                    f"Опции, дающие улучшение по критерию: {', '.join(improvements)}"
                )

            if regressions:
                st.error(
                    f"Опции, дающие ухудшение по критерию: {', '.join(regressions)}"
                )


# -------------------------------------------------
# СВОДНАЯ ТАБЛИЦА ВСЕХ РЕЗУЛЬТАТОВ
# -------------------------------------------------

st.markdown("---")
st.subheader("Сводная таблица всех результатов")

summary_data = []
for crit, opt_result in optimization_results.items():
    if "error" not in opt_result:
        iterations_data = opt_result.get("iterations", [])
        methods_used = opt_result.get("methods_used", {})
        optimal_flags_set = set(opt_result.get("optimal_options", []))
        rank_type_crit = opt_result.get("rank_type", "descending")
        
        for flag in flags:
            if flag in opt_result.get("p_values", {}):
                z_val = opt_result["z_values"][flag]
                u_val = opt_result["u_values"].get(flag, 0.0)
                p_val = opt_result["p_values"][flag]
                method = methods_used.get(flag, "z_test")
            else:
                z_val = 0.0
                u_val = 0.0
                p_val = 1.0
                method = "none"
            
            is_significant = p_val <= confidence_level
            
            if is_significant:
                if method == "u_test":
                    exp_cnt = 0
                    control_cnt = 0
                    for iter_info in iterations_data:
                        if flag in iter_info["options"]:
                            idx_flag = iter_info["options"].index(flag)
                            if idx_flag < len(iter_info["exp_count"]):
                                exp_cnt = iter_info["exp_count"][idx_flag]
                                control_cnt = iter_info["n_combinations"] - exp_cnt
                                break
                    
                    max_u = exp_cnt * control_cnt if exp_cnt > 0 and control_cnt > 0 else 1
                    
                    if (u_val <= 0.05 * max_u and rank_type_crit == "ascending") or \
                       (u_val >= 0.95 * max_u and rank_type_crit == "descending"):
                        status = "Улучшение"
                    else:
                        status = "Ухудшение"
                else:
                    if (z_val > 0 and rank_type_crit == "descending") or \
                       (z_val < 0 and rank_type_crit == "ascending"):
                        status = "Улучшение"
                    else:
                        status = "Ухудшение"
            else:
                status = "Нет эффекта"
        
            
            if method == "u_test":
                summary_data.append({
                    "Критерий": crit,
                    "Тип": "Максимизация" if rank_type_crit == "descending" else "Минимизация",
                    "Флаг": flag,
                    "U-статистика": f"{u_val:.0f}",
                    "p-значение": f"{p_val:.2f}",
                    "Статус": status,
                })
            else:
                summary_data.append({
                    "Критерий": crit,
                    "Тип": "Максимизация" if rank_type_crit == "descending" else "Минимизация",
                    "Флаг": flag,
                    "z-статистика": f"{z_val:.4f}",
                    "p-значение": f"{p_val:.2f}",
                    "Статус": status,
                })

if summary_data:
    df_summary = pd.DataFrame(summary_data)
    col1, col2 = st.columns(2)
    with col1:
        filter_crit = st.selectbox(
            "Фильтр по критерию:",
            ["Все"] + sorted(df_summary["Критерий"].unique())
        )
    with col2:
        filter_status = st.selectbox(
            "Фильтр по статусу:",
            ["Все", "Улучшение", "Ухудшение", "Нет эффекта"]
        )
    
    filtered_df = df_summary.copy()
    
    if filter_crit != "Все":
        filtered_df = filtered_df[filtered_df["Критерий"] == filter_crit]
    if filter_status != "Все":
        filtered_df = filtered_df[filtered_df["Статус"] == filter_status]

    filtered_df.index = range(1, len(filtered_df) + 1)
    styled_summary = filtered_df.style.applymap(color_status, subset=["Статус"])
    st.dataframe(styled_summary, use_container_width=True, height=500)

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
    - **p-значение:** вероятность случайного возникновения эффекта (p <= {confidence_level} = статистически значимо)
    - **Среднее:** ожидаемое значение суммы рангов для группы
    - **Ст. отклонение:** мера разброса экспериментальных данных
    
    **Интерпретация:**
    - **Улучшение:** флаг положительно влияет на критерий
    - **Ухудшение:** флаг отрицательно влияет на критерий
    - **Нет эффекта:** влияние флага статистически незначимо
    
    **Параметры анализа:**
    - Уровень значимости α = {confidence_level}
    - Тип ранжирования: {rank_type}
    """)

    
# -------------------------------------------------
# МНОГОКРИТЕРИАЛЬНЫЙ АНАЛИЗ
# -------------------------------------------------

if len(optimization_results) >= 2:
    st.markdown("---")
    st.subheader("Многокритериальный анализ")
    
    criteria_list = list(optimization_results.keys())
    
    with st.expander("Корреляционная таблица по критериям"):
        corr_data = {}
        for crit in criteria_list:
            if "error" not in optimization_results[crit]:
                if isinstance(raw_results[crit], dict):
                    corr_data[crit] = list(raw_results[crit].values())
                elif isinstance(raw_results[crit], np.ndarray):
                    corr_data[crit] = raw_results[crit]
        
        if len(corr_data) >= 2:
            df_corr = pd.DataFrame(corr_data)
            correlation_matrix = df_corr.corr()
            
            fig_corr = px.imshow(
                correlation_matrix,
                text_auto=".2f",
                aspect="auto",
                color_continuous_scale="RdBu",
                title="Корреляционная матрица критериев"
            )
            st.plotly_chart(fig_corr, use_container_width=True)
            
            st.write("Числовые значения корреляции:")
            st.dataframe(correlation_matrix.style.format("{:.3f}"), width='stretch')
        else:
            st.info("Недостаточно данных для построения корреляционной матрицы")
    
    with st.expander("Вариационные ряды по критериям"):
        if len(criteria_list) >= 2:
            selected_criteria = st.multiselect(
                "Выберите критерии для анализа:",
                criteria_list,
                default=criteria_list[:min(3, len(criteria_list))]
            )
            
            if len(selected_criteria) >= 2:
                var_data = {}
                for crit in selected_criteria:
                    if "error" not in optimization_results[crit]:
                        if isinstance(raw_results[crit], dict):
                            values = list(raw_results[crit].values())
                        elif isinstance(raw_results[crit], np.ndarray):
                            values = raw_results[crit]
                        else:
                            continue
                        
                        var_data[crit] = np.sort(values)
                
                if len(var_data) >= 2:
                    min_len = min(len(v) for v in var_data.values())
                    normalized_data = {k: v[:min_len] for k, v in var_data.items()}
                    
                    fig_var = go.Figure()
                    
                    for crit_name, values in normalized_data.items():
                        fig_var.add_trace(go.Scatter(
                            x=list(range(1, len(values) + 1)),
                            y=values,
                            mode='lines+markers',
                            name=crit_name,
                            marker=dict(size=6)
                        ))
                    
                    fig_var.update_layout(
                        title="Вариационные ряды критериев",
                        xaxis_title="Порядковый номер",
                        yaxis_title="Значение",
                        height=500
                    )
                    
                    st.plotly_chart(fig_var, use_container_width=True)
                    
                    stats_data = []
                    for crit_name, values in normalized_data.items():
                        stats_data.append({
                            "Критерий": crit_name,
                            "Минимум": f"{np.min(values):.3f}",
                            "Максимум": f"{np.max(values):.3f}",
                            "Среднее": f"{np.mean(values):.3f}",
                            "Медиана": f"{np.median(values):.3f}",
                            "Ст. отклонение": f"{np.std(values):.3f}",
                            "Размах": f"{np.max(values) - np.min(values):.3f}"
                        })
                    
                    if stats_data:
                        df_stats = pd.DataFrame(stats_data)
                        df_stats.index = range(1, len(df_stats) + 1)
                        st.dataframe(df_stats, width='stretch')


st.markdown("---")
st.subheader("Дерево решений для многокритериальной оптимизации")

if len(optimization_results) >= 1:
    
    decision_tree_data = {}

    for crit, opt_result in optimization_results.items():
        if "error" not in opt_result:
            significant_flags = opt_result.get("significant_options", [])
            
            if not significant_flags:
                for removed in opt_result.get("removed_options", []):
                    if removed["p_value"] < confidence_level:
                        significant_flags.append(removed["option"])
            
            decision_tree_data[crit] = {
                "z_values": opt_result.get("z_values", {}),
                "u_values": opt_result.get("u_values", {}),
                "p_values": opt_result.get("p_values", {}),
                "methods_used": opt_result.get("methods_used", {}),
                "effect_types": opt_result.get("effect_types", {}),
                "rank_type": opt_result.get("rank_type", "descending"),
                "alpha": confidence_level,
                "significant_options": list(set(significant_flags)),
                "optimal_options": opt_result.get("optimal_options", []),
                "regression_options": opt_result.get("regression_options", [])
            }

    st.session_state.decision_tree_data = decision_tree_data

    if len(decision_tree_data) >= 1:
        if 'decision_tree_data' in st.session_state:
            decision_tree_data = st.session_state.decision_tree_data
            with st.spinner("Построение дерева решений..."):
                try:
                    tree_builder = DecisionTreeBuilder(decision_tree_data)
                    tree = tree_builder.build()
                    
                    optimal_options = tree_builder.get_optimal_options()
                    tree_stats = tree_builder.get_statistics()
                    
                    
                    st.write("#### Пошаговая фильтрация опций")
                    
                    all_flags_set = set()
                    for crit_data in decision_tree_data.values():
                        all_flags_set.update(crit_data.get("significant_options", []))
                    all_flags = sorted(list(all_flags_set))
                    
                    table_data = []
                    
                    current = tree
                    level_num = 1
                    
                    while current.children:
                        criterion = list(current.children.keys())[0]
                        node = current.children[criterion]
                        
                        rank_type_crit = decision_tree_data.get(criterion, {}).get("rank_type", "descending")
                        direction_text = "максимизация" if rank_type_crit == "descending" else "минимизация"
                        
                        row = {
                            "Уровень": level_num,
                            "Критерий": f"{criterion} ({direction_text})"
                        }
                        
                        for flag in all_flags:
                            if flag in node.filtered_options: 
                                if tree_builder._is_improvement(criterion, flag): 
                                    row[flag] = "Улучшение" 
                                else: row[flag] = "Без эффекта" 
                            else: 
                                if tree_builder._is_regression(criterion, flag): row[flag] = "Ухудшение" 
                                else: row[flag] = "Исключена"
                        
                        table_data.append(row)
                        current = node
                        level_num += 1
                    
                    final_row = {
                        "Уровень": "Итог",
                        "Критерий": f"Оптимальные опции ({len(optimal_options)})"
                    }
                    for flag in all_flags:
                        if flag in optimal_options:
                            final_row[flag] = "Оптимальная"
                        else:
                            final_row[flag] = "Не выбрана"
                    table_data.append(final_row)
                    
                    df_tree = pd.DataFrame(table_data)
                    df_tree.index = range(1, len(df_tree) + 1)
                    
                    styled_tree = df_tree.style.applymap(color_status)
                    st.dataframe(styled_tree, use_container_width=True)
                    
                    total_initial = len(all_flags)
                    total_final = len(optimal_options)
                    total_removed = total_initial - total_final
                    removed_percent = (total_removed / total_initial * 100) if total_initial > 0 else 0
                    
                    st.info(f"**Общий результат фильтрации:** Исключено {total_removed} из {total_initial} опций ({removed_percent:.1f}%)")
                    
                    st.divider()
                    st.write("**Итоговое решение:**")
                    if optimal_options:
                        st.success(f"Оптимальные опции: {', '.join(optimal_options)}")
                    else:
                        st.info("Не найдено опций, удовлетворяющих всем критериям")
                    
                    st.session_state.decision_tree_results = {
                        "optimal_options": optimal_options,
                        "statistics": tree_stats
                    }
                    
                except Exception as e:
                    st.error(f"Ошибка при построении дерева решений: {e}")
                    st.info("Для построения дерева решений необходимо иметь результаты анализа хотя бы для одного критерия")
    else:
        st.info("Недостаточно данных для построения дерева решений")
else:
    st.info("Дерево решений доступно при наличии хотя бы одного критерия")


# -------------------------------------------------
# Экспорт результатов
# -------------------------------------------------

if st.button("Экспортировать результаты", type="secondary"):
    export_data = {
        "analysis_results": optimization_results,
        "decision_tree": st.session_state.get("decision_tree_results", {})
    }
    
    import json
    import datetime
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"optimization_results_{timestamp}.json"
    
    def serialize(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, set):
            return list(obj)
        return str(obj)
    
    json_str = json.dumps(export_data, default=serialize, indent=2, ensure_ascii=False)
    
    st.download_button(
        label="Скачать результаты (JSON)",
        data=json_str,
        file_name=filename,
        mime="application/json"
    )