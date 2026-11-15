"""Configuração central do CivicSphere. Nada de segredo no código: tudo vem do ambiente."""
import os
from pathlib import Path

VERSAO = "2.0.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CIVICSPHERE_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("CIVICSPHERE_DB", DATA_DIR / "civicsphere.db"))

# --- Modelo (NVIDIA API, compatível com a biblioteca OpenAI) ---
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
# O nome do modelo veio de um resumo anterior e NÃO foi confirmado.
# Rode `python check_model.py` para listar os modelos realmente disponíveis na sua chave
# e ajuste a variável NVIDIA_MODEL.
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/deepseek-v4.1-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "3000"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# --- Servidor ---
HOST = os.getenv("APP_HOST", "0.0.0.0")
PORT = int(os.getenv("APP_PORT", "7860"))
# Se definidos, a interface exige login simples. Recomendado em qualquer exposição pública.
APP_USER = os.getenv("APP_USER", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

# --- Limites de contexto enviado ao modelo ---
MAX_ITENS_CONTEXTO = int(os.getenv("MAX_ITENS_CONTEXTO", "40"))
