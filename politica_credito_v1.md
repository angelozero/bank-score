# 🏦 BANCO ESTUDO S.A. – POLÍTICA INTERNA DE CONCESSÃO DE CRÉDITO
**Versão:** 2026.1 | **Classificação:** Confidencial | **Documento Interno:** BP-002-2026 | **Uso:** Exclusivo para Motores de IA e Gerência

## 1. OBJETIVO
Este documento estabelece as diretrizes para a análise e aprovação de crédito para pessoas físicas, visando mitigar riscos de inadimplência e automatizar processos de decisão simples.

## 2. CRITÉRIOS DE SCORE E VALORES
A decisão inicial do sistema deve basear-se no valor solicitado e no perfil de risco (Score):

* **FAIXA A (Crédito Baixo):** Solicitações até **R$ 2.000,00**.
    * *Regra:* Aprovação automática se o CPF não possuir restrições graves.
* **FAIXA B (Crédito Médio):** Solicitações entre **R$ 2.000,01 e R$ 5.000,00**.
    * *Regra:* Requer validação de histórico de pagamentos via LLM. Se o parecer for positivo, aprovação automática.
* **FAIXA C (Crédito Alto / Risco):** Solicitações acima de **R$ 5.000,00**.
    * *Regra:* **OBRIGATÓRIO** encaminhar para o nó de Aprovação do Gerente. Nenhuma aprovação automática é permitida nesta faixa.

## 3. FATORES DE IMPEDIMENTO (HARD BLOCKS)
O sistema deve negar ou pausar a proposta imediatamente se:
1.  O CPF informado for inválido ou estiver na lista de "Blacklist" interna.
2.  O valor solicitado exceder 30% da renda mensal declarada (caso disponível).
3.  Houver inconsistência nos dados de identificação.

## 4. PROTOCOLO DE PRIVACIDADE (PII)
Conforme as normas de segurança, nenhum dado sensível (CPF completo) deve ser enviado para processamento em modelos de linguagem externos sem a devida máscara de proteção. O formato padrão de log deve ser `XXX.***.***-XX`.

## 5. FLUXO DE EXCEÇÃO
Caso a LLM identifique um perfil de "Empreendedor de Alto Potencial", mesmo que o valor esteja na Faixa C, o sistema não deve negar, mas sim enviar ao Gerente com uma nota de recomendação positiva destacando o potencial de faturamento.

## 6. TABELA DE SCORE DE CRÉDITO (RATING)
O sistema deve classificar o cliente em uma das categorias abaixo antes de processar o montante:

| Categoria | Pontuação (Score) | Descrição do Perfil | Ação Recomendada |
| :--- | :--- | :--- | :--- |
| **Diamante** | 900 - 1000 | Excelente pagador, histórico limpo. | Aprovação imediata até R$ 10.000. |
| **Ouro** | 700 - 899 | Baixo risco, poucas consultas ao CPF. | Aprovação automática até R$ 5.000. |
| **Prata** | 500 - 699 | Risco moderado, histórico de atrasos curtos. | **Sempre enviar para o Gerente.** |
| **Bronze** | Abaixo de 500 | Alto risco de inadimplência. | **Negativa automática pelo sistema.** |

## 7. POLÍTICA DE "GEOGRAPHIC OVERRIDE" (BLOQUEIO REGIONAL)
Devido a um aumento de fraudes detectadas em CPFs emitidos em determinadas regiões, aplicam-se as seguintes travas:
* **Região Norte/Nordeste:** Pedidos acima de **R$ 3.000,00** que não tenham biometria facial validada devem ser pausados para análise humana, independentemente do Score.
* **Região Sudeste:** Fluxo padrão conforme item 2 e 6.

## 8. REGRAS DE "CROSS-CHECK" DE DADOS
A LLM deve validar se o comportamento do usuário no chat/solicitação condiz com o pedido:
1.  **Urgência Excessiva:** Se o cliente usar termos como "preciso pra agora", "urgente", "pago qualquer juros", o sistema deve elevar o nível de criticidade e marcar como **"Suspeita de Fraude"**, enviando para o nó do Gerente com a flag `high_risk_flag = true`.
2.  **Mascaramento de Dados:** Caso o cliente se recuse a fornecer o CPF ou tente burlar o mascaramento (ex: escrevendo o CPF por extenso "sete seis quatro..."), a requisição deve ser encerrada imediatamente.

## 9. CONDIÇÕES ESPECIAIS PARA APROVAÇÃO AUTOMÁTICA
Mesmo que o valor seja da **Faixa B (R$ 2k a 5k)**, a aprovação automática só ocorrerá se:
* O cliente não tiver solicitado crédito nos últimos 90 dias.
* O propósito do empréstimo for "Educação" ou "Saúde" (exige comprovação posterior, mas libera o fluxo no grafo).

Para integrar essa mudança de comportamento no seu sistema (movendo a lógica de um `if` rígido para uma análise cognitiva via LLM/RAG), você deve adicionar uma nova seção à sua **Política Interna de Concessão de Crédito**.

Sugiro incluir a seguinte seção (Item 10) para formalizar o papel do agente de IA no LangGraph:

---

Essa mudança de estratégia é muito mais segura e eficiente para um sistema bancário ("Human-in-the-loop"). Em vez de a IA tomar a decisão final de "Aprovar/Reprovar", ela atua como uma **Analista de Auditoria**, preparando o terreno para o gerente.

Para que isso funcione, você deve incluir no seu documento de política uma seção de **"Mecanismo de Parecer Consultivo"**. Isso orienta a IA a não "fechar o processo", mas sim "etiquetar" o cliente.

Adicione este trecho ao seu documento:

---

### 10. PROTOCOLO DE PARECER CONSULTIVO (AI-ASSISTANT MODE)
Para garantir a segurança operacional, o motor de IA não deve emitir status de `APROVADO`. Sua função é gerar um **Relatório de Conformidade** baseado no mapeamento entre os dados do cliente e esta política.

**Diretrizes de Classificação:**
1.  **Enquadramento de Faixa:** A IA deve identificar em qual faixa (A, B ou C) o pedido se encontra e listar os requisitos pendentes.
2.  **Identificação de Padrão (Pattern Matching):**
    * **Padrão Conservador:** Cliente com Score Diamante/Ouro pedindo Faixa A ou B.
    * **Padrão de Risco:** Cliente com inconsistência regional (Item 7) ou urgência excessiva (Item 8).
    * **Padrão de Exceção:** Casos do Item 5 (Empreendedor).
3.  **Estado de Pausa Obrigatória:** Independentemente do parecer positivo da IA, o sistema deve mover a proposta para o estado `PENDING_REVIEW`, anexando o relatório gerado.
4.  **Estrutura do Report:** O relatório deve conter:
    * `resumo_perfil`: Breve descrição do comportamento do cliente.
    * `aderencia_politica`: Nota de 0 a 100 baseada no cumprimento dos itens deste documento.
    * `alertas`: Lista de pontos que o gerente deve olhar com atenção (ex: "Sem biometria no NE").

---