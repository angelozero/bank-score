from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

PROMPT_TEMPLATE = """
Responda a pergunta baseada apenas no seguinte contexto:
{context}

---

Responda a pergunta baseada apenas no seguinte contexto:
{question}
"""

def generate_prompt(context_text, query):
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    return prompt_template.format(context=context_text, question=query)