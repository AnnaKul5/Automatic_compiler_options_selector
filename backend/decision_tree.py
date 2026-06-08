import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum


class DecisionNodeType(Enum):
    """Тип узла дерева решений"""
    ROOT = "root"
    CRITERION = "criterion"
    LEAF = "leaf"


@dataclass
class DecisionNode:
    """Узел дерева решений"""
    node_type: DecisionNodeType
    criterion: str = None
    criterion_index: int = None
    children: Dict[str, 'DecisionNode'] = field(default_factory=dict)
    allowed_options: List[str] = None
    filtered_options: List[str] = None
    level: int = 0
    parent: 'DecisionNode' = None


@dataclass
class DecisionPath:
    """Путь в дереве решений"""
    criteria: List[str]
    decisions: List[str]
    final_options: List[str]


class DecisionTreeBuilder:
    """
    Построитель дерева решений для многокритериальной оптимизации
    
    Дерево строится на основе результатов статистического анализа:
    - На каждом уровне проверяется влияние опции на очередной критерий
    - Опции, дающие отрицательное влияние, исключаются
    - Опции, дающие положительное влияние, сохраняются
    - Опции без статистически значимого влияния сохраняются
    """
    
    def __init__(self, criteria_results: Dict[str, Dict], alpha: float = 0.05):
        """
        Инициализация построителя дерева
        
        Parameters:
        -----------
        criteria_results : Dict[str, Dict]
            Результаты анализа для каждого критерия
            Структура: {
                "критерий1": {
                    "z_values": {флаг: z},
                    "p_values": {флаг: p},
                    "rank_type": "ascending"/"descending",
                    "alpha": float
                },
                ...
            }
        alpha : float
            Глобальный уровень значимости (используется если не указан для критерия)
        """
        self.criteria_results = criteria_results
        self.default_alpha = alpha
        self.criteria_list = list(criteria_results.keys())
        self.tree = None
        self.significant_options = self._get_significant_options()
        
    def _get_significant_options(self) -> Set[str]:
        significant = set()
        for criterion, results in self.criteria_results.items():
            if "significant_options" in results:
                for option in results["significant_options"]:
                    significant.add(option)
        return significant
    
    def _is_improvement(self, criterion: str, option: str) -> bool: 
        results = self.criteria_results.get(criterion, {}) 
        effect_types = results.get("effect_types", {}) 
        return effect_types.get(option) == "improvement"
    
    def _is_regression(self, criterion: str, option: str) -> bool: 
        results = self.criteria_results.get(criterion, {}) 
        effect_types = results.get("effect_types", {}) 
        return effect_types.get(option) == "regression"
    
    def build(self) -> DecisionNode:
        """
        Построение дерева решений
        
        Returns:
        --------
        DecisionNode
            Корневой узел дерева решений
        """
        # Начальное множество опций - прошедшие статистический отбор
        initial_options = sorted(list(self.significant_options))
        
        # Создаем корневой узел
        root = DecisionNode(
            node_type=DecisionNodeType.ROOT,
            allowed_options=initial_options,
            filtered_options=initial_options.copy(),
            level=0
        )
        
        current_level = 1
        
        # Рекурсивно строим дерево для каждого критерия
        self._build_level(root, 0, current_level)
        
        self.tree = root
        return root
    
    def _build_level(self, node: DecisionNode, criterion_idx: int, level: int):
        """
        Рекурсивное построение уровня дерева для очередного критерия
        
        Parameters:
        -----------
        node : DecisionNode
            Текущий узел
        criterion_idx : int
            Индекс текущего критерия
        level : int
            Текущий уровень глубины
        """
        if criterion_idx >= len(self.criteria_list):
            # Достигнут лист дерева
            node.node_type = DecisionNodeType.LEAF
            return
        
        criterion = self.criteria_list[criterion_idx]
        
        # Создаем узел критерия
        criterion_node = DecisionNode(
            node_type=DecisionNodeType.CRITERION,
            criterion=criterion,
            criterion_index=criterion_idx,
            level=level,
            parent=node
        )
        
        # Анализируем каждую опцию
        positive_options = []  # Опции с положительным влиянием
        neutral_options = []   # Опции без значимого влияния
        negative_options = []  # Опции с отрицательным влиянием (будут исключены)
        
        for option in node.filtered_options:
            if self._is_improvement(criterion, option):
                positive_options.append(option)
            elif self._is_regression(criterion, option):
                negative_options.append(option)
            else:
                neutral_options.append(option)
        
        # Опции, прошедшие фильтрацию на этом уровне:
        # положительные + нейтральные
        passed_options = sorted(positive_options + neutral_options)
        
        # Сохраняем информацию в узле
        criterion_node.allowed_options = passed_options
        criterion_node.filtered_options = passed_options
        
        # Добавляем дочерние узлы
        node.children[criterion] = criterion_node
        
        # Рекурсивно строим следующий уровень
        self._build_level(criterion_node, criterion_idx + 1, level + 1)
    
    def get_optimal_options(self) -> List[str]:
        """
        Получение оптимальных опций на основе дерева решений
        
        Returns:
        --------
        List[str]
            Список оптимальных опций
        """
        if self.tree is None:
            self.build()
        
        # Проходим по дереву до листа
        current = self.tree
        while current.children:
            # Берем первого потомка (всегда один путь, так как фильтрация последовательная)
            next_node = list(current.children.values())[0]
            current = next_node
        
        return current.filtered_options if current.filtered_options else []
    
    def get_decision_path(self) -> DecisionPath:
        """
        Получение пути принятия решений
        
        Returns:
        --------
        DecisionPath
            Объект с информацией о пути в дереве
        """
        if self.tree is None:
            self.build()
        
        criteria = []
        decisions = []
        
        current = self.tree
        while current.children:
            criterion = list(current.children.keys())[0]
            node = current.children[criterion]
            
            criteria.append(criterion)
            
            # Формируем описание решения
            kept = len(node.filtered_options) if node.filtered_options else 0
            total = len(current.filtered_options) if current.filtered_options else 0
            
            if total > 0:
                kept_percent = (kept / total) * 100
                decisions.append(f"Оставлено {kept} из {total} опций ({kept_percent:.1f}%)")
            else:
                decisions.append("Нет опций, прошедших фильтрацию")
            
            current = node
        
        return DecisionPath(
            criteria=criteria,
            decisions=decisions,
            final_options=current.filtered_options if current.filtered_options else []
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по дереву решений
        
        Returns:
        --------
        Dict[str, Any]
            Статистика дерева
        """
        if self.tree is None:
            self.build()
        
        stats = {
            "total_criteria": len(self.criteria_list),
            "significant_options": len(self.significant_options),
            "optimal_options": len(self.get_optimal_options()),
            "criteria_processed": []
        }
        
        current = self.tree
        level = 0
        
        while current.children:
            criterion = list(current.children.keys())[0]
            node = current.children[criterion]
            
            total = len(current.filtered_options) if current.filtered_options else 0
            kept = len(node.filtered_options) if node.filtered_options else 0
            
            stats["criteria_processed"].append({
                "level": level + 1,
                "criterion": criterion,
                "options_before": total,
                "options_after": kept,
                "removed": total - kept,
                "removed_percent": ((total - kept) / total * 100) if total > 0 else 0
            })
            
            current = node
            level += 1
        
        return stats