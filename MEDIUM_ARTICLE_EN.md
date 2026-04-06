# Credit Audit System 
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

An application that receives a credit request (CPF + amount), retrieves relevant excerpts from the bank's internal policy, sends them to a local AI that analyzes and classifies the risk — the CPF is automatically masked before reaching the model, without a single line of Python code for that.

---

## Flow Orchestration

```
User sends CPF + amount
        │
        ▼
FastAPI receives the request
        │
        ▼
RAG retrieves credit policy excerpts from ChromaDB
        │
        ▼
LLM (Llama 3.2) analyzes and classifies the client
        │
        ▼
LangGraph decides: automatic approval or pause for the manager
        │
        ▼
JSON response with report + masked CPF (XXX.***.***-XX)
```

The CPF `123.456.789-00` never reaches the AI model. It is intercepted and replaced with `XXX.***.***-XX` at the infrastructure layer.

---

## RAG — The AI Responds Based on Real Documents

RAG (Retrieval-Augmented Generation) is the technique that prevents the AI from making up answers. Instead of relying on the model's generic knowledge, the application retrieves real excerpts from the credit policy and provides them as context.

The complete flow is in [`rag_service.py`](src/service/rag_service.py):

```python
def execute(cpf, amount):
    # 1. Build the query
    query = (
        f"Perform the credit audit for the amount of R$ {amount} "
        f"and CPF {cpf}. Check the score range classification, "
        "possible impediment factors from Item 3 and 'Geographic Override' rules from Item 7. "
        "Return the client pattern and the report according to the Item 10 protocol."
    )

    # 2. Retrieve the 3 most relevant excerpts from the policy in ChromaDB
    results = get_results_by_relevance_score(query)

    # 3. Combine the excerpts into a context string
    context = get_context_by_results(results)

    # 4. Send context + query to the LLM → receive risk analysis
    analysis_risk_description = get_client_analysis_risk_descritpion(context, query)

    # 5. Build the final audit prompt
    prompt = get_risk_analysis_prompt(cpf, amount, analysis_risk_description)

    # 6. Configure the LLM with tool + structured response
    llm = get_llm_with_tools(validate_credit_policy)

    # 7. Send and receive the final response
    response = llm.invoke(prompt["messages"])
    return {"data": response}
```

### How the Search Works Under the Hood

The credit policy document (PDF) was previously split into **chunks** of 2000 characters with an overlap of 500. Each chunk was transformed into a numerical vector (embedding) and stored in **ChromaDB**.

When a query arrives, it is also converted into a vector. ChromaDB compares the vectors and returns the most semantically similar chunks — not by keywords, but by meaning.

```python
# src/service/generate_chunks_service.py — how chunks are created
spliter = RecursiveCharacterTextSplitter(
    chunk_size=2000, chunk_overlap=500, length_function=len, add_start_index=True
)
```

The 500-character overlap ensures that sentences at the boundary between two chunks are not lost.

### Tool and Structured Response

The LLM doesn't just generate text — it can call a Python tool during the analysis:

```python
# src/tools/validate_credit_policy_tool.py
@tool
def validate_credit_policy(score: float, regional_risk: bool, has_impediment: bool) -> str:
    if has_impediment:
        return "BLOCKED: Direct impediment identified in Item 3."
    if regional_risk and score < 800:
        return "RISK: Insufficient score for the region (Geographic Override)."
    return "CONSERVATIVE: Client meets all security requirements."
```

And the response is forced to follow a Pydantic schema — if the AI returns something outside the schema, it is rejected:

```python
# src/agent/agent_langgraph_model.py
class LangGraphAgentResponse(BaseModel):
    answer: str
    client_cpf: str
    requested_amount: float
    sources: List[LangGraphSource]
```

---

## LangGraph — The Flow Is Not Linear, It's a Graph

Instead of a script that does A → B → C, the flow is modeled as a **state graph** where each step is a node and transitions can be conditional. This allows the flow to **pause for human approval** and be **resumed later**.

The complete graph is in [`state.py`](src/node/state.py):

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

This is the shared state. All nodes read from and write to it.

### The Nodes

```
START → [guardrails] → [analysis] → (condition) → [auto_approve] → END
                                         │
                                         └──────→ [manager_approval] ⏸ → END
```

- **guardrails** — prepares the input data
- **analysis** — calls the full RAG pipeline and obtains the AI report
- **auto_approve** — marks as automatically approved
- **manager_approval** — pauses for the manager to decide

### Conditional Routing

After the analysis, the graph decides the path:

```python
def route_request(state: CreditState) -> Literal["to_manager", "to_auto_check"]:
    pattern = state.get("client_pattern")
    if pattern == "RISCO" or state["amount"] > 5000:
        return "to_manager"
    return "to_auto_check"
```

Amount above R$ 5,000 or RISK classification → pause for the manager. All other cases → automatic approval.

### Checkpoint and Human-in-the-Loop

The graph uses `MemorySaver` to save the state at each node and `interrupt_before` to pause before the manager node:

```python
memory = MemorySaver()
graph = builder.compile(checkpointer=memory, interrupt_before=["manager_approval"])
```

When the flow pauses, the manager can access the state, read the report, decide, and resume:

```python
# The flow pauses automatically
response = graph.invoke(input_data, config)

# The manager reads the report
snapshot = graph.get_state(config)
print(snapshot.values.get("analysis_report"))

# The manager decides
graph.update_state(config, {"is_approved": True})

# The manager resumes
graph.invoke(None, config)
```

The `None` indicates that this is not a new flow — it's the resumption of the one that was paused.

---

## CPF Masking with LiteLLM

The CPF is masked at the **infrastructure** level, not in the code. Every call to the LLM goes through the LiteLLM proxy, which uses Microsoft Presidio to detect and replace the CPF automatically.

```
Python App → LiteLLM (proxy) → Presidio detects CPF → Anonymizer replaces → LLM receives XXX.***.***-XX
```

### How to Configure

**1. Custom Recognizer** — teaches Presidio to detect Brazilian CPF:

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

**2. Guardrail in LiteLLM** — activates Presidio as an interceptor:

```yaml
guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"          # intercepts BEFORE sending to the LLM
      default_on: true          # always active
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
```

**3. Anonymizer Proxy** — applies the custom mask `XXX.***.***-XX`:

```python
# anonymizer_proxy/app.py
CUSTOM_OPERATORS = {
    "BRAZIL_CPF": OperatorConfig("replace", {"new_value": "XXX.***.***-XX"}),
}

engine = AnonymizerEngine()
result = engine.anonymize(text=text, analyzer_results=results, operators=CUSTOM_OPERATORS)
```

The proxy exists because the Presidio Anonymizer REST API ignores custom operators — only the Python API supports them.

**4. Docker Compose** — brings everything up with a single command:

```bash
docker compose up -d --build
```

There are 4 containers: LiteLLM (proxy), Presidio Analyzer (detects), Anonymizer Proxy (masks), and Anonymizer Upstream (fallback).

The result: the Python code sends the real CPF without worrying about it. The infrastructure intercepts and protects it. The LLM never sees `123.456.789-00` — only `XXX.***.***-XX`.

---

## Final Result

```json
{
  "data": {
    "answer": "REPORT: The client identifier is XXX.***.***-XX ...",
    "client_cpf": "XXX.***.***-XX",
    "requested_amount": 10000.0,
    "sources": [
      {
        "url": "https://www.bankestudo.com.br/creditos",
        "title": "Credit Policy of BANCO ESTUDO S.A.",
        "relevance_score": 0.8
      }
    ]
  }
}
```

A credit request comes in with a real CPF → RAG retrieves the bank's policy → the AI analyzes and classifies → LangGraph decides whether to pause for the manager or approve automatically → Presidio ensures the CPF never reached the model → the response comes out structured, validated, and with protected data.

---
