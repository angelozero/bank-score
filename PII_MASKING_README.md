# 🔒 Mascaramento de CPF com Microsoft Presidio + LiteLLM

Este documento explica, passo a passo, como o CPF do cliente é mascarado automaticamente neste projeto — desde a entrada no `rag_service.py` até a resposta final da API.

---

## 📋 Visão Geral

O objetivo é garantir que **nenhum CPF real** chegue ao modelo de IA (LLM). O CPF `123.456.789-00` é automaticamente substituído por `XXX.***.***-XX` antes de ser enviado ao LLM, e a resposta final também contém apenas o CPF mascarado.

**Tecnologias utilizadas:**

| Tecnologia | Função |
|---|---|
| **LiteLLM** | Proxy que intermedia as chamadas ao LLM (Ollama/Llama 3.2) |
| **Microsoft Presidio Analyzer** | Detecta dados sensíveis (PII) no texto |
| **Microsoft Presidio Anonymizer** | Substitui os dados sensíveis por valores mascarados |
| **Anonymizer Proxy** (custom) | Proxy leve que permite customizar o formato da máscara |
| **Docker Compose** | Orquestra todos os containers |

---

## 🏗️ Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│  App Python  │────▶│   LiteLLM    │────▶│ Presidio Analyzer  │     │  Ollama LLM  │
│  (FastAPI)   │     │  (porta 4000)│     │   (porta 3000)     │     │ (porta 11434)│
└─────────────┘     └──────┬───────┘     └────────────────────┘     └──────────────┘
                           │                                              ▲
                           │  ┌─────────────────────┐                     │
                           └─▶│  Anonymizer Proxy   │                     │
                              │   (porta 3000)      │                     │
                              └─────────┬───────────┘                     │
                                        │                                 │
                              ┌─────────▼───────────┐                     │
                              │ Presidio Anonymizer  │                     │
                              │  Upstream (3000)     │                     │
                              └─────────────────────┘                     │
                                                                          │
                    LiteLLM envia o texto já mascarado ───────────────────┘
```

---

## 🔄 Fluxo Passo a Passo

### Passo 1 — O usuário faz uma requisição

O usuário chama a API (GET ou POST) com um CPF real:

```python
# app.py (linha 26)
return rag_langgraph_execute("123.456.789-00", 10000.0)
```

### Passo 2 — O `rag_service.py` monta a query

O serviço RAG recebe o CPF **sem máscara** e monta a query para buscar contexto:

```python
# src/service/rag_service.py
query = (
    f"Realize a auditoria de crédito para o valor de R$ {amount} "
    f"e CPF {cpf}. ..."
)
```

Neste ponto, o CPF ainda é `123.456.789-00`.

### Passo 3 — Busca de contexto (RAG)

O serviço busca documentos relevantes no ChromaDB e gera uma análise de risco:

```
[02] Busca por relevância no ChromaDB
[06] Monta o contexto
[07] Gera análise de risco (1ª chamada ao LLM via LiteLLM)
```

> ⚠️ **Importante:** Toda chamada ao LLM passa pelo LiteLLM proxy, que intercepta e mascara o CPF automaticamente.

### Passo 4 — LiteLLM intercepta a mensagem (Guardrail Presidio)

Quando o `rag_service.py` chama `llm.invoke(prompt)`, a requisição vai para o **LiteLLM proxy** (porta 4000). O LiteLLM tem um **guardrail** configurado que intercepta a mensagem **antes** de enviá-la ao LLM:

```yaml
# config.yaml
guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio          # Usa Microsoft Presidio
      mode: "pre_call"             # Intercepta ANTES de enviar ao LLM
      default_on: true             # Sempre ativo
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
      presidio_language: "en"
```

### Passo 5 — Presidio Analyzer detecta o CPF

O LiteLLM envia o texto para o **Presidio Analyzer** (container Docker), que analisa o texto procurando dados sensíveis.

O Analyzer usa um **recognizer customizado** definido em `presidio_ad_hoc_recognizers.json`:

```json
[
  {
    "name": "BrazilCpfRecognizer",
    "supported_language": "en",
    "patterns": [
      {
        "name": "cpf_with_dots",
        "regex": "\\d{3}\\.\\d{3}\\.\\d{3}-\\d{2}",
        "score": 1.0
      }
    ],
    "supported_entity": "BRAZIL_CPF"
  }
]
```

**Resultado:** O Analyzer retorna que encontrou a entidade `BRAZIL_CPF` na posição 19-33 do texto, com score 1.0.

```json
{
  "entity_type": "BRAZIL_CPF",
  "start": 19,
  "end": 33,
  "score": 1.0
}
```

### Passo 6 — Anonymizer Proxy substitui o CPF

O LiteLLM envia o texto + as entidades detectadas para o **Anonymizer Proxy** (nosso container customizado).

O proxy usa a **Python API** do Presidio Anonymizer com um operador customizado:

```python
# anonymizer_proxy/app.py
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

CUSTOM_OPERATORS = {
    "BRAZIL_CPF": OperatorConfig("replace", {"new_value": "XXX.***.***-XX"}),
}

engine = AnonymizerEngine()
result = engine.anonymize(text=text, analyzer_results=results, operators=CUSTOM_OPERATORS)
```

**Resultado:** O texto `"O CPF é 123.456.789-00"` vira `"O CPF é XXX.***.***-XX"`.

> 💡 **Por que o proxy?** A REST API do Presidio Anonymizer ignora o campo `operators` no JSON. Apenas a Python API respeita os operadores customizados. O proxy resolve isso usando a Python API diretamente.

### Passo 7 — LiteLLM envia o texto mascarado ao LLM

O LiteLLM recebe o texto já mascarado e envia ao **Ollama (Llama 3.2)**:

```
Mensagem enviada ao LLM:
"Identificador do Cliente: XXX.***.***-XX"
"Valor Solicitado: R$ 10000.0"
```

O LLM **nunca vê** o CPF real. Ele trabalha apenas com `XXX.***.***-XX`.

### Passo 8 — LLM gera a resposta

O LLM gera a resposta estruturada (JSON) com o CPF mascarado:

```json
{
  "answer": "REPORT: ... O identificador do cliente é XXX.***.***-XX ...",
  "client_cpf": "XXX.***.***-XX",
  "requested_amount": 10000.0,
  "sources": [...]
}
```

### Passo 9 — Resposta retorna ao usuário

O `rag_service.py` recebe a resposta do LLM e retorna ao `app.py`, que devolve ao usuário:

```json
{
  "data": {
    "answer": "REPORT: ...",
    "client_cpf": "XXX.***.***-XX",
    "requested_amount": 10000.0,
    "sources": [...]
  }
}
```

---

## 🐳 Containers Docker

| Container | Imagem | Porta | Função |
|---|---|---|---|
| `bank-score` | `litellm/litellm:latest` | 4000 | Proxy LLM com guardrail Presidio |
| `presidio-analyzer` | `mcr.microsoft.com/presidio-analyzer:latest` | 3000 | Detecta PII (CPF) no texto |
| `presidio-anonymizer` | Build local (`anonymizer_proxy/`) | 3000 | Substitui CPF por `XXX.***.***-XX` |
| `presidio-anonymizer-upstream` | `mcr.microsoft.com/presidio-anonymizer:latest` | 3000 | Anonymizer original (backup) |

Para subir tudo:

```bash
docker compose up -d --build
```

---

## 📁 Arquivos de Configuração

| Arquivo | O que faz |
|---|---|
| `config.yaml` | Configura o guardrail Presidio no LiteLLM |
| `presidio_ad_hoc_recognizers.json` | Define o regex para detectar CPF brasileiro |
| `anonymizer_proxy/app.py` | Proxy que aplica a máscara `XXX.***.***-XX` |
| `anonymizer_proxy/Dockerfile` | Container do proxy |
| `anonymizer_proxy/requirements.txt` | Dependências do proxy |
| `docker-compose.yaml` | Orquestra todos os containers |

---

## 🔑 Conceitos Importantes

### O que é PII?
**PII** (Personally Identifiable Information) são dados que identificam uma pessoa, como CPF, nome, telefone, e-mail, etc.

### O que é Microsoft Presidio?
É uma ferramenta open-source da Microsoft para **detectar e anonimizar** dados sensíveis em texto. Tem dois componentes:
- **Analyzer**: Detecta onde estão os dados sensíveis
- **Anonymizer**: Substitui os dados sensíveis por valores mascarados

### O que é LiteLLM?
É um proxy que fica entre sua aplicação e o LLM. Ele permite adicionar **guardrails** (proteções) como o Presidio, que interceptam as mensagens antes de chegarem ao modelo de IA.

### Por que não mascarar no código Python?
Porque o mascaramento na infraestrutura (LiteLLM + Presidio) é uma **camada de segurança independente**. Mesmo que alguém esqueça de mascarar no código, o Presidio vai interceptar e mascarar automaticamente. É uma proteção em profundidade (defense in depth).

---

## ✅ Resumo em uma frase

> O CPF entra como `123.456.789-00`, o **Presidio Analyzer** detecta que é um CPF, o **Anonymizer Proxy** substitui por `XXX.***.***-XX`, e o **LLM nunca vê o CPF real**.
