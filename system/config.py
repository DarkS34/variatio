from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_DIR = PROJECT_ROOT / "system"

INSTANCE_DIR = PROJECT_ROOT / "instance"
CACHE_DIR = PROJECT_ROOT / "cache"

# System & Logging
NOISY_LOGGERS = ("docling", "docling_core", "docling_ibm_models", "PIL")
NOISY_WARNING_MODULES = (r"docling.*", r"PIL.*")

# Network & Infrastructure
_OLLAMA_HOST = os.environ.setdefault("OLLAMA_HOST", "localhost:13434")
OLLAMA_HOST = _OLLAMA_HOST if _OLLAMA_HOST.startswith(("http://", "https://")) else f"http://{_OLLAMA_HOST}"

# LLMs
CONTENT_CLEANING_LLM = "gemma4:e4b-it-q4_K_M"
CONTENT_FORMATTING_LLM = "gemma4:e4b-it-q4_K_M"
EMBEDDING_LLM = "embeddinggemma:latest"
CONCEPT_TAGGER_LLM = "gemma4:e4b-it-q4_K_M"
REPAIR_LLM = "gemma4:e4b-it-q4_K_M"
CONTENT_GENERATION_LLM = "gemma4:e4b-it-q4_K_M"
KG_BUILDER_LLM = "gemma4:e4b-it-q4_K_M"

# File Paths & Cache
RAW_EXEMPLARS_BANK_DIR = PROJECT_ROOT / "raw_exemplars_bank"
RAW_CORPUS_DIR = PROJECT_ROOT / "raw_corpus"

KG_PATH = INSTANCE_DIR / "knowledge_graph.json"
KG_STAGING_PATH = INSTANCE_DIR / "knowledge_graph_staging.json"
EXEMPLARS_BANK_PATH = INSTANCE_DIR / "exemplars_bank.json"
CONTENT_PROFILE_PATH = INSTANCE_DIR / "content_profile.json"
CONCEPT_DESCRIPTIONS_PATH = CACHE_DIR / "concept_descriptions.json"
CONCEPTS_EMBEDDINGS_PATH = CACHE_DIR / "embeddings" / "concepts_embeddings.npz"
EXEMPLARS_BANK_EMBEDDINGS_PATH = CACHE_DIR / "embeddings" / "exemplars_bank_embeddings.npz"
CONCEPT_DESCRIPTIONS_PATH = CACHE_DIR / "concept_descriptions.json"



# Content Processing
MAX_CHUNK_SIZE = 3500
MAX_JSON_REPAIR_TRIES = 3
EMBEDDER_SIMILARITY_THRESHOLD = 0.3
MAX_FEW_SHOT_EXAMPLES = 4
KG_BUILDER_CHUNK_SIZE = 5000