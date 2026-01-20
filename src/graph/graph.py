# src/graph/graph.py

from langgraph.graph import StateGraph, END
from src.graph.state import AnalystState
from src.graph.nodes.classify import classify_intent
from src.graph.nodes.describe import describe
from src.graph.nodes.diagnose import diagnose
from src.graph.nodes.prescribe import prescribe
from src.graph.nodes.synthesize import synthesize


def create_analyst_graph():
    """
    Создаёт граф Senior WB Analyst v1.0.

    Flow:
    - describe: classify → describe → synthesize
    - diagnose: classify → describe → diagnose → synthesize
    - prescribe: classify → describe → diagnose → prescribe → synthesize
    """

    # Создаём граф
    workflow = StateGraph(AnalystState)

    # Добавляем ноды
    workflow.add_node("classify", classify_intent)
    workflow.add_node("describe", describe)
    workflow.add_node("diagnose", diagnose)
    workflow.add_node("prescribe", prescribe)
    workflow.add_node("synthesize", synthesize)

    # Определяем entry point
    workflow.set_entry_point("classify")

    # Роутинг после classify — все идут в describe сначала
    workflow.add_edge("classify", "describe")

    # Роутинг после describe — зависит от intent
    def route_after_describe(state: AnalystState) -> str:
        """Роутинг после describe на основе intent."""
        intent = state.get("intent", "describe")

        if intent == "diagnose":
            return "diagnose"
        elif intent == "prescribe":
            return "diagnose"  # prescribe тоже сначала идёт в diagnose
        else:
            return "synthesize"

    workflow.add_conditional_edges(
        "describe",
        route_after_describe,
        {
            "diagnose": "diagnose",
            "synthesize": "synthesize"
        }
    )

    # Роутинг после diagnose — зависит от intent
    def route_after_diagnose(state: AnalystState) -> str:
        """Роутинг после diagnose."""
        intent = state.get("intent", "describe")

        if intent == "prescribe":
            return "prescribe"
        else:
            return "synthesize"

    workflow.add_conditional_edges(
        "diagnose",
        route_after_diagnose,
        {
            "prescribe": "prescribe",
            "synthesize": "synthesize"
        }
    )

    # После prescribe → synthesize
    workflow.add_edge("prescribe", "synthesize")

    # После synthesize → END
    workflow.add_edge("synthesize", END)

    # Компилируем
    return workflow.compile()


# Singleton графа
analyst_graph = create_analyst_graph()
