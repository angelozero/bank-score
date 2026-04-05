# 🏦 Bank Score — Auditoria de Crédito com IA + Proteção de Dados (LGPD)

Sistema de auditoria cognitiva de crédito que usa **RAG (Retrieval-Augmented Generation)** para analisar solicitações de crédito com base na política interna do banco, com **mascaramento automático de CPF** via Microsoft Presidio.

---

## 📋 O que este projeto faz?

1. Recebe uma solicitação de crédito (CPF + valor)
2. Busca trechos relevantes da política de crédito do banco (RAG)
3. Envia para uma IA (Llama 3.2) que analisa e classifica o cliente
4. **Mascara automaticamente o CPF** antes de enviar à IA (LGPD)
5. Retorna um relatório estruturado com a classificação do cliente

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Para que serve |
|---|---|
| **Python 3.14** | Linguagem principal da aplicação |
| **FastAPI** | Framework web para criar a API REST |
| **LangChain** | Framework para construir aplicações com LLMs |
| **LangGraph** | Orquestração de fluxos com grafos de estado (nodes, edges, checkpoints) |
| **Ollama + Llama 3.2** | Modelo de IA local (roda na sua máquina) |
| **ChromaDB** | Banco de dados vetorial para busca semântica (RAG) |
| **LiteLLM** | Proxy que intermedia chamadas ao LLM e aplica proteções |
| **Microsoft Presidio** | Detecta e mascara dados sensíveis (CPF) |
| **Docker Compose** | Orquestra os containers da infraestrutura |
| **Pydantic** | Validação e estruturação das respostas do LLM |

---

## 📁 Estrutura do Projeto

```
bank-score/
├── app.py                          # API FastAPI (ponto de entrada)
├── config.yaml                     # Configuração do LiteLLM + Presidio
├── docker-compose.yaml             # Orquestração dos containers
├── presidio_ad_hoc_recognizers.json # Regex para detectar CPF brasileiro
├── graph.png                       # Imagem do grafo LangGraph (gerada)
├── pyproject.toml                  # Dependências Python
├── .env                            # Variáveis de ambiente
│
├── anonymizer_proxy/               # Proxy customizado do Presidio Anonymizer
│   ├── app.py                      # Aplica a máscara XXX.***.***-XX
│   ├── Dockerfile
│   └── requirements.txt
│
├── base_path_files/                # Documentos fonte
│   └── politica_credito_v1.pdf     # Política de crédito do banco
│
├── chunks_db/                      # Banco vetorial ChromaDB (gerado)
│
└── src/
    ├── agent/
    │   ├── agent_langgraph_model.py    # Schema da resposta estruturada (Pydantic)
    │   └── agent_base_model.py         # Schema base do agente
    │
    ├── dataprovider/
    │   ├── chroma_db.py                # Acesso ao ChromaDB
    │   └── llm_factory.py              # Fábrica de instâncias do LLM
    │
    ├── node/
    │   ├── state.py                    # Grafo LangGraph de crédito (produção)
    │   ├── state_test.py               # Testes do grafo com checkpoint e gerente
    │   └── node_example.py             # Exemplo didático de grafo condicional
    │
    ├── service/
    │   ├── rag_service.py              # Orquestrador principal do fluxo RAG
    │   ├── get_results_by_relevance_score.py  # Busca semântica
    │   ├── get_context_by_results.py          # Monta o contexto
    │   ├── get_client_analysis_risk_descritpion.py  # 1ª análise do LLM
    │   ├── get_risk_analysis_prompt.py        # Prompt final de auditoria
    │   ├── get_llm_with_tools.py              # LLM com ferramentas
    │   ├── get_chat_model.py                  # Instância do chat model
    │   ├── get_embedding_service.py           # Serviço de embeddings
    │   └── ...
    │
    └── tools/
        └── validate_credit_policy_tool.py  # Ferramenta de validação de política
```

---

## 🔄 Fluxo Completo (Passo a Passo)

Quando o usuário faz uma requisição `GET /` ou `POST /`, o seguinte acontece:

### Fase 1 — Entrada

```
Usuário → API FastAPI (app.py) → rag_service.py
```

O `app.py` recebe o CPF e o valor, e chama o `rag_service.py`:

```python
# app.py
return rag_langgraph_execute("123.456.789-00", 10000.0)
```

### Fase 2 — Busca de Contexto (RAG)

```
rag_service.py → ChromaDB → Contexto relevante
```

| Passo | Arquivo | O que faz |
|---|---|---|
| `[01]` | `rag_service.py` | Monta a query com CPF + valor |
| `[02]` | `get_results_by_relevance_score.py` | Inicia a busca semântica |
| `[03]` | `get_embedding_service.py` | Gera embeddings via LiteLLM/Ollama |
| `[04]` | `chroma_db.py` | Busca os 3 trechos mais relevantes da política |
| `[05]` | `chroma_db.py` | Recupera dados do ChromaDB |
| `[06]` | `get_context_by_results.py` | Junta os trechos em um texto de contexto |

**O que é RAG?** Em vez de o LLM "inventar" respostas, ele recebe trechos reais da política de crédito do banco como contexto. Assim, a resposta é baseada em fatos.

### Fase 3 — Primeira Análise do LLM

```
Contexto + Query → LiteLLM → Presidio (mascara CPF) → Ollama/Llama 3.2 → Análise de risco
```

| Passo | Arquivo | O que faz |
|---|---|---|
| `[07]` | `get_client_analysis_risk_descritpion.py` | Envia contexto + query ao LLM para gerar uma descrição de risco |

> ⚠️ Nesta chamada, o CPF `123.456.789-00` é **automaticamente mascarado** pelo Presidio para `XXX.***.***-XX` antes de chegar ao LLM.

### Fase 4 — Mascaramento do CPF (Presidio)

Toda chamada ao LLM passa pelo **LiteLLM proxy** (porta 4000), que tem o guardrail Presidio ativo. O mascaramento acontece em 3 sub-passos:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DENTRO DO LITELLM PROXY                      │
│                                                                 │
│  1. Texto com CPF real                                          │
│     "CPF 123.456.789-00"                                        │
│              │                                                  │
│              ▼                                                  │
│  2. Presidio Analyzer detecta: BRAZIL_CPF (score: 1.0)          │
│              │                                                  │
│              ▼                                                  │
│  3. Anonymizer Proxy substitui: "CPF XXX.***.***-XX"            │
│              │                                                  │
│              ▼                                                  │
│  4. Texto mascarado enviado ao Ollama/Llama 3.2                 │
│     "CPF XXX.***.***-XX"                                        │
└─────────────────────────────────────────────────────────────────┘
```

**O LLM nunca vê o CPF real.**

### Fase 5 — Auditoria Final

```
Análise de risco + CPF mascarado + Valor → Prompt final → LLM → Resposta estruturada
```

| Passo | Arquivo | O que faz |
|---|---|---|
| `[08]` | `get_risk_analysis_prompt.py` | Monta o prompt final com instruções de auditoria |
| `[09]` | `get_llm_with_tools.py` | Configura o LLM com a ferramenta `validate_credit_policy` |
| `[10]` | `rag_service.py` | Envia ao LLM e recebe resposta estruturada |

O prompt instrui o LLM a:
- Classificar o cliente em: **CONSERVADOR**, **RISCO**, **EXCEÇÃO** ou **BLOQUEIO**
- Citar os itens da política que fundamentam a decisão
- Usar o CPF mascarado (`XXX.***.***-XX`) no relatório

### Fase 6 — Resposta

O LLM retorna um JSON estruturado (validado pelo Pydantic):

```json
{
  "data": {
    "answer": "REPORT: ... O identificador do cliente é XXX.***.***-XX ...",
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

---

## 🐳 Infraestrutura Docker

O projeto usa 4 containers orquestrados pelo Docker Compose:

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────┐           │
│  │   LiteLLM Proxy  │───▶│  Presidio Analyzer   │           │
│  │   (porta 4000)   │    │   (porta 3000)       │           │
│  │                  │    │   Detecta CPF        │           │
│  │  Guardrail PII   │    └──────────────────────┘           │
│  │                  │                                       │
│  │                  │    ┌──────────────────────┐           │
│  │                  │───▶│  Anonymizer Proxy    │           │
│  └──────────────────┘    │   (porta 3000)       │           │
│                          │   Máscara: XXX.***   │           │
│                          └──────────┬───────────┘           │
│                                     │                       │
│                          ┌──────────▼───────────┐           │
│                          │  Presidio Anonymizer │           │
│                          │  Upstream (3000)     │           │
│                          └──────────────────────┘           │
└─────────────────────────────────────────────────────────────┘

         ┌──────────────────┐
         │  Ollama (local)  │  ← Roda fora do Docker
         │  Llama 3.2       │
         │  (porta 11434)   │
         └──────────────────┘
```

| Container | Imagem | Função |
|---|---|---|
| `bank-score` | `litellm/litellm:latest` | Proxy LLM com guardrail Presidio |
| `presidio-analyzer` | `mcr.microsoft.com/presidio-analyzer:latest` | Detecta dados sensíveis no texto |
| `presidio-anonymizer` | Build local (`anonymizer_proxy/`) | Substitui CPF por `XXX.***.***-XX` |
| `presidio-anonymizer-upstream` | `mcr.microsoft.com/presidio-anonymizer:latest` | Anonymizer original (fallback) |

---

## 🚀 Como Executar

### Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Ollama** instalado e rodando com o modelo `llama3.2`:
  ```bash
  ollama pull llama3.2
  ollama serve
  ```
- **Python 3.14** com `uv` (gerenciador de pacotes)

### Passo 1 — Subir a infraestrutura Docker

```bash
docker compose up -d --build
```

Isso inicia o LiteLLM, Presidio Analyzer, Anonymizer Proxy e Anonymizer Upstream.

### Passo 2 — Instalar dependências Python

```bash
uv sync
```

### Passo 3 — Executar a aplicação

```bash
uv run python app.py
```

A API estará disponível em `http://localhost:8000`.

### Passo 4 — Testar

```bash
# GET (usa CPF hardcoded 123.456.789-00)
curl http://localhost:8000/

# POST (com CPF customizado)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"cpf": "987.654.321-00", "valor": 5000.0}'
```

---

## ⚙️ Configuração

### Variáveis de Ambiente (`.env`)

| Variável | Valor | Descrição |
|---|---|---|
| `MODEL_NAME` | `ai-angelo-zero` | Nome do modelo no LiteLLM |
| `API_KEY` | `api-key-angelo-1234` | Chave de API do LiteLLM |
| `BASE_URL` | `http://localhost:4000/v1` | URL do LiteLLM proxy |
| `BASE_PATH_FILES` | `base_path_files` | Pasta dos documentos fonte |
| `CHUNKS_DB_PATH` | `chunks_db` | Pasta do banco vetorial ChromaDB |

### Configuração do LiteLLM (`config.yaml`)

```yaml
model_list:
  - model_name: ai-angelo-zero
    litellm_params:
      model: ollama/llama3.2
      api_base: "http://host.docker.internal:11434"

guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      default_on: true
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
      presidio_language: "en"
```

### Recognizer de CPF (`presidio_ad_hoc_recognizers.json`)

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

---

## 🔒 Proteção de Dados (LGPD)

O mascaramento de CPF é feito em **camada de infraestrutura**, não no código da aplicação. Isso significa:

- ✅ O código Python **não precisa se preocupar** com mascaramento
- ✅ Mesmo que alguém esqueça de mascarar, o Presidio intercepta automaticamente
- ✅ O LLM **nunca recebe** o CPF real
- ✅ A resposta final contém apenas `XXX.***.***-XX`

Para mais detalhes técnicos sobre o mascaramento, veja o [PII_MASKING_README.md](PII_MASKING_README.md).

---

## 📊 Classificações do Cliente

O LLM classifica o cliente em um destes padrões:

| Padrão | Significado |
|---|---|
| **CONSERVADOR** | Score alto, valor compatível, sem alertas regionais |
| **RISCO** | Suspeita de fraude, urgência excessiva, ou regras regionais |
| **EXCEÇÃO** | Empreendedor de Alto Potencial (Seção 5 da política) |
| **BLOQUEIO** | Violação de Hard Blocks (Seção 3) ou Score Bronze |

---

## 🔧 Ferramenta de Validação

O LLM tem acesso a uma ferramenta (`validate_credit_policy`) que verifica tecnicamente se os dados violam a política:

```python
@tool
def validate_credit_policy(score, regional_risk, has_impediment):
    if has_impediment:
        return "BLOQUEIO"
    if regional_risk and score < 800:
        return "RISCO"
    return "CONSERVADOR"
```

---

## 🔀 LangGraph — Orquestração com Grafos de Estado

O projeto utiliza **LangGraph** para orquestrar o fluxo de análise de crédito como um **grafo de estado** com nós, arestas condicionais e checkpoints. Os arquivos ficam em [`src/node/`](src/node/).

### Conceito

Em vez de um script linear, o fluxo é modelado como um **grafo dirigido** onde cada etapa é um **nó** e as transições entre elas são **arestas**. Isso permite:

- **Roteamento condicional** — a IA decide o próximo passo
- **Pausa e retomada** — o grafo pode pausar para aprovação humana (gerente)
- **Checkpoints** — o estado é salvo em memória e pode ser inspecionado/retomado

### Exemplo Didático (`node_example.py`)

O arquivo [`node_example.py`](src/node/node_example.py) é um exemplo simples para entender o conceito:

```
START → [A] → (condição) → [B] ou [C] → END
```

```python
# Se current_number >= 50, vai para C; senão, vai para B
def conditional_function(state) -> Literal["goes_to_b", "goes_to_c"]:
    if state.current_number >= 50:
        return "goes_to_c"
    return "goes_to_b"
```

Cada nó recebe e retorna um estado tipado (`StateConditional`), e o grafo decide automaticamente qual caminho seguir.

### Grafo de Crédito (`state.py`)

O arquivo [`state.py`](src/node/state.py) implementa o **grafo real de análise de crédito** com 4 nós:

```
START → [guardrails] → [analysis] → (condição) → [auto_approve] → END
                                         │
                                         └──────→ [manager_approval] ⏸ → END
```

#### Estado (`CreditState`)

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

#### Nós

| Nó | Função | O que faz |
|---|---|---|
| `guardrails` | [`guardrails_node()`](src/node/state.py:28) | Prepara os dados; o mascaramento real é feito pelo LiteLLM/Presidio |
| `analysis` | [`analysis_node()`](src/node/state.py:37) | Chama o RAG (`rag_service.execute`) e obtém o relatório da IA |
| `manager_approval` | [`manager_node()`](src/node/state.py:60) | Pausa o grafo para aprovação humana |
| `auto_approve` | lambda | Aprova automaticamente e encerra |

#### Roteamento Condicional

Após a análise, a função [`route_request()`](src/node/state.py:69) decide o destino:

```python
def route_request(state) -> Literal["to_manager", "to_auto_check"]:
    pattern = state.get("client_pattern")
    if pattern == "RISCO" or state["amount"] > 5000:
        return "to_manager"       # Vai para aprovação do gerente
    return "to_auto_check"        # Aprovação automática
```

- **Valor > R$ 5.000** ou **padrão RISCO** → pausa para o gerente aprovar
- **Demais casos** → aprovação automática

#### Checkpoint e Interrupção

O grafo usa `MemorySaver` como checkpointer e `interrupt_before=["manager_approval"]`:

```python
memory = MemorySaver()
graph = builder.compile(checkpointer=memory, interrupt_before=["manager_approval"])
```

Isso significa que quando o fluxo chega no nó `manager_approval`, ele **pausa automaticamente**. O gerente pode então:

1. Inspecionar o estado atual (`graph.get_state(config)`)
2. Atualizar campos (`graph.update_state(config, {"is_approved": True})`)
3. Retomar o grafo (`graph.invoke(None, config)`)

### Testes (`state_test.py`)

O arquivo [`state_test.py`](src/node/state_test.py) contém dois cenários de teste:

| Teste | O que simula |
|---|---|
| [`execute_test()`](src/node/state_test.py:3) | Fluxo completo: entrada com valor alto → pausa → retomada |
| [`execute_manager_aproval_test()`](src/node/state_test.py:36) | Gerente acessa proposta pausada, visualiza relatório e decide |

```bash
# Executar os testes do grafo
cd src/node && python state_test.py
```

### Visualização do Grafo

O grafo pode ser exportado como imagem PNG:

```python
graph.get_graph().draw_mermaid_png(output_file_path="graph.png")
```

O arquivo [`graph.png`](graph.png) é gerado na raiz do projeto.

---

## 📝 Resumo

> Uma solicitação de crédito entra com CPF real → o **LangGraph** orquestra o fluxo como um grafo de estado → o **RAG** busca a política do banco → o **Presidio** mascara o CPF → a **IA** analisa e classifica → se necessário, o grafo **pausa para aprovação do gerente** → a resposta sai com CPF mascarado como `XXX.***.***-XX`.
