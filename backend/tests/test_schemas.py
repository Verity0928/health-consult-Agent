from app.schemas import LLMConfig


def test_llm_config_embedding_model_defaults_to_empty_string():
    config = LLMConfig(base_url="https://api.openai.com/v1", api_key="k", model="gpt-4o-mini")
    assert config.embedding_model == ""
