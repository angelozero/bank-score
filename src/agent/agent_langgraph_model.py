from typing import List
from pydantic import BaseModel, Field

class LangGraphSource(BaseModel):
    url: str = Field(description="URL da fonte consultada")
    title: str = Field(description="Título do documento ou página")
    relevance_score: float = Field(description="Score de relevância de 0 a 1")

class LangGraphAgentResponse(BaseModel):
    answer: str = Field(description="Resposta detalhada da auditoria de crédito")
    # Novos campos para o relatório
    client_cpf: str = Field(description="CPF do cliente (formato mascarado)")
    requested_amount: float = Field(description="Valor solicitado na auditoria")
    sources: List[LangGraphSource] = Field(default_factory=list, description="Fontes utilizadas no RAG")