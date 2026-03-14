from __future__ import annotations

from typing import Any

import httpx

from app.common import settings


class SearchService:
    def __init__(self) -> None:
        self.provider = settings.search_provider.lower()
        self.tavily_api_key = settings.tavily_api_key
        self.serper_api_key = settings.serper_api_key
        
    async def search(self, query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
        if self.provider == "tavily":
            return await self._tavily_search(query, max_results=max_results)
        if self.provider == "serper":
            return await self._serper_search(query, max_results=max_results)
        raise RuntimeError(f"Unsupported search provider: {self.provider}")

    async def _tavily_search(self, query: str, *, max_results: int) -> list[dict[str, Any]]:
        if not self.tavily_api_key or self.tavily_api_key == "changeme":
            raise RuntimeError("Tavily API key not configured.")
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()
        return data.get("results", [])

    async def _serper_search(self, query: str, *, max_results: int) -> list[dict[str, Any]]:
        if not self.serper_api_key or self.serper_api_key == "changeme":
            raise RuntimeError("Serper API key not configured.")
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serper_api_key,
            "num": max_results,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://serpapi.com/search", params=params)
            response.raise_for_status()
            data = response.json()
        return data.get("organic_results", [])
