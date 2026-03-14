from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.services.email_service import EmailService
from app.services.pdf_service import PDFEmbeddingService, get_pdf_service
from app.services.search_service import SearchService


class EmailInput(BaseModel):
    to_address: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject")
    body: str = Field(description="Email body content")
    is_html: bool = Field(default=False, description="Whether the body is HTML")


class SearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum number of results")


class PDFSearchInput(BaseModel):
    query: str = Field(description="Search query for PDF content")
    top_k: int = Field(default=5, description="Number of top results to return")


class EmailTool(BaseTool):
    name: str = "send_email"
    description: str = "Send an email to a specified recipient"
    args_schema: type[BaseModel] = EmailInput
    email_service: EmailService = Field(default_factory=EmailService)

    def _run(self, to_address: str, subject: str, body: str, is_html: bool = False) -> str:
        try:
            self.email_service.send_email(to_address, subject, body, is_html=is_html)
            return f"Email sent successfully to {to_address}"
        except Exception as e:
            return f"Failed to send email: {str(e)}"


class SearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for information"
    args_schema: type[BaseModel] = SearchInput
    search_service: SearchService = Field(default_factory=SearchService)

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            results = asyncio.run(self.search_service.search(query, max_results=max_results))
            if not results:
                return "No search results found"
            
            formatted_results = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "No URL")
                content = result.get("content", result.get("snippet", "No content"))
                formatted_results.append(f"{i}. {title}\n   URL: {url}\n   Content: {content[:200]}...")
            
            return "\n\n".join(formatted_results)
        except Exception as e:
            return f"Search failed: {str(e)}"


class PDFSearchTool(BaseTool):
    name: str = "search_pdf"
    description: str = (
        "Search through all uploaded PDF documents for relevant content. "
        "Use this when the user asks about their uploaded documents. "
        "Only requires a search query — paths are resolved automatically."
    )
    args_schema: type[BaseModel] = PDFSearchInput
    pdf_service: PDFEmbeddingService = Field(default_factory=get_pdf_service)

    def _run(self, query: str, top_k: int = 5) -> str:
        try:
            index_dir = Path(self.pdf_service.index_dir)
            faiss_files = list(index_dir.glob("*.faiss"))

            if not faiss_files:
                return "No documents have been uploaded yet."

            all_results: list[dict] = []
            for faiss_file in faiss_files:
                metadata_file = faiss_file.with_suffix(".json")
                if not metadata_file.exists():
                    continue
                results = asyncio.run(
                    self.pdf_service.search(
                        query,
                        index_path=str(faiss_file),
                        metadata_path=str(metadata_file),
                        top_k=top_k,
                    )
                )
                all_results.extend(results)

            # Sort by score (lower = more similar for L2) and keep top_k
            all_results.sort(key=lambda r: r.get("score", float("inf")))
            all_results = all_results[:top_k]

            if not all_results:
                return "No relevant content found in uploaded documents."

            formatted_results = []
            for i, result in enumerate(all_results, 1):
                score = result.get("score", 0)
                text = result.get("text", "")
                source = result.get("source", "Unknown")
                formatted_results.append(
                    f"{i}. Source: {source} (Score: {score:.3f})\n   Content: {text[:300]}..."
                )

            return "\n\n".join(formatted_results)
        except Exception as e:
            return f"PDF search failed: {str(e)}"


def get_langchain_tools() -> list[BaseTool]:
    """Return a list of all available LangChain tools."""
    return [
        EmailTool(),
        SearchTool(),
        PDFSearchTool(),
    ]