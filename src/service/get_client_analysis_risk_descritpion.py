from src.service.get_chat_model import get_chat_model
from langchain_core.prompts import ChatPromptTemplate

PROMPT_TEMPLATE = """
                        Responda a pergunta baseada apenas no seguinte contexto:
                        {context}

                        ---

                        Responda a pergunta baseada apenas no seguinte contexto:
                        {question}
                        """


def get_client_analysis_risk_descritpion(context, query):
    print("[07] - Obtendo análise de risco do cliente...")

    model = get_chat_model()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context, question=query)
    reponse = model.invoke(prompt)
    return reponse.content
