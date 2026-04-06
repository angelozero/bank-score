# Sistema de Auditoria de Crédito 
|  |
| ------ |
| Python |
| FastAPI |
| LangChain |
| LangGraph |
| LangSmith |
| Ollama/Llama 3.2 (local) |
| ChromaDB |
| LiteLLM |
| Microsoft Presidio |
| Docker |
| Pydantic |

Uma aplicação que recebe uma solicitação de crédito (CPF + valor), busca trechos relevantes da política interna do banco, envia para uma IA local que analisa e classifica o risco, o CPF é mascarado automaticamente antes de chegar ao modelo, sem nenhuma linha de código Python para isso.

---

## Orquestração de fluxo

```
Usuário envia CPF + valor
        │
        ▼
API FastAPI recebe a solicitação
        │
        ▼
RAG busca trechos da política de crédito no ChromaDB
        │
        ▼
LLM (Llama 3.2) analisa e classifica o cliente
        │
        ▼
LangGraph decide: aprovação automática ou pausa para o gerente
        │
        ▼
Resposta JSON com relatório + CPF mascarado (XXX.***.***-XX)
```

O CPF `123.456.789-00` nunca chega ao modelo de IA. Ele é interceptado e substituído por `XXX.***.***-XX` na camada de infraestrutura.

---

## RAG — A IA responde com base em documentos reais

RAG (Retrieval-Augmented Generation) é a técnica que impede a IA de inventar respostas. Em vez de confiar no conhecimento genérico do modelo, a aplicação busca trechos reais da política de crédito e entrega como contexto.

O fluxo completo está no [`rag_service.py`](src/service/rag_service.py):

```python
def execute(cpf, amount):
    # 1. Monta a pergunta
    query = (
        f"Realize a auditoria de crédito para o valor de R$ {amount} "
        f"e CPF {cpf}. Verifique o enquadramento nas faixas de score, "
        "possíveis fatores de impedimento do Item 3 e regras de 'Geographic Override' do Item 7. "
        "Retorne o padrão do cliente e o relatório conforme o protocolo do Item 10."
    )

    # 2. Busca os 3 trechos mais relevantes da política no ChromaDB
    results = get_results_by_relevance_score(query)

    # 3. Junta os trechos em um texto de contexto
    context = get_context_by_results(results)

    # 4. Envia contexto + pergunta ao LLM → recebe análise de risco
    analysis_risk_description = get_client_analysis_risk_descritpion(context, query)

    # 5. Monta o prompt final de auditoria
    prompt = get_risk_analysis_prompt(cpf, amount, analysis_risk_description)

    # 6. Configura o LLM com ferramenta + resposta estruturada
    llm = get_llm_with_tools(validate_credit_policy)

    # 7. Envia e recebe a resposta final
    response = llm.invoke(prompt["messages"])
    return {"data": response}
```

### Como a busca funciona por baixo

O documento da política de crédito (PDF) foi previamente dividido em **chunks** de 2000 caracteres com sobreposição de 500. Cada chunk foi transformado em um vetor numérico (embedding) e armazenado no **ChromaDB**.

Quando chega uma pergunta, ela também vira um vetor. O ChromaDB compara os vetores e retorna os chunks mais parecidos semanticamente — não por palavras-chave, mas por significado.

```python
# src/service/generate_chunks_service.py — como os chunks são criados
spliter = RecursiveCharacterTextSplitter(
    chunk_size=2000, chunk_overlap=500, length_function=len, add_start_index=True
)
```

A sobreposição de 500 caracteres garante que frases na fronteira entre dois chunks não se percam.

### Ferramenta e resposta estruturada

O LLM não apenas gera texto — ele pode chamar uma ferramenta Python durante a análise:

```python
# src/tools/validate_credit_policy_tool.py
@tool
def validate_credit_policy(score: float, regional_risk: bool, has_impediment: bool) -> str:
    if has_impediment:
        return "BLOQUEIO: Identificado impedimento direto no Item 3."
    if regional_risk and score < 800:
        return "RISCO: Score insuficiente para a região (Geographic Override)."
    return "CONSERVADOR: Cliente atende todos os requisitos de segurança."
```

E a resposta é forçada a seguir um formato Pydantic — se a IA retornar algo fora do schema, é rejeitado:

```python
# src/agent/agent_langgraph_model.py
class LangGraphAgentResponse(BaseModel):
    answer: str
    client_cpf: str
    requested_amount: float
    sources: List[LangGraphSource]
```

---

## LangGraph — O fluxo não é linear, é um grafo

Em vez de um script que faz A → B → C, o fluxo é modelado como um **grafo de estado** onde cada etapa é um nó e as transições podem ser condicionais. Isso permite que o fluxo **pause para aprovação humana** e seja **retomado depois**.

O grafo completo está no [`state.py`](src/node/state.py):

```python
class CreditState(TypedDict):
    messages: Annotated[list[str], add_messages]
    cpf_original: str
    cpf_masked: str
    amount: float
    is_approved: bool
    analysis_report: str
    client_pattern: Literal["CONSERVADOR", "RISCO", "EXCECAO", "BLOQUEIO"]
```

Esse é o estado compartilhado. Todos os nós leem e escrevem nele.

### Os nós

```
START → [guardrails] → [analysis] → (condição) → [auto_approve] → END
                                         │
                                         └──────→ [manager_approval] ⏸ → END
```

- **guardrails** — prepara os dados de entrada
- **analysis** — chama o RAG completo e obtém o relatório da IA
- **auto_approve** — marca como aprovado automaticamente
- **manager_approval** — pausa para o gerente decidir

### O roteamento condicional

Após a análise, o grafo decide o caminho:

```python
def route_request(state: CreditState) -> Literal["to_manager", "to_auto_check"]:
    pattern = state.get("client_pattern")
    if pattern == "RISCO" or state["amount"] > 5000:
        return "to_manager"
    return "to_auto_check"
```

Valor acima de R$ 5.000 ou classificação RISCO → pausa para o gerente. Demais casos → aprovação automática.

### Checkpoint e Human-in-the-Loop

O grafo usa `MemorySaver` para salvar o estado a cada nó e `interrupt_before` para pausar antes do nó do gerente:

```python
memory = MemorySaver()
graph = builder.compile(checkpointer=memory, interrupt_before=["manager_approval"])
```

Quando o fluxo pausa, o gerente pode acessar o estado, ler o relatório, decidir e retomar:

```python
# O fluxo pausa automaticamente
response = graph.invoke(input_data, config)

# O gerente lê o relatório
snapshot = graph.get_state(config)
print(snapshot.values.get("analysis_report"))

# O gerente decide
graph.update_state(config, {"is_approved": True})

# O gerente retoma
graph.invoke(None, config)
```

O `None` indica que não é um novo fluxo — é a retomada do que estava pausado.

---

## Mascaramento de CPF no LiteLLM

O CPF é mascarado na **infraestrutura**, não no código. Toda chamada ao LLM passa pelo proxy LiteLLM, que usa o Microsoft Presidio para detectar e substituir o CPF automaticamente.

```
App Python → LiteLLM (proxy) → Presidio detecta CPF → Anonymizer substitui → LLM recebe XXX.***.***-XX
```

### Como configurar

**1. Recognizer customizado** — ensina o Presidio a detectar CPF brasileiro:

```json
[
  {
    "name": "BrazilCpfRecognizer",
    "supported_language": "en",
    "patterns": [
      { "name": "cpf_with_dots", "regex": "\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}", "score": 1.0 },
      { "name": "cpf_digits_only", "regex": "\\b\\d{11}\\b", "score": 0.6 }
    ],
    "supported_entity": "BRAZIL_CPF"
  }
]
```

**2. Guardrail no LiteLLM** — ativa o Presidio como interceptador:

```yaml
guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"          # intercepta ANTES de enviar ao LLM
      default_on: true          # sempre ativo
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
```

**3. Anonymizer Proxy** — aplica a máscara customizada `XXX.***.***-XX`:

```python
# anonymizer_proxy/app.py
CUSTOM_OPERATORS = {
    "BRAZIL_CPF": OperatorConfig("replace", {"new_value": "XXX.***.***-XX"}),
}

engine = AnonymizerEngine()
result = engine.anonymize(text=text, analyzer_results=results, operators=CUSTOM_OPERATORS)
```

O proxy existe porque a REST API do Presidio Anonymizer ignora operadores customizados — só a Python API os respeita.

**4. Docker Compose** — sobe tudo com um comando:

```bash
docker compose up -d --build
```

São 4 containers: LiteLLM (proxy), Presidio Analyzer (detecta), Anonymizer Proxy (mascara) e Anonymizer Upstream (fallback).

O resultado: o código Python envia o CPF real sem se preocupar. A infraestrutura intercepta e protege. O LLM nunca vê `123.456.789-00` — só `XXX.***.***-XX`.

---

## Resultado final

```json
{
  "data": {
    "answer": "REPORT: O identificador do cliente é XXX.***.***-XX ...",
    "client_cpf": "XXX.***.***-XX",
    "requested_amount": 10000.0,
    "sources": [
      {
        "url": "https://www.bankestudo.com.br/creditos",
        "title": "Política de Crédito do BANCO ESTUDO S.A.",
        "relevance_score": 0.8
      }
    ]
  }
}
```

Uma solicitação de crédito entra com CPF real → o RAG busca a política do banco → a IA analisa e classifica → o LangGraph decide se pausa para o gerente ou aprova automaticamente → o Presidio garante que o CPF nunca chegou ao modelo → a resposta sai estruturada, validada e com dados protegidos.

---