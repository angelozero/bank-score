# 🏦 Bank Score — Auditoria Cognitiva de Crédito com IA

Sistema que analisa solicitações de crédito usando inteligência artificial. A aplicação lê a política interna do banco, entende o contexto da solicitação e gera um relatório de auditoria — tudo isso protegendo automaticamente os dados sensíveis do cliente (CPF).

---

## O que esta aplicação faz

Uma pessoa solicita crédito informando seu CPF e o valor desejado. A aplicação:

1. Busca os trechos mais relevantes da política de crédito do banco
2. Envia esses trechos junto com os dados da solicitação para uma IA local
3. A IA analisa e classifica o cliente em um padrão de risco
4. Se o valor for alto ou houver risco, o fluxo pausa para um gerente humano decidir
5. O CPF é mascarado automaticamente antes de chegar à IA — ela nunca vê o dado real

O resultado é um relatório estruturado com a classificação do cliente, os itens da política que fundamentam a decisão e o CPF protegido.

---

## Conceitos e Padrões Aplicados

### RAG — Retrieval-Augmented Generation

A IA não inventa respostas. Antes de gerar qualquer análise, a aplicação busca trechos reais da política de crédito do banco e entrega como contexto para o modelo. Isso se chama RAG.

Na prática, funciona assim:

1. O documento da política de crédito (PDF) é dividido em pedaços menores chamados **chunks**
2. Cada chunk é transformado em um vetor numérico (embedding) que representa seu significado
3. Esses vetores são armazenados em um banco de dados vetorial (ChromaDB)
4. Quando chega uma solicitação, a pergunta também é transformada em vetor
5. O sistema compara os vetores e encontra os chunks mais parecidos com a pergunta
6. Esses chunks são enviados como contexto para a IA responder

Isso garante que a resposta da IA seja baseada em fatos documentados, não em conhecimento genérico.

### Chunks — Divisão de Documentos

Um documento grande não pode ser enviado inteiro para a IA — existe um limite de texto que o modelo processa por vez. A solução é dividir o documento em pedaços menores (chunks).

Nesta aplicação, o arquivo [`generate_chunks_service.py`](src/service/generate_chunks_service.py) usa o `RecursiveCharacterTextSplitter` do LangChain com:

- **chunk_size = 2000**: cada pedaço tem no máximo 2000 caracteres
- **chunk_overlap = 500**: os últimos 500 caracteres de um chunk se repetem no início do próximo

A sobreposição (overlap) existe para que o contexto não se perca na fronteira entre dois pedaços. Se uma frase importante estiver dividida entre dois chunks, a sobreposição garante que pelo menos um deles tenha a frase completa.

```python
# src/service/generate_chunks_service.py
spliter = RecursiveCharacterTextSplitter(
    chunk_size=2000, chunk_overlap=500, length_function=len, add_start_index=True
)
chunks = spliter.split_documents(documents)
```

### Embeddings — Representação Vetorial de Texto

Embedding é a transformação de um texto em uma lista de números (vetor). Textos com significados parecidos geram vetores próximos no espaço matemático.

Quando a aplicação recebe a pergunta "Realize a auditoria de crédito para o valor de R$ 10000", ela transforma essa frase em um vetor e compara com os vetores dos chunks armazenados. Os chunks cujos vetores estão mais próximos são os mais relevantes para responder aquela pergunta.

O serviço de embeddings é criado em [`llm_factory.py`](src/dataprovider/llm_factory.py):

```python
# src/dataprovider/llm_factory.py
def get_embedding():
    return init_embeddings(
        model=MODEL_NAME,
        provider="openai",
        api_key=API_KEY,
        base_url=BASE_URL,
        model_kwargs={"encoding_format": "float"},
    )
```

O parâmetro `encoding_format: "float"` força o retorno em formato numérico decimal, evitando erros de compatibilidade entre LiteLLM e Ollama.

### Busca por Similaridade com Relevance Score

A busca no ChromaDB não é uma busca por palavras-chave. É uma busca semântica — ela encontra trechos que têm significado parecido com a pergunta, mesmo que usem palavras diferentes.

O método `similarity_search_with_relevance_scores` retorna os `k` chunks mais relevantes junto com uma pontuação de 0 a 1. Quanto mais próximo de 1, mais relevante é o trecho.

```python
# src/dataprovider/chroma_db.py
def similarity_search_with_relevance_scores(embeddings, query, k):
    database = Chroma(persist_directory=CHUNKS_DB_PATH, embedding_function=embeddings)
    return database.similarity_search_with_relevance_scores(query, k=k)
```

A aplicação busca os 3 chunks mais relevantes (`k=3`) e descarta resultados com score abaixo de 0.2:

```python
# src/service/get_context_by_results.py
def get_context_by_results(results):
    if not results or results[0][1] < 0.2:
        return
    return "\n".join([doc.page_content for doc, _score in results])
```

### ChromaDB — Banco de Dados Vetorial

ChromaDB é o banco de dados que armazena os vetores dos chunks. Diferente de um banco de dados tradicional que busca por igualdade (WHERE nome = 'João'), o ChromaDB busca por proximidade vetorial — ele encontra os registros cujos vetores estão mais próximos do vetor da consulta.

Os dados ficam persistidos na pasta `chunks_db/` e são carregados automaticamente quando a aplicação inicia uma busca.

### LLM — Large Language Model

LLM é o modelo de inteligência artificial que processa texto. Nesta aplicação, o modelo usado é o **Llama 3.2** rodando localmente via **Ollama**. Isso significa que nenhum dado sai da máquina — tudo é processado localmente.

A comunicação com o modelo passa por um proxy chamado **LiteLLM**, que adiciona camadas de proteção (como o mascaramento de CPF) antes de o texto chegar ao modelo.

### Tool Calling — Ferramentas do LLM

O LLM pode usar ferramentas (funções Python) durante sua análise. Nesta aplicação, existe uma ferramenta chamada `validate_credit_policy` que verifica tecnicamente se os dados violam a política do banco:

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

O LLM decide sozinho quando chamar essa ferramenta. Ele extrai os parâmetros do contexto e usa o resultado para fundamentar sua análise. Isso é chamado de **Tool Calling** — o modelo não apenas gera texto, mas também executa ações.

### Structured Output — Resposta Estruturada com Pydantic

A resposta da IA não é texto livre. Ela é forçada a seguir um formato específico definido por um modelo Pydantic:

```python
# src/agent/agent_langgraph_model.py
class LangGraphAgentResponse(BaseModel):
    answer: str = Field(description="Resposta detalhada da auditoria de crédito")
    client_cpf: str = Field(description="CPF do cliente (formato mascarado)")
    requested_amount: float = Field(description="Valor solicitado na auditoria")
    sources: List[LangGraphSource] = Field(description="Fontes utilizadas no RAG")
```

Isso garante que a resposta sempre tenha os campos esperados, com os tipos corretos. Se a IA retornar algo fora do formato, o Pydantic rejeita.

### Mascaramento de CPF — Defense in Depth

O CPF do cliente é mascarado automaticamente na camada de infraestrutura, não no código Python. Toda chamada ao LLM passa pelo proxy LiteLLM, que usa o Microsoft Presidio para detectar e substituir o CPF por `XXX.***.***-XX` antes de o texto chegar ao modelo.

Isso é um padrão de segurança chamado **Defense in Depth** (defesa em profundidade): mesmo que o desenvolvedor esqueça de mascarar o CPF no código, a infraestrutura intercepta e protege automaticamente.

Para detalhes completos sobre como o mascaramento funciona, veja o [PII_MASKING_README.md](PII_MASKING_README.md).

### LangGraph — Orquestração com Grafos de Estado

O fluxo da aplicação não é um script linear. Ele é modelado como um grafo de estado usando LangGraph, onde cada etapa é um nó e as transições entre elas podem ser condicionais. Isso permite que o fluxo pause para aprovação humana e seja retomado depois.

Para detalhes completos sobre o LangGraph nesta aplicação, veja o [LANGGRAPH_README.md](LANGGRAPH_README.md).

---

## Tecnologias

| Tecnologia | O que é | Como é usada nesta aplicação |
|---|---|---|
| **Python 3.14** | Linguagem de programação | Linguagem principal de toda a aplicação |
| **FastAPI** | Framework web para APIs REST | Expõe os endpoints GET e POST que recebem as solicitações |
| **LangChain** | Framework para aplicações com LLMs | Gerencia prompts, embeddings, busca vetorial e tool calling |
| **LangGraph** | Extensão do LangChain para grafos de estado | Orquestra o fluxo de análise com nós, arestas condicionais e checkpoints |
| **Ollama** | Servidor local para rodar modelos de IA | Executa o modelo Llama 3.2 na máquina local |
| **Llama 3.2** | Modelo de linguagem da Meta | Gera as análises de risco e relatórios de auditoria |
| **ChromaDB** | Banco de dados vetorial | Armazena e busca os chunks da política por similaridade semântica |
| **LiteLLM** | Proxy para chamadas a LLMs | Intermedia todas as chamadas ao modelo e aplica o guardrail de mascaramento |
| **Microsoft Presidio** | Ferramenta de detecção e anonimização de PII | Detecta CPFs no texto e substitui por `XXX.***.***-XX` |
| **Pydantic** | Biblioteca de validação de dados | Define e valida o formato da resposta estruturada da IA |
| **Docker Compose** | Orquestrador de containers | Gerencia os containers do LiteLLM, Presidio Analyzer e Anonymizer |
| **uv** | Gerenciador de pacotes Python | Instala e gerencia as dependências do projeto |

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              APLICAÇÃO PYTHON                                │
│                                                                              │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐   │
│  │ FastAPI │───▶│  LangGraph   │───▶│  RAG Service │───▶│  LLM + Tools   │   │
│  │ (app.py)│    │  (state.py)  │    │              │    │                │   │
│  └─────────┘    └──────────────┘    │  1. Embedding│    │  1. Prompt     │   │
│                                     │  2. ChromaDB │    │  2. Tool Call  │   │
│                                     │  3. Contexto │    │  3. Structured │   │
│                                     └──────────────┘    └───────┬────────┘   │
│                                                                 │            │
└─────────────────────────────────────────────────────────────────┼────────────┘
                                                                  │
                                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           INFRAESTRUTURA (Docker)                            │
│                                                                              │
│  ┌──────────────┐    ┌────────────────────┐    ┌─────────────────────────┐   │
│  │   LiteLLM    │───▶│ Presidio Analyzer  │    │   Anonymizer Proxy      │   │
│  │  (porta 4000)│    │   (porta 3000)     │    │   (porta 3000)          │   │
│  │              │    │   Detecta CPF      │    │   Substitui por         │   │
│  │  Guardrail   │───▶│                    │    │   XXX.***.***-XX        │   │
│  │  PII Masking │    └────────────────────┘    └─────────────────────────┘   │
│  └──────┬───────┘                                                            │
│         │                                                                    │
└─────────┼────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────┐
│  Ollama (local)  │
│  Llama 3.2       │
│  (porta 11434)   │
└──────────────────┘
```

---

## Estrutura do Projeto

```
bank-score/
├── app.py                              # Ponto de entrada — API FastAPI
├── config.yaml                         # Configuração do LiteLLM + guardrail Presidio
├── docker-compose.yaml                 # Orquestração dos 4 containers
├── presidio_ad_hoc_recognizers.json    # Regex customizado para detectar CPF brasileiro
├── politica_credito_v1.md              # Documento da política de crédito do banco
├── graph.png                           # Imagem do grafo LangGraph (gerada)
├── pyproject.toml                      # Dependências Python (gerenciadas pelo uv)
│
├── anonymizer_proxy/                   # Proxy customizado do Presidio Anonymizer
│   ├── app.py                          # Aplica a máscara XXX.***.***-XX via Python API
│   ├── Dockerfile                      # Container do proxy
│   └── requirements.txt               # Dependências do proxy
│
├── base_path_files/                    # Documentos fonte (PDFs)
│   └── politica_credito_v1.pdf         # Política de crédito em PDF
│
├── chunks_db/                          # Banco vetorial ChromaDB (gerado automaticamente)
│
└── src/
    ├── agent/
    │   └── agent_langgraph_model.py    # Schema Pydantic da resposta estruturada
    │
    ├── dataprovider/
    │   ├── chroma_db.py                # Acesso ao ChromaDB (persistir e buscar)
    │   └── llm_factory.py              # Fábrica de instâncias do LLM e embeddings
    │
    ├── node/
    │   ├── state.py                    # Grafo LangGraph de análise de crédito
    │   └── state_test.py               # Testes do grafo com checkpoint e gerente
    │
    ├── service/
    │   ├── rag_service.py              # Orquestrador principal do fluxo RAG
    │   ├── upload_files.py             # Pipeline: carrega PDF → chunks → embeddings → ChromaDB
    │   ├── load_source_data_service.py # Carrega PDFs da pasta base_path_files
    │   ├── generate_chunks_service.py  # Divide documentos em chunks de 2000 caracteres
    │   ├── get_embedding_service.py    # Cria instância do serviço de embeddings
    │   ├── save_data_db.py             # Persiste chunks no ChromaDB
    │   ├── get_results_by_relevance_score.py    # Busca semântica no ChromaDB
    │   ├── find_data_by_similarity_relevance_scores.py  # Executa a busca vetorial
    │   ├── get_context_by_results.py            # Junta os chunks em texto de contexto
    │   ├── get_client_analysis_risk_descritpion.py  # 1ª chamada ao LLM (análise de risco)
    │   ├── get_risk_analysis_prompt.py          # Monta o prompt final de auditoria
    │   ├── get_llm_with_tools.py                # Configura LLM com tool + structured output
    │   └── get_chat_model.py                    # Instância do chat model via factory
    │
    └── tools/
        └── validate_credit_policy_tool.py  # Ferramenta que valida dados contra a política
```

---

## Fluxo Completo 

Quando o usuário faz uma requisição `GET /` ou `POST /`, o seguinte acontece:

### 1. Entrada — API recebe a solicitação

O [`app.py`](app.py) recebe o CPF e o valor via FastAPI e chama o serviço RAG:

```python
# app.py
@app.get("/")
def root():
    return rag_langgraph_execute("123.456.789-00", 10000.0)

@app.post("/")
def root(dados: SolicitacaoRAG):
    response = rag_langgraph_execute(dados.cpf, dados.valor)
    return {"status": "sucesso", "response": response}
```

### 2. Montagem da Query

O [`rag_service.py`](src/service/rag_service.py) monta uma pergunta estruturada com o CPF e o valor:

```python
# src/service/rag_service.py
query = (
    f"Realize a auditoria de crédito para o valor de R$ {amount} "
    f"e CPF {cpf}. Verifique o enquadramento nas faixas de score, "
    "possíveis fatores de impedimento do Item 3 e regras de 'Geographic Override' do Item 7. "
    "Retorne o padrão do cliente e o relatório conforme o protocolo do Item 10."
)
```

### 3. Busca de Contexto (RAG)

A query é transformada em embedding e comparada com os vetores no ChromaDB:

| Passo | Arquivo | O que faz |
|---|---|---|
| `[02]` | [`get_results_by_relevance_score.py`](src/service/get_results_by_relevance_score.py) | Inicia a busca semântica |
| `[03]` | [`llm_factory.py`](src/dataprovider/llm_factory.py) | Gera o embedding da query via LiteLLM/Ollama |
| `[04]` | [`chroma_db.py`](src/dataprovider/chroma_db.py) | Busca os 3 chunks mais relevantes no ChromaDB |
| `[05]` | [`chroma_db.py`](src/dataprovider/chroma_db.py) | Recupera os dados persistidos |
| `[06]` | [`get_context_by_results.py`](src/service/get_context_by_results.py) | Junta os chunks em um texto de contexto |

### 4. Primeira Análise do LLM

O contexto recuperado e a query são enviados ao LLM para gerar uma descrição de risco:

```python
# src/service/get_client_analysis_risk_descritpion.py
prompt = "Responda a pergunta baseada apenas no seguinte contexto: {context} --- {question}"
response = model.invoke(prompt)
```

Nesta chamada, o CPF `123.456.789-00` é automaticamente mascarado pelo Presidio para `XXX.***.***-XX` antes de chegar ao LLM.

### 5. Prompt Final de Auditoria

O [`get_risk_analysis_prompt.py`](src/service/get_risk_analysis_prompt.py) monta um prompt detalhado com:

- **SystemMessage**: instruções de como a IA deve se comportar (protocolo de privacidade, diretrizes de análise, classificação obrigatória, formato de resposta)
- **HumanMessage**: dados da solicitação (CPF, valor, contexto recuperado da política)

O prompt instrui a IA a classificar o cliente em um destes padrões:

| Padrão | Significado |
|---|---|
| **CONSERVADOR** | Score alto, valor compatível, sem alertas regionais |
| **RISCO** | Suspeita de fraude, urgência excessiva, ou regras regionais |
| **EXCEÇÃO** | Empreendedor de Alto Potencial (Seção 5 da política) |
| **BLOQUEIO** | Violação de Hard Blocks (Seção 3) ou Score Bronze |

### 6. LLM com Ferramentas e Resposta Estruturada

O [`get_llm_with_tools.py`](src/service/get_llm_with_tools.py) configura o modelo com a ferramenta de validação e força a resposta no formato Pydantic:

```python
# src/service/get_llm_with_tools.py
def get_llm_with_tools(tool):
    model = get_chat_model()
    llm = model.bind_tools([tool])
    return llm.with_structured_output(LangGraphAgentResponse)
```

### 7. Resposta Final

O LLM retorna um JSON estruturado e validado:

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

---

## Pipeline de Ingestão de Documentos

Antes de a aplicação poder responder perguntas, os documentos precisam ser processados e armazenados no ChromaDB. Esse processo é executado uma vez pelo [`upload_files.py`](src/service/upload_files.py):

```
PDF → Carregamento → Chunks → Embeddings → ChromaDB
```

| Passo | Arquivo | O que faz |
|---|---|---|
| 1 | [`load_source_data_service.py`](src/service/load_source_data_service.py) | Carrega todos os PDFs da pasta `base_path_files/` usando PyPDF |
| 2 | [`generate_chunks_service.py`](src/service/generate_chunks_service.py) | Divide os documentos em chunks de 2000 caracteres com overlap de 500 |
| 3 | [`llm_factory.py`](src/dataprovider/llm_factory.py) | Gera embeddings para cada chunk |
| 4 | [`chroma_db.py`](src/dataprovider/chroma_db.py) | Persiste os chunks vetorizados no ChromaDB |

---

## Infraestrutura Docker

O projeto usa 4 containers orquestrados pelo Docker Compose:

| Container | Imagem | Porta | Função |
|---|---|---|---|
| `bank-score` | `litellm/litellm:latest` | 4000 | Proxy LLM com guardrail Presidio |
| `presidio-analyzer` | `mcr.microsoft.com/presidio-analyzer:latest` | 3000 | Detecta dados sensíveis (CPF) no texto |
| `presidio-anonymizer` | Build local (`anonymizer_proxy/`) | 3000 | Substitui CPF por `XXX.***.***-XX` |
| `presidio-anonymizer-upstream` | `mcr.microsoft.com/presidio-anonymizer:latest` | 3000 | Anonymizer original (fallback) |

O **Ollama** roda fora do Docker, diretamente na máquina local (porta 11434).

---

## Como Executar

### Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Ollama** instalado com o modelo Llama 3.2:
  ```bash
  ollama pull llama3.2
  ollama serve
  ```
- **Python 3.14** com **uv** (gerenciador de pacotes)

### Passo 1 — Subir a infraestrutura

```bash
docker compose up -d --build
```

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
# GET (usa CPF e valor padrão)
curl http://localhost:8000/

# POST (com dados customizados)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"cpf": "987.654.321-00", "valor": 5000.0}'
```

---

## Configuração

### Variáveis de Ambiente (`.env`)

| Variável | Exemplo | Descrição |
|---|---|---|
| `MODEL_NAME` | `ai-angelo-zero` | Nome do modelo registrado no LiteLLM |
| `API_KEY` | `api-key-angelo-1234` | Chave de API do LiteLLM |
| `BASE_URL` | `http://localhost:4000/v1` | URL do proxy LiteLLM |
| `BASE_PATH_FILES` | `base_path_files` | Pasta dos documentos fonte (PDFs) |
| `CHUNKS_DB_PATH` | `chunks_db` | Pasta do banco vetorial ChromaDB |

### LiteLLM (`config.yaml`)

```yaml
model_list:
  - model_name: ai-angelo-zero
    litellm_params:
      model: ollama/llama3.2
      api_base: "http://host.docker.internal:11434"
      drop_params: True
      temperature: 0

guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      default_on: true
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
      presidio_language: "en"
```

- `temperature: 0` faz o modelo gerar respostas determinísticas (sempre a mesma resposta para a mesma entrada)
- `mode: "pre_call"` significa que o mascaramento acontece antes de a mensagem ser enviada ao LLM
- `default_on: true` garante que o guardrail está sempre ativo, sem precisar ativá-lo por requisição

---

## Documentação Complementar

| Documento | O que explica |
|---|---|
| [LANGGRAPH_README.md](LANGGRAPH_README.md) | Como o LangGraph orquestra o fluxo com grafos de estado, nós, arestas condicionais e checkpoints |
| [PII_MASKING_README.md](PII_MASKING_README.md) | Como o mascaramento de CPF funciona na camada de infraestrutura com Presidio + LiteLLM |
