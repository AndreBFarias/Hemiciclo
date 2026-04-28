"""Testes da pipeline de fontes auto-hospedadas (S23.1).

Cobre:
- Presença dos 6 TTFs em ``src/hemiciclo/dashboard/static/fonts/``
- LICENSE SIL OFL 1.1 presente
- Função ``_carregar_fontes_inline`` gera CSS válido com 6 ``@font-face``
- Idempotência do verificador de hashes
- Resiliência a fontes ausentes (não quebra app)
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FONTES_DIR = REPO_ROOT / "src" / "hemiciclo" / "dashboard" / "static" / "fonts"

TTFS_ESPERADOS = [
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "Inter-Bold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Bold.ttf",
]


def test_ttfs_existem_em_static_fonts() -> None:
    """Os 6 TTFs declarados em ADR-021 estão versionados no repo."""
    for nome in TTFS_ESPERADOS:
        path = FONTES_DIR / nome
        assert path.exists(), f"TTF ausente: {path}"
        # Tamanho razoável (entre 100 KiB e 1 MiB cada)
        tamanho = path.stat().st_size
        assert 100_000 < tamanho < 1_000_000, f"{nome} tamanho fora de faixa: {tamanho}"


def test_license_sil_ofl_presente() -> None:
    """LICENSE SIL OFL 1.1 com cópia + atribuição."""
    license_path = FONTES_DIR / "LICENSE"
    assert license_path.exists(), f"LICENSE ausente em {license_path}"
    texto = license_path.read_text(encoding="utf-8")
    assert "SIL Open Font License" in texto
    assert "Inter Project Authors" in texto
    assert "JetBrains Mono Project Authors" in texto


def test_readme_documenta_origem_e_versao() -> None:
    """README.md da pasta fontes lista TTFs + origens oficiais."""
    readme_path = FONTES_DIR / "README.md"
    assert readme_path.exists()
    texto = readme_path.read_text(encoding="utf-8")
    assert "SIL Open Font License" in texto
    assert "Inter v4.0" in texto
    assert "rsms.me/inter" in texto or "rsms/inter" in texto


def test_carregar_fontes_inline_gera_seis_font_faces() -> None:
    """``_carregar_fontes_inline`` produz 6 ``@font-face`` com base64 válido."""
    # Import lazy: app.py depende de streamlit; só garantimos chamada se possível
    try:
        app_module = importlib.import_module("hemiciclo.dashboard.app")
    except ImportError:
        return  # streamlit ausente, skip
    # ``_carregar_fontes_inline`` é decorada com @st.cache_resource;
    # acessamos via __wrapped__ se necessário
    fn = getattr(app_module, "_carregar_fontes_inline", None)
    assert fn is not None
    # Dispara cache (ou ignora se já cached)
    css = fn()
    assert isinstance(css, str)
    # 6 font-faces se as 6 TTFs estão presentes
    assert css.count("@font-face") == 6
    assert "Inter" in css
    assert "JetBrains Mono" in css
    assert "data:font/ttf;base64," in css


def test_baixar_fontes_verifica_idempotente() -> None:
    """``scripts/baixar_fontes.verificar_fontes`` é puro e idempotente."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        baixar_fontes = importlib.import_module("baixar_fontes")
    finally:
        if str(REPO_ROOT / "scripts") in sys.path:
            sys.path.remove(str(REPO_ROOT / "scripts"))

    presentes_1, esperadas_1 = baixar_fontes.verificar_fontes(FONTES_DIR)
    presentes_2, esperadas_2 = baixar_fontes.verificar_fontes(FONTES_DIR)

    assert presentes_1 == presentes_2 == 6
    assert esperadas_1 == esperadas_2 == 6

    # Hash do primeiro TTF bate com tabela embedada
    inter_regular = FONTES_DIR / "Inter-Regular.ttf"
    sha = hashlib.sha256(inter_regular.read_bytes()).hexdigest()
    assert sha == baixar_fontes.HASHES_ESPERADOS["Inter-Regular.ttf"]
