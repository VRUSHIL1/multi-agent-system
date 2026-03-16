from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    @staticmethod
    def _require(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} environment variable is not set")
        return value

    @property
    def database_url(self) -> str:
        return self._require("DATABASE_URL")
    
    @property
    def mail_username(self) -> str:
        return self._require("SMTP_USERNAME")

    @property
    def mail_password(self) -> str:
        return self._require("SMTP_PASSWORD")

    @property
    def mail_from(self) -> str:
        return self._require("SMTP_FROM")

    @property
    def mail_host(self) -> str:
        return self._require("SMTP_HOST")

    @property
    def mail_port(self) -> str:
        return self._require("SMTP_PORT")
    
    @property
    def gemini_api_key(self) -> str:
        return self._require("GEMINI_API_KEY")
    
    @property
    def gemini_model(self) -> str:
        return self._require("GEMINI_MODEL")
    
    @property
    def search_provider(self) -> str:
        return self._require("SEARCH_PROVIDER")
    
    @property
    def tavily_api_key(self) -> str:
        value = os.getenv("TAVILY_API_KEY")
        if not value:
            # Fallback to optional for search functionality
            return ""
        return value
    
    @property
    def serper_api_key(self) -> str:
        value = os.getenv("SERPER_API_KEY")
        if not value:
            # Fallback to optional for search functionality
            return ""
        return value
    
    @property
    def pdf_index_dir(self) -> str:
        return self._require("PDF_INDEX_DIR")
    
    @property
    def pdf_chunk_size(self) -> int:
        return int(self._require("PDF_CHUNK_SIZE"))
    
    @property
    def pdf_chunk_overlap(self) -> int:
        return int(self._require("PDF_CHUNK_OVERLAP"))

    @property
    def secret_key(self) -> str:
        return self._require("SECRET_KEY")

    @property
    def mem0_api_key(self) -> str:
        return self._require("MEM0_API_KEY")

    

    

settings = Settings()