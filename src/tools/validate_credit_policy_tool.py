# import tavily
from langchain.tools import tool

# Pesquisa usando a internet com tavily
# @tool
# def search(query: str) -> str:
#     """
#     Search the internet. USE THIS TOOL TO GET DATA.
#     After receiving the results, provide the final answer to the user immediately.
#     """
#     print(f"\nSearching for '{query}'")
#     return tavily.search(query=query)

@tool
def validate_credit_policy(score: float, regional_risk: bool, has_impediment: bool) -> str:
    """
    Verifica tecnicamente se os dados extraídos violam a política do Banco.
    """
    if has_impediment:
        return "BLOQUEIO: Identificado impedimento direto no Item 3."
    
    if regional_risk and score < 800:
        return "RISCO: Score insuficiente para a região (Geographic Override)."
    
    return "CONSERVADOR: Cliente atende todos os requisitos de segurança."