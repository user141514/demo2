from .core import GraphRunner
from .nodes import (
    assemble_result,
    build_response,
    compute_confidence,
    extract_pdf,
    human_review_gate,
    route_strategy,
    score_heuristic,
    score_llm,
    store_result,
    track_calibration,
    validate_input,
)
from .state import EvalState


def _is_live(state: EvalState) -> bool:
    return state.scoring_mode == "live"


def _is_heuristic(state: EvalState) -> bool:
    return state.scoring_mode == "heuristic"


def build_graph() -> GraphRunner:
    """Build the scoring pipeline graph with conditional routing."""
    g = GraphRunner()

    g.add_node("validate_input", validate_input)
    g.add_node("extract_pdf", extract_pdf)
    g.add_node("route_strategy", route_strategy)
    g.add_node("score_llm", score_llm)
    g.add_node("score_heuristic", score_heuristic)
    g.add_node("assemble_result", assemble_result)
    g.add_node("store_result", store_result)
    g.add_node("compute_confidence", compute_confidence)
    g.add_node("human_review_gate", human_review_gate)
    g.add_node("track_calibration", track_calibration)
    g.add_node("build_response", build_response)

    g.add_edge("validate_input", "extract_pdf")
    g.add_edge("extract_pdf", "route_strategy")
    g.add_edge("route_strategy", "score_llm", condition=_is_live)
    g.add_edge("route_strategy", "score_heuristic", condition=_is_heuristic)
    g.add_edge("score_llm", "compute_confidence")
    g.add_edge("score_heuristic", "compute_confidence")
    g.add_edge("compute_confidence", "human_review_gate")
    g.add_edge("human_review_gate", "assemble_result")
    g.add_edge("assemble_result", "store_result")
    g.add_edge("store_result", "track_calibration")
    g.add_edge("track_calibration", "build_response")

    return g


def execute_scoring_pipeline(initial_state: dict) -> dict:
    """Build and run the full scoring graph, returning the assembled result.

    Raises
    ------
    RuntimeError
        If the pipeline encountered a validation error, storage error, or
        completed without producing an assembled result.
    """
    state = EvalState(**initial_state)
    graph = build_graph()
    final = graph.run(state)

    if final.error:
        raise RuntimeError(final.error)
    if final.store_error:
        raise RuntimeError(final.store_error)
    if not final.assembled_result:
        raise RuntimeError("Pipeline completed without an assembled result.")

    return final.assembled_result
