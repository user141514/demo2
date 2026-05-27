from typing import Callable, Optional
from .state import EvalState


class GraphRunner:
    def __init__(self):
        self._nodes: dict[str, Callable] = {}
        self._edges: dict[str, list[tuple[str, Optional[Callable]]]] = {}

    def add_node(self, name: str, fn: Callable[[EvalState], EvalState]) -> None:
        self._nodes[name] = fn

    def add_edge(self, from_node: str, to_node: str,
                 condition: Optional[Callable[[EvalState], bool]] = None) -> None:
        if from_node not in self._edges:
            self._edges[from_node] = []
        self._edges[from_node].append((to_node, condition))

    def run(self, state: EvalState, start_node: str = "validate_input") -> EvalState:
        current = start_node
        while current is not None:
            state._trace.append(current)
            if current not in self._nodes:
                break
            state = self._nodes[current](state)
            next_node = self._resolve_next(current, state)
            current = next_node
        return state

    def _resolve_next(self, from_node: str, state: EvalState) -> Optional[str]:
        edges = self._edges.get(from_node, [])
        for to_node, condition in edges:
            if condition is None or condition(state):
                return to_node
        return None
