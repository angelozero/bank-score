from langchain_core.messages import HumanMessage, SystemMessage

def get_credit_analysis_prompt(cpf, amount):
    return {
        "messages": [
            SystemMessage(
                content=(
                    "Você é um Analista de Risco de Crédito sênior do Banco Estudo S.A. "
                    "Sua função é utilizar a ferramenta de busca (RAG) para consultar a 'Política Interna de Concessão de Crédito'. "
                    "\n\nREGRAS DE EXECUÇÃO:\n"
                    "1. Use a ferramenta de busca APENAS UMA VEZ para extrair as regras de Score, Faixas de Valor e PII.\n"
                    "2. Sempre utilize o CPF MASCARADO (ex: 123.***.***-01) em suas respostas.\n"
                    "3. Ao finalizar a análise, sua resposta DEVE seguir este formato: \n"
                    "   - 'PARECER: [Aprovado / Negado / Encaminhado ao Gerente]'\n"
                    "   - 'MOTIVO: [Breve explicação baseada no documento]'\n"
                    "4. Se os dados necessários já estiverem no histórico, não use a ferramenta novamente."
                )
            ),
            HumanMessage(
                content=(
                    f"O cliente com CPF {cpf} solicitou um crédito de R$ {amount}. "
                    "Com base na nossa política de crédito, qual o procedimento correto para este caso?"
                )
            ),
        ]
    }
