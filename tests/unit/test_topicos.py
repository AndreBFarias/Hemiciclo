"""Testes do carregador runtime `src/hemiciclo/etl/topicos.py` (S27).

Cobre os 6 cenários do spec:
1. Carrega `aborto.yaml` válido.
2. YAML inválido falha com ValueError.
3. Regex compila (sem ValueError).
4. casa_keywords em ementa que tem termo.
5. casa_categoria_oficial em casa correta.
6. listar_topicos retorna 3 seeds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hemiciclo.etl.topicos import (
    Topico,
    carregar_topico,
    listar_topicos,
)

RAIZ = Path(__file__).resolve().parents[2]
TOPICOS_DIR = RAIZ / "topicos"
SCHEMA_PATH = TOPICOS_DIR / "_schema.yaml"


def test_carregar_aborto_valido() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    assert isinstance(aborto, Topico)
    assert aborto.nome == "aborto"
    assert aborto.versao == 1
    assert "aborto" in aborto.keywords
    assert any("interrup" in r for r in aborto.regex)
    assert "Saúde" in aborto.categorias_oficiais_camara
    assert len(aborto.proposicoes_seed) >= 5
    assert len(aborto.exclusoes) >= 2


def test_yaml_invalido_falha(tmp_path: Path) -> None:
    invalido = tmp_path / "invalido.yaml"
    # Falta `keywords` (obrigatório no schema).
    invalido.write_text(
        "nome: invalido\n"
        "versao: 1\n"
        'descricao_curta: "Tópico sem keywords obrigatórias."\n'
        "regex:\n"
        '  - "(?i)foo"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema inválido"):
        carregar_topico(invalido, schema_path=SCHEMA_PATH)


def test_regex_compila() -> None:
    """Os 3 seeds compilam todos os regex sem erro."""
    for slug in ("aborto", "porte_armas", "marco_temporal"):
        t = carregar_topico(TOPICOS_DIR / f"{slug}.yaml")
        assert len(t.regex_compilados) == len(t.regex)
        if t.exclusoes:
            assert len(t.exclusoes_compiladas) == len(t.exclusoes)


def test_casa_keywords_match() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    assert aborto.casa_keywords("Dispõe sobre o direito ao aborto legal em casos de estupro.")
    # Match via regex (não é literal nas keywords)
    assert aborto.casa_keywords("Trata da interrupção da gravidez por anencefalia.")
    # Caso negativo
    assert not aborto.casa_keywords("Lei sobre transporte rodoviário interestadual.")
    # Exclusão funcionando: 'aborto espontâneo' não casa
    assert not aborto.casa_keywords("Estatísticas de aborto espontâneo no SUS.")


def test_casa_categoria_oficial_match() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    assert aborto.casa_categoria_oficial("Saúde", "camara") is True
    assert aborto.casa_categoria_oficial("Saúde", "senado") is True
    assert aborto.casa_categoria_oficial("Transporte", "camara") is False
    assert aborto.casa_categoria_oficial(None, "camara") is False
    assert aborto.casa_categoria_oficial("Saúde", "outro") is False


def test_listar_topicos_3_seed() -> None:
    todos = listar_topicos(TOPICOS_DIR)
    assert set(todos.keys()) == {"aborto", "porte_armas", "marco_temporal"}
    for nome, t in todos.items():
        assert t.nome == nome
        assert len(t.keywords) >= 1
        assert len(t.regex) >= 1


def test_listar_topicos_diretorio_inexistente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        listar_topicos(tmp_path / "nao_existe")


def test_carregar_topico_inexistente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        carregar_topico(tmp_path / "nao_existe.yaml", schema_path=SCHEMA_PATH)


def test_topico_imutavel() -> None:
    """`Topico` é frozen -- atributos não podem ser mudados."""
    from pydantic import ValidationError

    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    with pytest.raises((AttributeError, TypeError, ValidationError)):
        aborto.nome = "outro"  # type: ignore[misc]


def test_casa_keywords_ementa_vazia() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    assert aborto.casa_keywords("") is False


def test_regex_invalida_no_topico_falha(tmp_path: Path) -> None:
    """Se o YAML passa schema mas regex não compila, validator do Pydantic pega."""
    arq = tmp_path / "regex_quebrada.yaml"
    arq.write_text(
        "nome: regex_quebrada\n"
        "versao: 1\n"
        'descricao_curta: "Regex com sintaxe inválida no topico."\n'
        "keywords:\n"
        "  - x\n"
        "regex:\n"
        '  - "("\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="regex"):
        carregar_topico(arq, schema_path=SCHEMA_PATH)
