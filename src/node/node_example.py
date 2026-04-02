from rich import print
from typing import Annotated, Literal, TypedDict
from langgraph.graph import END, START, StateGraph, add_messages
from dataclasses import dataclass


@dataclass
class StateConditional:
    nodes_path: Annotated[list[str], add_messages]
    current_number: int = 0


def node_a(state: StateConditional) -> StateConditional:
    print(f"\n>> node A custom state: {state}")
    state_conditional = StateConditional(
        nodes_path=["A"], current_number=state.current_number
    )
    return state_conditional


def node_b(state: StateConditional) -> StateConditional:
    print(f">> node B custom state: {state}")
    state_conditional = StateConditional(
        nodes_path=["B"], current_number=state.current_number
    )
    return state_conditional


def node_c(state: StateConditional) -> StateConditional:
    print(f">> node C custom state: {state}")
    state_conditional = StateConditional(
        nodes_path=["C"], current_number=state.current_number
    )
    return state_conditional


# ---- #


def conditional_function(state: StateConditional) -> Literal["B", "C"]:
    if state.current_number >= 50:
        return "goes_to_c"
    
    return "goes_to_b"


# ---- #

builder = StateGraph(StateConditional)

builder.add_node("A", node_a)
builder.add_node("B", node_b)
builder.add_node("C", node_c)

builder.add_edge(START, "A")
builder.add_conditional_edges("A", conditional_function, {
    "goes_to_b": "B",
    "goes_to_c": "C"
})
builder.add_edge("B", END)
builder.add_edge("C", END)

graph = builder.compile()

graph.get_graph().draw_mermaid_png(output_file_path='graph.png')

response = graph.invoke(StateConditional(nodes_path=[], current_number=51))
print()
print(response)
print()