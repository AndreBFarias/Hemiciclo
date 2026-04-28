"""Testes do scripts/validar_topicos.py (S27).

Cobre os 5 cenários do spec:
1. YAML válido passa.
2. YAML sem keywords falha.
3. Regex inválida falha.
4. Diretório vazio (só `_schema.yaml`) passa com total=0.
5. Os 3 seeds reais validam.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import validar_topicos  # noqa: E402

SCHEMA_REAL = RAIZ / "topicos" / "_schema.yaml"


@pytest.fixture
def topicos_tmp(tmp_path: Path) -> Path:
    """Cria diretório temporário com _schema.yaml copiado do projeto real."""
    destino = tmp_path / "topicos"
    destino.mkdir()
    shutil.copy(SCHEMA_REAL, destino / "_schema.yaml")
    return destino


def _yaml_valido_minimo(nome: str = "test_x") -> str:
    return (
        f"nome: {nome}\n"
        "versao: 1\n"
        'descricao_curta: "Tópico minimo de teste para validador."\n'
        "keywords:\n"
        "  - palavra\n"
        "regex:\n"
        '  - "(?i)palavra"\n'
    )


def test_yaml_valido_passa(topicos_tmp: Path) -> None:
    (topicos_tmp / "test_x.yaml").write_text(_yaml_valido_minimo("test_x"), encoding="utf-8")
    erros, total = validar_topicos.validar_diretorio(topicos_tmp)
    assert erros == []
    assert total == 1


def test_yaml_sem_keywords_falha(topicos_tmp: Path) -> None:
    yaml_invalido = (
        "nome: sem_kw\n"
        "versao: 1\n"
        'descricao_curta: "Falta keywords obrigatórias."\n'
        "regex:\n"
        '  - "(?i)algo"\n'
    )
    (topicos_tmp / "sem_kw.yaml").write_text(yaml_invalido, encoding="utf-8")
    erros, total = validar_topicos.validar_diretorio(topicos_tmp)
    assert total == 1
    assert any("keywords" in e for e in erros), erros


def test_regex_invalida_falha(topicos_tmp: Path) -> None:
    yaml_regex_quebrada = (
        "nome: regex_ruim\n"
        "versao: 1\n"
        'descricao_curta: "Regex com parênteses desbalanceados."\n'
        "keywords:\n"
        "  - x\n"
        "regex:\n"
        '  - "(unclosed"\n'
    )
    (topicos_tmp / "regex_ruim.yaml").write_text(yaml_regex_quebrada, encoding="utf-8")
    erros, _ = validar_topicos.validar_diretorio(topicos_tmp)
    assert any("regex" in e and "inv" in e.lower() for e in erros), erros


def test_diretorio_vazio_passa(topicos_tmp: Path) -> None:
    """Apenas `_schema.yaml`, nenhum tópico -> exit 0 com total=0."""
    erros, total = validar_topicos.validar_diretorio(topicos_tmp)
    assert erros == []
    assert total == 0


def test_seed_3_topicos_validos() -> None:
    """Os 3 seeds reais (aborto, porte_armas, marco_temporal) validam."""
    erros, total = validar_topicos.validar_diretorio(RAIZ / "topicos")
    assert erros == [], erros
    assert total == 3


def test_filename_diverge_de_nome_falha(topicos_tmp: Path) -> None:
    """Achado-extra: nome interno != filename é erro semântico."""
    yaml_div = _yaml_valido_minimo("nome_interno_diferente")
    (topicos_tmp / "filename_diferente.yaml").write_text(yaml_div, encoding="utf-8")
    erros, _ = validar_topicos.validar_diretorio(topicos_tmp)
    assert any("diverge do filename" in e for e in erros), erros


def test_main_cli_ok(tmp_path: Path) -> None:
    """`main([dir])` retorna 0 quando diretório é válido (3 seeds reais)."""
    rc = validar_topicos.main([str(RAIZ / "topicos")])
    assert rc == 0


def test_main_cli_erro(tmp_path: Path) -> None:
    """`main([dir_inexistente])` retorna 1."""
    rc = validar_topicos.main([str(tmp_path / "nao_existe")])
    assert rc == 1
