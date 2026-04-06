# 🔒 Mascaramento de CPF — Proteção Automática na Camada de Infraestrutura

Este documento explica como o CPF do cliente é mascarado automaticamente nesta aplicação, desde a entrada na API até a resposta final. O mascaramento acontece fora do código Python, na camada de infraestrutura, usando Microsoft Presidio + LiteLLM.

---

## O Problema

Quando uma aplicação envia dados para um modelo de IA (LLM), tudo que está no texto é processado pelo modelo. Se o texto contém um CPF real como `123.456.789-00`, o modelo recebe, processa e pode até reproduzir esse dado na resposta.

Isso é um problema de privacidade. A LGPD (Lei Geral de Proteção de Dados) exige que dados pessoais sensíveis sejam protegidos. O CPF é um dado que identifica uma pessoa de forma única — é o que se chama de **PII** (Personally Identifiable Information, ou Informação de Identificação Pessoal).

## A Solução — Defense in Depth

Em vez de mascarar o CPF no código Python (onde um desenvolvedor pode esquecer de fazer), o mascaramento é feito na **infraestrutura**. Toda chamada ao LLM passa por um proxy (LiteLLM) que intercepta o texto e substitui o CPF automaticamente antes de enviar ao modelo.

Isso é um padrão de segurança chamado **Defense in Depth** (defesa em profundidade): a proteção não depende de uma única camada. Mesmo que o código Python envie o CPF real, a infraestrutura intercepta e protege.

Resultado:
- O código Python **não precisa se preocupar** com mascaramento
- Mesmo que alguém esqueça de mascarar, o Presidio intercepta automaticamente
- O LLM **nunca recebe** o CPF real
- A resposta final contém apenas `XXX.***.***-XX`

---

## Arquitetura do Mascaramento

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────────┐
│  App Python │────▶│   LiteLLM    │────▶│ Presidio Analyzer  │     │  Ollama LLM  │
│  (FastAPI)  │     │  (porta 4000)│     │   (porta 3000)     │     │ (porta 11434)│
└─────────────┘     └──────┬───────┘     └────────────────────┘     └──────────────┘
                           │                                              ▲
                           │  ┌─────────────────────┐                     │
                           └─▶│  Anonymizer Proxy   │                     │
                              │   (porta 3000)      │                     │
                              └─────────┬───────────┘                     │
                                        │                                 │
                              ┌─────────▼───────────┐                     │
                              │ Presidio Anonymizer │                     │
                              │  Upstream (3000)    │                     │
                              └─────────────────────┘                     │
                                                                          │
                    LiteLLM envia o texto já mascarado ───────────────────┘
```

São 4 containers Docker trabalhando juntos:

| Container | Imagem | O que faz |
|---|---|---|
| `bank-score` | `litellm/litellm:latest` | Proxy que intercepta chamadas ao LLM e aplica o guardrail |
| `presidio-analyzer` | `mcr.microsoft.com/presidio-analyzer:latest` | Analisa o texto e detecta onde estão os dados sensíveis |
| `presidio-anonymizer` | Build local ([`anonymizer_proxy/`](anonymizer_proxy/)) | Substitui os dados detectados pela máscara customizada |
| `presidio-anonymizer-upstream` | `mcr.microsoft.com/presidio-anonymizer:latest` | Anonymizer original da Microsoft (usado como fallback) |

---

## Fluxo

### Passo 1 — O usuário faz uma requisição

O usuário chama a API com um CPF real:

```python
# app.py
return rag_langgraph_execute("123.456.789-00", 10000.0)
```

### Passo 2 — O serviço RAG monta a query com o CPF real

O [`rag_service.py`](src/service/rag_service.py) recebe o CPF sem máscara e monta a query:

```python
# src/service/rag_service.py
query = (
    f"Realize a auditoria de crédito para o valor de R$ {amount} "
    f"e CPF {cpf}. ..."
)
```

Neste ponto, o CPF ainda é `123.456.789-00`. O código Python não faz nenhum mascaramento — ele confia na infraestrutura.

### Passo 3 — A chamada ao LLM passa pelo LiteLLM

Quando o [`rag_service.py`](src/service/rag_service.py) chama `llm.invoke(prompt)`, a requisição não vai direto para o Ollama. Ela vai para o **LiteLLM proxy** (porta 4000), porque o modelo foi configurado com `base_url=http://localhost:4000/v1` no [`llm_factory.py`](src/dataprovider/llm_factory.py).

### Passo 4 — LiteLLM ativa o guardrail Presidio

O LiteLLM tem um **guardrail** configurado no [`config.yaml`](config.yaml) que intercepta a mensagem **antes** de enviá-la ao LLM:

```yaml
# config.yaml
guardrails:
  - guardrail_name: "pii-masking"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      default_on: true
      presidio_analyzer_api_base: "http://presidio-analyzer:3000"
      presidio_anonymizer_api_base: "http://presidio-anonymizer:3000"
      presidio_ad_hoc_recognizers: "/app/presidio_ad_hoc_recognizers.json"
      output_parse_pii: false
      presidio_language: "en"
```

Cada configuração tem uma função:

| Parâmetro | Valor | O que faz |
|---|---|---|
| `mode` | `"pre_call"` | Intercepta **antes** de enviar ao LLM (não depois) |
| `default_on` | `true` | O guardrail está sempre ativo, sem precisar ativá-lo por requisição |
| `presidio_ad_hoc_recognizers` | caminho do JSON | Arquivo com o regex customizado para detectar CPF brasileiro |
| `output_parse_pii` | `false` | Não tenta desmascarar na resposta (o CPF fica mascarado para sempre) |
| `presidio_language` | `"en"` | Idioma do Presidio (o recognizer customizado está registrado como "en") |

### Passo 5 — Presidio Analyzer detecta o CPF

O LiteLLM envia o texto para o **Presidio Analyzer**, que analisa o conteúdo procurando dados sensíveis.

O Analyzer usa um **recognizer customizado** definido em [`presidio_ad_hoc_recognizers.json`](presidio_ad_hoc_recognizers.json):

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
      },
      {
        "name": "cpf_digits_only",
        "regex": "\\b\\d{11}\\b",
        "score": 0.6
      }
    ],
    "supported_entity": "BRAZIL_CPF"
  }
]
```

O recognizer tem dois padrões:

| Padrão | Regex | Score | Exemplo |
|---|---|---|---|
| `cpf_with_dots` | `\d{3}\.\d{3}\.\d{3}-\d{2}` | 1.0 (certeza total) | `123.456.789-00` |
| `cpf_digits_only` | `\b\d{11}\b` | 0.6 (possível CPF) | `12345678900` |

O score indica a confiança da detecção. O formato com pontos e traço tem score 1.0 porque é inequivocamente um CPF. O formato só com dígitos tem score 0.6 porque pode ser outro número de 11 dígitos.

O Analyzer retorna a posição exata do CPF no texto:

```json
{
  "entity_type": "BRAZIL_CPF",
  "start": 19,
  "end": 33,
  "score": 1.0
}
```

### Passo 6 — Anonymizer Proxy substitui o CPF

O LiteLLM envia o texto e as entidades detectadas para o **Anonymizer Proxy** ([`anonymizer_proxy/app.py`](anonymizer_proxy/app.py)).

Este proxy existe por um motivo técnico: a REST API oficial do Presidio Anonymizer **ignora** o campo `operators` no JSON da requisição. Isso significa que não é possível customizar o formato da máscara via REST. A Python API do Presidio, por outro lado, respeita os operadores customizados.

O proxy resolve isso usando a Python API diretamente:

```python
# anonymizer_proxy/app.py
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig

CUSTOM_OPERATORS = {
    "BRAZIL_CPF": OperatorConfig("replace", {"new_value": "XXX.***.***-XX"}),
}

engine = AnonymizerEngine()

@app.post("/anonymize")
async def anonymize(request: Request):
    payload = await request.json()
    text = payload.get("text", "")
    analyzer_results_raw = payload.get("analyzer_results", [])

    # Converte os dicts em objetos RecognizerResult
    analyzer_results = []
    for item in analyzer_results_raw:
        analyzer_results.append(
            RecognizerResult(
                entity_type=item["entity_type"],
                start=item["start"],
                end=item["end"],
                score=item.get("score", 1.0),
            )
        )

    # Anonimiza usando a Python API com operadores customizados
    result = engine.anonymize(
        text=text,
        analyzer_results=analyzer_results,
        operators=dict(CUSTOM_OPERATORS),
    )

    return JSONResponse(content={
        "text": result.text,
        "items": [...]
    })
```

O `OperatorConfig("replace", {"new_value": "XXX.***.***-XX"})` diz ao Presidio: "quando encontrar uma entidade do tipo `BRAZIL_CPF`, substitua pelo texto `XXX.***.***-XX`".

Qualquer requisição que não seja para `/anonymize` é encaminhada para o Anonymizer original (upstream):

```python
# anonymizer_proxy/app.py
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_all(path: str, request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=f"{ANONYMIZER_UPSTREAM}/{path}",
            content=body,
            headers={...},
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
```

**Resultado:** O texto `"O CPF é 123.456.789-00"` vira `"O CPF é XXX.***.***-XX"`.

### Passo 7 — LiteLLM envia o texto mascarado ao LLM

O LiteLLM recebe o texto já mascarado e envia ao Ollama (Llama 3.2):

```
Mensagem enviada ao LLM:
"Identificador do Cliente: XXX.***.***-XX"
"Valor Solicitado: R$ 10000.0"
```

O LLM nunca vê o CPF real. Ele trabalha apenas com `XXX.***.***-XX`.

### Passo 8 — LLM gera a resposta com CPF mascarado

O prompt do sistema ([`get_risk_analysis_prompt.py`](src/service/get_risk_analysis_prompt.py)) instrui a IA a copiar exatamente o identificador mascarado recebido:

```
"No campo 'client_cpf' da resposta, copie EXATAMENTE o identificador mascarado
recebido (ex: XXX.***.***-XX). Nunca substitua por outro texto."
```

A resposta da IA já vem com o CPF mascarado:

```json
{
  "answer": "REPORT: O identificador do cliente é XXX.***.***-XX ...",
  "client_cpf": "XXX.***.***-XX",
  "requested_amount": 10000.0,
  "sources": [...]
}
```

### Passo 9 — Resposta retorna ao usuário

O [`rag_service.py`](src/service/rag_service.py) recebe a resposta do LLM e retorna ao [`app.py`](app.py), que devolve ao usuário:

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

## Resumo Visual do Mascaramento

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

---

## Containers Docker

Os containers são definidos no [`docker-compose.yaml`](docker-compose.yaml):

```yaml
services:
  litellm:
    image: litellm/litellm:latest
    container_name: bank-score
    ports:
      - "4000:4000"
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./presidio_ad_hoc_recognizers.json:/app/presidio_ad_hoc_recognizers.json
    environment:
      - PRESIDIO_ANALYZER_API_BASE=http://presidio-analyzer:3000
      - PRESIDIO_ANONYMIZER_API_BASE=http://presidio-anonymizer:3000
    command: ["--config", "/app/config.yaml", "--detailed_debug"]
    depends_on:
      - presidio-analyzer
      - presidio-anonymizer

  presidio-analyzer:
    image: mcr.microsoft.com/presidio-analyzer:latest
    container_name: presidio-analyzer

  presidio-anonymizer-upstream:
    image: mcr.microsoft.com/presidio-anonymizer:latest
    container_name: presidio-anonymizer-upstream

  presidio-anonymizer:
    build: ./anonymizer_proxy
    container_name: presidio-anonymizer
    environment:
      - ANONYMIZER_UPSTREAM=http://presidio-anonymizer-upstream:3000
    depends_on:
      - presidio-anonymizer-upstream
```

A ordem de dependência é:

1. `presidio-anonymizer-upstream` sobe primeiro (Anonymizer original da Microsoft)
2. `presidio-anonymizer` sobe depois (nosso proxy que usa o upstream como fallback)
3. `presidio-analyzer` sobe (detector de PII)
4. `litellm` sobe por último (depende do analyzer e do anonymizer)

Para subir tudo:

```bash
docker compose up -d --build
```

---

## Arquivos de Configuração

| Arquivo | O que faz |
|---|---|
| [`config.yaml`](config.yaml) | Configura o guardrail Presidio no LiteLLM |
| [`presidio_ad_hoc_recognizers.json`](presidio_ad_hoc_recognizers.json) | Define o regex para detectar CPF brasileiro |
| [`anonymizer_proxy/app.py`](anonymizer_proxy/app.py) | Proxy que aplica a máscara `XXX.***.***-XX` via Python API |
| [`anonymizer_proxy/Dockerfile`](anonymizer_proxy/Dockerfile) | Container do proxy (Python 3.11 slim) |
| [`anonymizer_proxy/requirements.txt`](anonymizer_proxy/requirements.txt) | Dependências do proxy (FastAPI, httpx, presidio-anonymizer) |
| [`docker-compose.yaml`](docker-compose.yaml) | Orquestra os 4 containers |

---

## Conceitos Utilizados

### O que é PII?

**PII** (Personally Identifiable Information) são dados que identificam uma pessoa de forma única. Exemplos: CPF, nome completo, telefone, e-mail, endereço. Nesta aplicação, o dado protegido é o CPF.

### O que é Microsoft Presidio?

É uma ferramenta open-source da Microsoft para detectar e anonimizar dados sensíveis em texto. Tem dois componentes:

- **Analyzer**: recebe um texto e retorna a lista de entidades sensíveis encontradas, com posição e score de confiança
- **Anonymizer**: recebe o texto e a lista de entidades, e substitui cada uma por um valor mascarado

### O que é um Recognizer?

É uma regra que ensina o Presidio a detectar um tipo específico de dado. O Presidio já vem com recognizers para dados americanos (SSN, telefone, etc.), mas não reconhece CPF brasileiro. Por isso, esta aplicação define um **recognizer customizado** via JSON com regex.

### O que é um Operator?

É a regra que define como o dado detectado será substituído. O operador `replace` substitui o texto por um valor fixo. Nesta aplicação, o operador substitui qualquer CPF por `XXX.***.***-XX`.

### O que é LiteLLM?

É um proxy que fica entre a aplicação e o LLM. Ele expõe uma API compatível com OpenAI, o que permite trocar o modelo (Ollama, OpenAI, Anthropic, etc.) sem mudar o código. Além disso, permite adicionar **guardrails** — proteções que interceptam as mensagens antes ou depois de chegarem ao modelo.

### O que é um Guardrail?

É uma camada de proteção que intercepta as mensagens trocadas entre a aplicação e o LLM. Nesta aplicação, o guardrail `pii-masking` usa o Presidio para detectar e mascarar CPFs antes de o texto chegar ao modelo. O modo `pre_call` significa que a interceptação acontece antes do envio.

### Por que um Proxy em vez de mascarar no código?

Três motivos:

1. **Segurança**: mesmo que um desenvolvedor esqueça de mascarar, a infraestrutura protege
2. **Separação de responsabilidades**: o código Python cuida da lógica de negócio, a infraestrutura cuida da segurança
3. **Centralização**: se amanhã for necessário mascarar outro dado (telefone, e-mail), basta adicionar um recognizer no JSON — sem alterar nenhuma linha de Python

### Por que o Anonymizer Proxy existe?

A REST API oficial do Presidio Anonymizer tem uma limitação: ela ignora o campo `operators` no JSON da requisição. Isso significa que não é possível definir uma máscara customizada (`XXX.***.***-XX`) via REST — o Presidio usaria o formato padrão dele.

A Python API do Presidio, por outro lado, aceita operadores customizados. O proxy resolve essa limitação: ele recebe a requisição REST do LiteLLM, usa a Python API internamente para aplicar a máscara customizada, e retorna o resultado no mesmo formato da REST API.

---

## Resumo

> O CPF entra como `123.456.789-00` → o **LiteLLM** intercepta a chamada → o **Presidio Analyzer** detecta que é um CPF → o **Anonymizer Proxy** substitui por `XXX.***.***-XX` → o **LLM nunca vê o CPF real** → a resposta final contém apenas o CPF mascarado.
