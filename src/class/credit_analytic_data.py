from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

class CreditAnalyticData(BaseModel):
    score: float = Field(description="Score numérico do cliente")
    faixa: str = Field(description="Faixa de score (A, B, ou C)")
    padrao_extraido: str = Field(description="O padrão identificado (Diamante, Ouro, etc)")
    has_impediment: bool = Field(description="Se há fatores de impedimento no Item 3")
    geographic_risk: bool = Field(description="Se o CPF cai nas regras de restrição regional")