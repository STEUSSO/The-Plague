"""
Async API Client for the Dennis Reep Dead by Daylight API v3.
Features in-memory TTL caching and fuzzy search.
"""
import time
import urllib.parse
import difflib
from typing import Optional, Dict, Any, List, Tuple
import aiohttp
from constants import normalize_text, resolve_killer, KILLERS_DB

BASE_URL = "https://dennisreep.nl/dbd/api/v3"
DEFAULT_HEADERS = {
    "User-Agent": "ThePlague-DiscordBot/2.0 (DBD Assistant; Python 3.14)"
}

class DBDClient:
    def __init__(self, cache_ttl: int = 1800):  # 30 min cache TTL
        self.cache_ttl = cache_ttl
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Tuple[float, Any]] = {}
        # Pre-warmed index for autocomplete
        self._all_perks_cache: Optional[List[Dict[str, Any]]] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=12)
            self._session = aiohttp.ClientSession(headers=DEFAULT_HEADERS, timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            timestamp, data = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: Any):
        self._cache[key] = (time.time(), data)

    async def get_all_killers(self) -> List[Dict[str, Any]]:
        """Fetch all killers with their overall rating and tier."""
        cache_key = "all_killers"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        session = await self.get_session()
        url = f"{BASE_URL}/getKillerData"
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            killers = data.get("Killers", [])
            self._set_cache(cache_key, killers)
            return killers

    async def get_killer_stats(self, api_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve overall killer info (Image, Tier, Rating, Ratings) by killer API name."""
        all_killers = await self.get_all_killers()
        norm_name = api_name.lower().strip()
        for k in all_killers:
            if k["KillerName"].lower().strip() == norm_name:
                return k
        return None

    async def get_killer_build(self, killer_api_name: str) -> List[Dict[str, Any]]:
        """
        Fetch ranked perks for a specific killer from Dennis Reep API.
        URL format: getKillerData/?killer={KillerName}
        """
        cache_key = f"killer_build_{killer_api_name}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        encoded_name = urllib.parse.quote(killer_api_name)
        url = f"{BASE_URL}/getKillerData/?killer={encoded_name}"
        session = await self.get_session()
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            perks = data.get("Killers")
            if not perks:
                perks = []
            self._set_cache(cache_key, perks)
            return perks

    async def get_perks(self, role: str = "Killer") -> List[Dict[str, Any]]:
        """
        Fetch all perks for either Killer or Survivor.
        role: 'Killer' or 'Survivor'
        """
        role_key = "Killer" if "kill" in role.lower() else "Survivor"
        cache_key = f"all_perks_{role_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        url = f"{BASE_URL}/get{role_key}PerkData"
        session = await self.get_session()
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            perks = data.get("Perks", [])
            # Store role marker inside each perk object for convenience
            for p in perks:
                p["Role"] = role_key
            self._set_cache(cache_key, perks)
            return perks

    async def get_all_perks_combined(self) -> List[Dict[str, Any]]:
        """Fetch and combine both Killer and Survivor perks."""
        killer_perks = await self.get_perks("Killer")
        survivor_perks = await self.get_perks("Survivor")
        return killer_perks + survivor_perks

    async def search_perk(self, query: str, role: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Intelligently searches for a perk by name with normalization and fuzzy matching.
        """
        if not query:
            return None

        if role:
            perks = await self.get_perks(role)
        else:
            perks = await self.get_all_perks_combined()

        norm_query = normalize_text(query)

        # 1. Exact match on normalized perk name
        for p in perks:
            if normalize_text(p["PerkName"]) == norm_query:
                return p

        # 2. Substring match
        for p in perks:
            norm_name = normalize_text(p["PerkName"])
            if norm_query in norm_name or norm_name in norm_query:
                return p

        # 3. Fuzzy match with difflib
        name_map = {normalize_text(p["PerkName"]): p for p in perks}
        matches = difflib.get_close_matches(norm_query, list(name_map.keys()), n=1, cutoff=0.45)
        if matches:
            return name_map[matches[0]]

        return None

# Singleton client instance
dbd_client = DBDClient()
