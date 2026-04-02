from state import graph, CreditState

def execute_test():
    # --- EXECUÇÃO NO TERMINAL ---

    # 1. Simulando entrada de um valor ALTO (> 5000) para forçar a pausa
    config = {"configurable": {"thread_id": "user_01"}}
    input_data = {
        "cpf_original": "123.456.789-00",
        "amount": 7500.0,
        "messages": []
    }

    print("\n=== INICIANDO FLUXO DE CRÉDITO ===")
    # O invoke vai rodar até encontrar o 'interrupt_before' no nó B
    response = graph.invoke(input_data, config)

    print("\n--- ESTADO APÓS A PRIMEIRA EXECUÇÃO (PAUSADO) ---")
    print(f"CPF Protegido: {response.get('cpf_masked')}")
    print(f"Status da Análise: {response.get('status_analise')}")
    print(f"Histórico de Mensagens: {response.get('messages')}")

    # Verificando se há um próximo passo pendente (o nó B)
    snapshot = graph.get_state(config)
    print(f"\nPróximo nó na fila: {snapshot.next}")

    print("\n--- SIMULANDO APROVAÇÃO DO GERENTE ---")
    # O gerente "acorda" o grafo
    graph.invoke(None, config)
    

    final_state = graph.get_state(config).values
    print("\n=== ESTADO FINAL DO OBJETO NO TERMINAL ===")
    print(final_state)

def execute_manager_aproval_test(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n=== [GERENTE] ACESSANDO PROPOSTA: {thread_id} ===")
    
    # 1. O Gerente visualiza como está o estado atual
    current_state = graph.get_state(config)
    print(f"Valor solicitado: {current_state.values.get('amount')}")
    print(f"Análise da IA: {current_state.values.get('analysis_report')}")

    # 2. O Gerente decide aprovar (Intervenção Manual)
    # Nós atualizamos o campo 'is_approved' diretamente no banco de checkpoints
    print("\n[Gerente]: 'Análise ok, vou aprovar este crédito.'")
    graph.update_state(config, {"is_approved": True})

    # 3. O Gerente manda o grafo CONTINUAR
    # Passamos 'None' porque não estamos iniciando um novo fluxo, 
    # estamos apenas retomando o que estava pausado.
    graph.invoke(None, config)

    # 4. Verificação Final
    final_snapshot = graph.get_state(config)
    print("\n=== FLUXO FINALIZADO PELO GERENTE ===")
    print(f"Status Final de Aprovação: {final_snapshot.values.get('is_approved')}")
    print(f"Mensagens Finais: {final_snapshot.values.get('messages')[-1]}")

if __name__ == "__main__":
    execute_test()
    execute_manager_aproval_test("user_01")