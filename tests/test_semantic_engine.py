import pytest


@pytest.mark.unit
def test_add_notices_calls_upsert(sample_notice, semantic_engine, fake_collection):
    semantic_engine.add_notices(sample_notice)
    fake_collection.upsert.assert_called_once()


@pytest.mark.unit
def test_search_returns_formatted_results(semantic_engine, fake_collection):
    result = semantic_engine.search("test", k=1)
    assert len(result) == 1
    assert result[0]["id"] == "1111"
    assert result[0]["score"] == 0.1
