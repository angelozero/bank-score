def get_context_by_results(results):
    print("[06] - Obtendo contexto pelos resultados...")
    if not results or results[0][1] < 0.2:
        print(f"\n\nNão foi possível encontrar resultados relevantes.\n\n")
        return

    return "\n".join([doc.page_content for doc, _score in results])