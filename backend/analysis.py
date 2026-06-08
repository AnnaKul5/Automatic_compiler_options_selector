import numpy as np
import math
import streamlit as st
from allpairspy import AllPairs
from scipy.stats import norm, mannwhitneyu

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


def compute_mann_whitney_directional_tests(
    experimental_scores,
    control_scores,
    rank_type="descending"
):
    try:
        if rank_type == "descending":
            # больше = лучше
            improvement_alt = "greater"
            regression_alt = "less"

        else:
            # меньше = лучше
            improvement_alt = "less"
            regression_alt = "greater"

        improvement_result = mannwhitneyu(
            experimental_scores,
            control_scores,
            alternative=improvement_alt,
            method='exact'
        )

        regression_result = mannwhitneyu(
            experimental_scores,
            control_scores,
            alternative=regression_alt,
            method='exact'
        )

        return {
            "u_improvement": improvement_result.statistic,
            "p_improvement": improvement_result.pvalue,

            "u_regression": regression_result.statistic,
            "p_regression": regression_result.pvalue
        }

    except Exception:

        return {
            "u_improvement": 0.0,
            "p_improvement": 1.0,

            "u_regression": 0.0,
            "p_regression": 1.0
        }


def find_optimal_options_iterative(
    combinations: np.ndarray,
    scores,
    options: np.ndarray,
    rank_type="descending",
    alpha=0.05,
    small_sample_threshold=19
):

    scores = _normalize_scores(scores)
    mask = ~np.isnan(scores)
    scores = scores[mask]
    combinations = combinations[mask]

    n = len(scores)
    if n == 0:
        raise ValueError("Нет валидных значений score")

    current_combinations = combinations.copy()
    current_scores = scores.copy()
    current_options = options.copy()

    iterations = []
    removed_options = []
    iteration_num = 0

    final_z_values = {}
    final_u_values = {}
    final_p_values = {}
    final_method_used = {}
    final_effect_types = {}

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

        p_vals = np.zeros(n_options_current)
        z_vals = np.zeros(n_options_current)
        u_vals = np.zeros(n_options_current)

        effect_types = []
        method_used = []

        for i in range(n_options_current):
            control = n_current - exp_count[i]
            use_u_test = (
                exp_count[i] < small_sample_threshold
                and control < small_sample_threshold
            )

            if use_u_test:
                exp_scores = []
                control_scores = []

                for j in range(n_current):
                    if current_combinations[j][i] == 1:
                        exp_scores.append(current_scores[j])
                    else:
                        control_scores.append(current_scores[j])

                test_result = compute_mann_whitney_directional_tests(
                    exp_scores,
                    control_scores,
                    rank_type
                )

                u_improvement = test_result["u_improvement"]
                p_improvement = test_result["p_improvement"]

                u_regression = test_result["u_regression"]
                p_regression = test_result["p_regression"]

                if p_improvement <= alpha:
                    effect = "improvement"
                    p_val = p_improvement
                    u_val = u_improvement

                elif p_regression <= alpha:
                    effect = "regression"
                    p_val = p_regression
                    u_val = u_regression

                else:
                    effect = "none"
                    p_val = min(p_improvement, p_regression)
                    u_val = u_improvement

                p_vals[i] = p_val
                u_vals[i] = u_val
                z_vals[i] = 0.0
                effect_types.append(effect)
                method_used.append("u_test")

            else:

                mean = exp_count[i] * (n_current + 1) / 2
                std = math.sqrt(exp_count[i] * control * (n_current + 1) / 12)
                if std > 0:
                    z = (k[i] - mean) / std
                else:
                    z = 0.0

                p = 2 * (1 - norm.cdf(abs(z)))
                p_vals[i] = p
                z_vals[i] = z
                u_vals[i] = 0.0

                if p <= alpha:
                    if ((z > 0 and rank_type == "descending") or (z < 0 and rank_type == "ascending")):
                        effect = "improvement"
                    else:
                        effect = "regression"
                else:
                    effect = "none"

                effect_types.append(effect)
                method_used.append("z_test")

        iteration_info = {
            "iteration": iteration_num,
            "options": current_options.copy().tolist(),
            "p_values": p_vals.copy().tolist(),
            "u_values": u_vals.copy().tolist(),
            "z_values": z_vals.copy().tolist(),
            "methods_used": method_used.copy(),
            "effect_types": effect_types.copy(),
            "n_combinations": n_current,
            "exp_count": exp_count.copy().tolist()
        }

        iterations.append(iteration_info)

        for idx, opt in enumerate(current_options):
            final_z_values[opt] = float(z_vals[idx])
            final_u_values[opt] = float(u_vals[idx])
            final_p_values[opt] = float(p_vals[idx])
            final_method_used[opt] = method_used[idx]
            final_effect_types[opt] = effect_types[idx]

        options_removed_this_iteration = False
        for i in range(n_options_current):
            if p_vals[i] > alpha:
                continue

            options_removed_this_iteration = True
            effect = effect_types[i]

            if effect == "improvement":
                target_value = 1
            elif effect == "regression":
                target_value = 0
            else:
                continue

            removed_options.append({
                "option": current_options[i],
                "iteration": iteration_num,
                "reason": effect,
                "p_value": float(p_vals[i]),
                "z_value": float(z_vals[i]),
                "u_value": float(u_vals[i]),
                "method_used": method_used[i],
                "exp_count": int(exp_count[i]),
                "control_count": int(n_current - exp_count[i])
            })

            rows_to_keep = current_combinations[:, i] == target_value
            current_combinations = current_combinations[rows_to_keep]
            current_scores = current_scores[rows_to_keep]
            current_combinations = np.delete(
                current_combinations,
                i,
                axis=1
            )

            current_options = np.delete(current_options, i)
            break

        if (not options_removed_this_iteration or len(current_options) == 0):
            break

    for opt in current_options:

        if opt not in final_z_values:
            final_z_values[opt] = 0.0
            final_u_values[opt] = 0.0
            final_p_values[opt] = 1.0
            final_method_used[opt] = "none"

    result = {
        "optimal_options": current_options.tolist(),
        "final_scores": current_scores.tolist(),
        "final_combinations": (
            current_combinations.tolist()
            if len(current_combinations) > 0
            else []
        ),
        "iterations": iterations,
        "removed_options": removed_options,
        "z_values": final_z_values,
        "u_values": final_u_values,
        "p_values": final_p_values,
        "methods_used": final_method_used,
        "effect_types": final_effect_types,
        "alpha": alpha,
        "rank_type": rank_type,
        "initial_options": options.tolist(),
        "initial_n": n,
        "final_n": len(current_scores)
    }
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