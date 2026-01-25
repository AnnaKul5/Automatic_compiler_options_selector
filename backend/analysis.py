import numpy as np
import math
from scipy.stats import norm
import streamlit as st
import numpy as np
from allpairspy import AllPairs

def generate_binary_values(options):
    binary_values = [[0, 1] for _ in options]
    return binary_values


def generate_sets_of_options(options, combinations):
    sets = []

    for combination in combinations:
        current_string = ""
        for idx, value in enumerate(combination):
            if value == 1:
                current_string += options[idx] + " "

        sets.append(current_string)

    return sets

def generate_orthogonal_array(options: list[str]):
    """
    Генерирует ортогональный массив (бинарную матрицу) и соответствующие наборы опций
    """
    binary_values = generate_binary_values(options)
    combinations = list(AllPairs(binary_values))
    binary_matrix = np.array(combinations)
    option_sets = generate_sets_of_options(options, combinations)
    
    return binary_matrix, option_sets


def _normalize_scores(scores):
    scores = np.atleast_1d(scores)

    clean = []
    for x in scores:
        if x is None:
            clean.append(np.nan)
            continue

        if isinstance(x, dict):
            raise TypeError(
                "Получен dict вместо массива чисел. "
                "Для нескольких критериев используйте multi-функцию."
            )

        if isinstance(x, str):
            x = x.strip().replace(",", ".")
            if x == "":
                clean.append(np.nan)
                continue

        try:
            clean.append(float(x))
        except Exception:
            clean.append(np.nan)

    return np.array(clean, dtype=float)


def get_rank_in_ascending(array):
    sorted_indices = np.argsort(array)
    ranks = np.zeros(len(array), dtype=int)

    for rank, index in enumerate(sorted_indices):
        ranks[index] = rank + 1

    return ranks


def get_rank_in_descending(array):
    sorted_indices = np.argsort(array)[::-1]
    ranks = np.zeros(len(array), dtype=int)

    for rank, index in enumerate(sorted_indices):
        ranks[index] = rank + 1

    return ranks


def get_k(combinations, ranks):
    n = combinations.shape[1]
    result = np.zeros(n, dtype=int)
    for combination_idx, combination in enumerate(combinations):
        for idx, value in enumerate(combination):
            result[idx] += value * ranks[combination_idx]
    return result


def experimental_group_count(combinations):
    n = combinations.shape[1]
    result = np.zeros(n, dtype=int)
    for combination_idx, combination in enumerate(combinations):
        for idx, value in enumerate(combination):
            if value != 0:
                result[idx] += 1
    return result


def find_optimal_options_iterative(
    combinations: np.ndarray,
    scores,
    options: np.ndarray,
    rank_type="descending",
    alpha=0.05
):
    print(scores)
    scores = _normalize_scores(scores)

    # синхронная фильтрация
    mask = ~np.isnan(scores)
    scores = scores[mask]
    combinations = combinations[mask]

    n = len(scores)
    num_options = combinations.shape[1]

    if n == 0:
        raise ValueError("Нет валидных значений score")
    
    current_combinations = combinations.copy()
    current_scores = scores.copy()
    current_options = options.copy()

    iterations = []
    removed_options = []
    
    iteration_num = 0
    
    while True:
        iteration_num += 1
        
        n_current = len(current_scores)
        n_options_current = len(current_options)
        
        if n_options_current == 0:
            break

        if rank_type == "descending":
            ranks = get_rank_in_descending(current_scores)
        else:
            ranks = get_rank_in_ascending(current_scores)


        k = get_k(current_combinations, ranks)
        exp_count = experimental_group_count(current_combinations)
        
        #print(f"k: {k}")
        #print('\n')
        # Массивы для результатов
        p_vals = np.zeros(n_options_current)
        z_vals = np.zeros(n_options_current)
        
        # Вычисляем p-значения (cdf_values в оригинале)
        for i in range(n_options_current):
            control = n_current - exp_count[i]
            if exp_count[i] == 0 or control == 0:
                p_vals[i] = 1.0
                continue
                
            mean = exp_count[i] * (n_current + 1) / 2
            std = math.sqrt(exp_count[i] * control * (n_current + 1) / 12)
            
            z = (k[i] - mean) / std
            p = 2 * (1 - norm.cdf(abs(z)))
            
            p_vals[i] = p
            z_vals[i] = z

        # Сохраняем состояние итерации
        iteration_info = {
            "iteration": iteration_num,
            "options": current_options.copy(),
            "p_values": p_vals.copy(),
            "z_values": z_vals.copy(),
            "n_combinations": n_current,
            "exp_count": exp_count.copy()
        }
        iterations.append(iteration_info)
        
        # Считаем незначимые опции на текущей итерации (как в оригинале)
        count_of_minor_opt = 0
        new_count_of_options = n_options_current
        
        # Обрабатываем опции по порядку
        i = 0
        options_processed = False
        
        while i < new_count_of_options:
            if p_vals[i] >= alpha:
                # Незначимая опция - пропускаем (как в оригинале)
                count_of_minor_opt += 1
                i += 1
                continue
            
            # Значимая опция
            options_processed = True
            
            if (z_vals[i] > 0 and rank_type == "descending") or \
               (z_vals[i] < 0 and rank_type == "ascending"):
                # Это плохая опция (регрессия) - target_value = 0
                target_value = 0
                reason = "regression"
            else:
                # Это хорошая опция (улучшение) - target_value = 1
                target_value = 1
                reason = "improvement"
            
            # Сохраняем информацию об удаляемой опции
            removed_options.append({
                "option": current_options[i],
                "iteration": iteration_num,
                "reason": reason,
                "p_value": p_vals[i],
                "z_value": z_vals[i]
            })
            
            # Фильтруем комбинации как в оригинале
            j = 0
            while j < n_current:
                if current_combinations[j, i] != target_value:
                    # Удаляем строку
                    current_combinations = np.delete(current_combinations, j, axis=0)
                    current_scores = np.delete(current_scores, j, axis=0)
                    n_current -= 1
                else:
                    j += 1
            
            # Удаляем столбец опции
            current_combinations = np.delete(current_combinations, i, axis=1)
            current_options = np.delete(current_options, i)
            
            # Обновляем размерности
            new_count_of_options -= 1
            n_options_current = new_count_of_options
            
            # Выходим из цикла (только одна опция за итерацию)
            break
        
        # Условие завершения как в оригинале
        if n_options_current == 0 or count_of_minor_opt == n_options_current:
            break
    
    # Формируем итоговый результат
    result = {
        "optimal_options": current_options.tolist(),
        "final_scores": current_scores.tolist(),
        "final_combinations": current_combinations.tolist(),
        "iterations": iterations,
        "removed_options": removed_options,
        "alpha": alpha,
        "rank_type": rank_type,
        "initial_options": options.tolist(),
        "initial_n": n,
        "final_n": len(current_scores)
    }
    
    # Добавляем z_values и p_values для ВСЕХ исходных опций
    # (нужно для отображения в аналитике)
    all_z_values = {}
    all_p_values = {}
    
    # Восстанавливаем итоговые значения для всех исходных опций
    for opt in options:
        # Если опция осталась в оптимальных
        if opt in current_options:
            idx = list(current_options).index(opt)
            all_z_values[opt] = z_vals[idx] if idx < len(z_vals) else 0
            all_p_values[opt] = p_vals[idx] if idx < len(p_vals) else 1.0
        else:
            # Ищем в истории удалений
            found = False
            for removed in removed_options:
                if removed["option"] == opt:
                    all_z_values[opt] = removed["z_value"]
                    all_p_values[opt] = removed["p_value"]
                    found = True
                    break
            if not found:
                all_z_values[opt] = 0
                all_p_values[opt] = 1.0
    
    result["z_values"] = all_z_values
    result["p_values"] = all_p_values
    
    return result


def find_optimal_options_multi(
    combinations: np.ndarray,
    criteria_scores: dict,
    options: np.ndarray,
    rank_type="descending"
):
    results = {}

    for criterion, scores in criteria_scores.items():
        results[criterion] = find_optimal_options_iterative(
            combinations=combinations.copy(),
            scores=scores,
            options=options.copy(),
            rank_type=rank_type,
        )

    return results