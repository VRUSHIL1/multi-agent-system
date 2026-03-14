from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.common import settings


@dataclass
class PDFIndexResult:
    index_path: str
    metadata_path: str
    chunk_count: int


class PDFEmbeddingService:
    def __init__(
        self,
        *,
        index_dir: str | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.index_dir = Path(index_dir or settings.pdf_index_dir)
        try:
            self.embedding_model = SentenceTransformer(
                embedding_model, local_files_only=True
            )
        except Exception:
            # First run: model not cached yet → download once
            self.embedding_model = SentenceTransformer(embedding_model)
        self.chunk_size = chunk_size or settings.pdf_chunk_size
        self.chunk_overlap = chunk_overlap or settings.pdf_chunk_overlap

    async def embed_pdf(self, file_path: str, *, index_name: str | None = None) -> PDFIndexResult:
        text = await self._extract_text(file_path)
        chunks = await self._chunk_text(text)
        if not chunks:
            raise ValueError("No extractable text found in PDF.")
        embeddings = await self._embed(chunks)

        await asyncio.to_thread(self.index_dir.mkdir, parents=True, exist_ok=True)
        index_basename = index_name or Path(file_path).stem
        index_path = str(self.index_dir / f"{index_basename}.faiss")
        metadata_path = str(self.index_dir / f"{index_basename}.json")

        index = faiss.IndexFlatL2(embeddings.shape[1])
        await asyncio.to_thread(index.add, embeddings)
        await asyncio.to_thread(faiss.write_index, index, index_path)

        metadata = [{"text": chunk, "source": os.path.basename(file_path)} for chunk in chunks]
        await asyncio.to_thread(self._write_metadata, metadata_path, metadata)

        return PDFIndexResult(index_path=index_path, metadata_path=metadata_path, chunk_count=len(chunks))

    async def search(self, query: str, *, index_path: str, metadata_path: str, top_k: int = 5) -> list[dict[str, Any]]:
        index = await asyncio.to_thread(faiss.read_index, index_path)
        metadata = await asyncio.to_thread(self._read_metadata, metadata_path)

        query_embedding = await self._embed([query])
        distances, indices = await asyncio.to_thread(index.search, query_embedding, top_k)

        results = []
        for score, idx in zip(distances[0], indices[0], strict=False):
            if idx < 0:
                continue
            chunk = metadata[idx]
            results.append({
                "score": float(score),
                "text": chunk.get("text"),
                "source": chunk.get("source"),
            })
        return results

    async def _extract_text(self, file_path: str) -> str:
        def _read_pdf():
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            # Extract text from all pages and join with newlines
            return "\n".join(page.get_text() for page in doc)
        
        return await asyncio.to_thread(_read_pdf)

    async def _chunk_text(self, text: str) -> list[str]:
        def _chunk():
            if not text:
                return []
            chunks: list[str] = []
            start = 0
            length = len(text)
            while start < length:
                end = min(start + self.chunk_size, length)
                chunk = text[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                start += max(self.chunk_size - self.chunk_overlap, 1)
            return chunks
        
        return await asyncio.to_thread(_chunk)

    async def _embed(self, texts: list[str]) -> np.ndarray:
        def _encode():
            embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
            return np.asarray(embeddings, dtype="float32")
        
        return await asyncio.to_thread(_encode)

    def _write_metadata(self, metadata_path: str, metadata: list[dict]) -> None:
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)

    def _read_metadata(self, metadata_path: str) -> list[dict]:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            return json.load(handle)


# ── Singleton accessor ──────────────────────────────────────────────
_pdf_service_instance: PDFEmbeddingService | None = None


def get_pdf_service() -> PDFEmbeddingService:
    """Return the shared PDFEmbeddingService (creates it on first call)."""
    global _pdf_service_instance
    if _pdf_service_instance is None:
        _pdf_service_instance = PDFEmbeddingService()
    return _pdf_service_instance
