from src.service.get_chat_model import get_chat_model
from src.agent.agent_langgraph_model import LangGraphAgentResponse


def get_llm_with_tools(tool):
    print("[09] - Inicializando LLM com ferramentas...")
    model = get_chat_model()
    llm = model.bind_tools([tool])
    return llm.with_structured_output(LangGraphAgentResponse)
