from langgraph.graph import StateGraph, START, END
from backend.agents.state import DigestState
from backend.agents.nodes import (
    fetch_data_node,
    pattern_lookup_node,
    classify_node,
    respond_node,
    generate_tip_node,
    save_results_node,
    has_signal_reports,
)


def build_digest_graph() -> StateGraph:
    graph = StateGraph(DigestState)


    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("pattern_lookup", pattern_lookup_node)
    graph.add_node("classify", classify_node)
    graph.add_node("respond", respond_node)
    graph.add_node("generate_tip", generate_tip_node)
    graph.add_node("save_results", save_results_node)

    graph.add_edge(START, "fetch_data")
    graph.add_edge("fetch_data", "pattern_lookup")
    graph.add_edge("pattern_lookup", "classify")

    graph.add_conditional_edges(
        "classify",
        has_signal_reports,
        {True: "respond", False: "generate_tip"},
    )

    graph.add_edge("respond", "generate_tip")
    graph.add_edge("generate_tip", "save_results")
    graph.add_edge("save_results", END)

    return graph.compile()

digest_pipeline = build_digest_graph()
