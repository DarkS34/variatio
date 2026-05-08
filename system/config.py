from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_DIR = PROJECT_ROOT / "system"

ESSENTIALS_DIR = PROJECT_ROOT / "essential_data"
CACHE_DIR = PROJECT_ROOT / "cache"

# System & Logging
NOISY_LOGGERS = ("docling", "docling_core", "docling_ibm_models", "PIL")
NOISY_WARNING_MODULES = (r"docling.*", r"PIL.*")

# Network & Infrastructure
OLLAMA_HOST = f"http://{os.environ.get('OLLAMA_HOST', 'localhost:13434')}"

# LLMs
CONTENT_CLEANING_LLM = "gemma4:e4b-it-q4_K_M"
CONTENT_FORMATTING_LLM = "gemma4:31b-it-q4_K_M"
EMBEDDING_LLM = "embeddinggemma:latest"
CONCEPT_TAGGER_LLM = "gemma4:31b-it-q4_K_M"
REPAIR_LLM = "gemma4:e4b-it-q4_K_M"

# File Paths & Cache
RAW_CONTENT_BANK_DIR = PROJECT_ROOT / "raw_content_bank"

KG_PATH = ESSENTIALS_DIR / "knowledge_graph_raw.json"
CONTENT_BANK_PATH = ESSENTIALS_DIR / "content_bank.json"
CONCEPT_DESCRIPTIONS_PATH = CACHE_DIR / "concept_descriptions.json"
CONCEPTS_EMBEDDINGS_PATH = CACHE_DIR / "embeddings" / "concepts_embeddings.npz"
CONTENT_BANK_EMBEDDINGS_PATH = CACHE_DIR / "embeddings" / "content_bank_embeddings.npz"
CONCEPT_DESCRIPTIONS_PATH = CACHE_DIR / "concept_descriptions.json"



# Content Processing
MAX_CHUNK_SIZE = 3500
MAX_JSON_REPAIR_TRIES = 3
EMBEDDER_SIMILARITY_THRESHOLD = 0.4