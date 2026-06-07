from unittest.mock import MagicMock

import pytest

from src.core.config import AppSettings
from src.core.enums import NoticeField
from src.search.search_service import SearchService
from src.search.semantic_search import SemanticEngine
from src.storage.db_manager import DBManager


@pytest.fixture
def db():
    """
    Returns a DBManager backed by an in-memory SQLite database."""
    return DBManager(db_path=":memory:")


@pytest.fixture
def valid_settings():
    """Returns an AppSettings instance with defaults and no .env file."""
    return AppSettings(_env_file=None)


@pytest.fixture
def sample_notice():
    """Returns a single-element list containing a minimal valid notice dict."""
    notice = {
        NoticeField.ID: "1111",
        NoticeField.TITLE: "Test title",
        NoticeField.PUB_DATE: "20260510",
        NoticeField.COUNTRY: "FRA",
        NoticeField.ESTIMATED_VALUE: None,
        NoticeField.CURRENCY: None,
        NoticeField.ESTIMATED_VALUE_EUR: None,
        NoticeField.DESCRIPTION: None,
        NoticeField.CPV: None,
        NoticeField.SOURCE_NAME: "test",
    }
    return [notice]


@pytest.fixture
def fake_collection():
    """Returns a mocked ChromaDB collection with hardcoded query results."""
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"ids": [["1111"]], "distances": [[0.1]]}
    return fake_collection


@pytest.fixture
def semantic_engine(fake_collection):
    """Returns a SemanticEngine wired with a mocked client and embedding function."""
    fake_client = MagicMock()
    fake_client.get_or_create_collection.return_value = fake_collection
    fake_embedding_func = MagicMock()
    return SemanticEngine(
        client=fake_client,
        embedding_func=fake_embedding_func,
        collection_name="test_collection",
    )


@pytest.fixture
def search_service(valid_settings):
    """Returns a tuple of SearchService and its two mock dependencies (db, engine)."""
    mock_db = MagicMock()
    mock_engine = MagicMock()
    service = SearchService(
        db=mock_db, search_engine=mock_engine, settings=valid_settings
    )
    return service, mock_db, mock_engine
