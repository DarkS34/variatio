from pathlib import Path
import os

# Network & Infrastructure
OLLAMA_HOST = f"http://{os.environ.get('OLLAMA_HOST', 'localhost:13434')}"

# LLMs
CONTENT_CLEANING_LLM = "gemma4:e4b-it-q4_K_M"
CONTENT_FORMATTING_LLM = "gemma4:31b-it-q4_K_M"
EMBEDDING_LLM = "embeddinggemma:latest"
CONCEPT_TAGGER_LLM = "gemma4:31b-it-q4_K_M"
REPAIR_LLM = "gemma4:e4b-it-q4_K_M"

# File Paths & Cache
_SYSTEM_DIR = Path(__file__).parent
PARTIAL_EMBEDDINGS_FILE = Path("cache", "embeddings", "partial.embed.npz")
FINAL_EMBEDDINGS_FILE = Path("cache", "embeddings", "final.embed.npz")

# Content Processing
MAX_CHUNK_SIZE = 3000
CONTENT_CLEAN_PROMPT_PATH = "content_prep/content_cleaner"
CONTENT_FORMAT_PROMPT_PATH = "content_prep/content_formatter"

# System & Logging
_NOISY_LOGGERS = ("docling", "docling_core", "docling_ibm_models", "PIL")
_NOISY_WARNING_MODULES = (r"docling.*", r"PIL.*")
