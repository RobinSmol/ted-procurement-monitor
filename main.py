"""CLI entry point — runs the daily ETL pipeline for today's date."""
from datetime import date

import chromadb
import torch
from chromadb.utils import embedding_functions

from src.core.config import settings
from src.core.email_service import EmailService
from src.core.enums import SourceNames, StorageConfig
from src.core.logger import setup_logger
from src.extraction.ted_api import TEDExtractor
from src.pipeline.notice_transformer import NoticeTransformer
from src.pipeline.pipeline import DataPipeline
from src.search.search_service import SearchService
from src.search.semantic_search import SemanticEngine
from src.storage.db_manager import DBManager

logger = setup_logger()


if __name__ == "__main__":
    logger.info("-----Start of the App-----")

    ted_extractor = TEDExtractor(settings, SourceNames.TED)
    db = DBManager(settings.ted_db_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    client = chromadb.PersistentClient(str(settings.chroma_db_path))
    notice_transformer = NoticeTransformer()
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model_name, device=device
    )
    chroma = SemanticEngine(
        client=client,
        embedding_func=embedding_func,
        collection_name=StorageConfig.CHROMA_COLLECTION,
    )
    search_service = SearchService(db=db, search_engine=chroma, settings=settings)
    email_service = EmailService(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_login=settings.smtp_login,
        smtp_password=settings.smtp_password,
        sender_email=settings.sender_email,
        dashboard_url=settings.dashboard_url,
    )
    pipeline = DataPipeline(
        extractors=[ted_extractor],
        db=db,
        search_engine=chroma,
        transformer=notice_transformer,
        search_service=search_service,
        email_service=email_service,
    )

    pipeline.run(date.today())

    logger.info("-----End of the App-----")
