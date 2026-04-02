import tavily
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """
    Search the internet. USE THIS TOOL TO GET DATA.
    After receiving the results, provide the final answer to the user immediately.
    """
    print(f"\nSearching for '{query}'")
    return tavily.search(query=query)