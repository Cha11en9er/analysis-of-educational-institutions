"""Пути gc_data (единый источник для скриптов)."""
from pathlib import Path

GC_DATA = Path(__file__).resolve().parent
GC_INPUT = GC_DATA / "gc_input"
GC_OUTPUT = GC_DATA / "gc_output"

ADDRESSES_JSON = GC_INPUT / "addresses.json"
GEOCODED_JSON = GC_OUTPUT / "geocoded.json"
CACHE_JSON = GC_OUTPUT / "_cache.json"

# legacy (миграция кэша)
LEGACY_CACHE = GC_OUTPUT / "_gc_ans_matched_cache.json"
LEGACY_ADDRESSES = GC_INPUT / "gc_ans_matched_input_data.json"
