import numpy as np

def pareto_front(points: dict):
    keys = list(points.keys())
    values = np.array(list(points.values()))

    is_pareto = np.ones(len(values), dtype=bool)

    for i, v in enumerate(values):
        if not is_pareto[i]:
            continue

        dominates = np.all(values >= v, axis=1) & np.any(values > v, axis=1)
        is_pareto[dominates] = False

    return [keys[i] for i in range(len(keys)) if is_pareto[i]]
