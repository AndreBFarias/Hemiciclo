"""Testes do checkpoint persistente em ``hemiciclo.coleta.checkpoint``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hemiciclo.coleta.checkpoint import (
    CheckpointCamara,
    caminho_checkpoint,
    carregar_checkpoint,
    hash_params,
    salvar_checkpoint,
)


def _checkpoint_basico() -> CheckpointCamara:
    """Helper para construir checkpoint com alguns dados."""
    return CheckpointCamara(
        iniciado_em=datetime(2026, 4, 28, 10, 0, tzinfo=UTC),
        atualizado_em=datetime(2026, 4, 28, 10, 30, tzinfo=UTC),
        legislaturas=[55, 56, 57],
        tipos=["proposicoes", "votacoes"],
        proposicoes_baixadas={1, 2, 3},
        votacoes_baixadas={"abc", "def"},
        votos_baixados={("abc", 100), ("abc", 101), ("def", 200)},
        discursos_baixados={"hash_a", "hash_b"},
        deputados_baixados={100, 101, 200},
        erros=[{"url": "https://x.gov.br/y", "codigo": 503, "mensagem": "tmp"}],
    )


def test_serializacao_round_trip(tmp_path: Path) -> None:
    """Salvar e carregar produz checkpoint equivalente ao original."""
    cp = _checkpoint_basico()
    arquivo = tmp_path / "cp.json"
    salvar_checkpoint(cp, arquivo)
    assert arquivo.exists()

    recarregado = carregar_checkpoint(arquivo)
    assert recarregado is not None
    assert recarregado.iniciado_em == cp.iniciado_em
    assert recarregado.atualizado_em == cp.atualizado_em
    assert recarregado.legislaturas == cp.legislaturas
    assert recarregado.tipos == cp.tipos
    assert recarregado.proposicoes_baixadas == cp.proposicoes_baixadas
    assert recarregado.votacoes_baixadas == cp.votacoes_baixadas
    assert recarregado.votos_baixados == cp.votos_baixados
    assert recarregado.discursos_baixados == cp.discursos_baixados
    assert recarregado.deputados_baixados == cp.deputados_baixados
    assert recarregado.erros == cp.erros


def test_hash_params_deterministico() -> None:
    """Mesmos params produzem mesmo hash."""
    h1 = hash_params([55, 56, 57], ["proposicoes", "votacoes"])
    h2 = hash_params([55, 56, 57], ["proposicoes", "votacoes"])
    assert h1 == h2
    assert len(h1) == 16


def test_hash_params_ordem_irrelevante() -> None:
    """Ordem da lista de legislaturas e tipos não afeta o hash."""
    h1 = hash_params([55, 56], ["proposicoes", "votacoes"])
    h2 = hash_params([56, 55], ["votacoes", "proposicoes"])
    assert h1 == h2


def test_hash_params_diferenca_em_mudanca() -> None:
    """Mudar qualquer parâmetro muda o hash."""
    base = hash_params([55, 56], ["proposicoes"])
    diferente_legislatura = hash_params([55, 57], ["proposicoes"])
    diferente_tipo = hash_params([55, 56], ["votacoes"])
    assert base != diferente_legislatura
    assert base != diferente_tipo


def test_escrita_atomica_nao_corrompe_em_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falha durante escrita do .tmp não corrompe o arquivo final.

    Simulamos ``kill -9`` injetando ``RuntimeError`` no meio do
    ``json.dump``. O arquivo final original permanece intacto (ou
    inexistente se primeira escrita).
    """
    cp_v1 = _checkpoint_basico()
    arquivo = tmp_path / "cp.json"
    salvar_checkpoint(cp_v1, arquivo)
    bytes_originais = arquivo.read_bytes()

    cp_v2 = _checkpoint_basico()
    cp_v2.proposicoes_baixadas.add(999)

    chamadas = {"n": 0}
    dump_real = __import__("json").dump

    def _dump_falha(*args: object, **kwargs: object) -> object:
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("simulando kill -9 no meio do dump")
        return dump_real(*args, **kwargs)

    monkeypatch.setattr("hemiciclo.coleta.checkpoint.json.dump", _dump_falha)
    with pytest.raises(RuntimeError, match="kill -9"):
        salvar_checkpoint(cp_v2, arquivo)

    # Arquivo final permanece intacto:
    assert arquivo.read_bytes() == bytes_originais


def test_carregar_inexistente_retorna_none(tmp_path: Path) -> None:
    """Arquivo ausente -> ``None`` (e não exceção)."""
    assert carregar_checkpoint(tmp_path / "nao_existe.json") is None


def test_caminho_checkpoint_em_home_correto(tmp_path: Path) -> None:
    """Path canônico é ``<home>/cache/checkpoints/camara_<hash>.json``."""
    h = hash_params([57], ["proposicoes"])
    path = caminho_checkpoint(tmp_path, h)
    assert path == tmp_path / "cache" / "checkpoints" / f"camara_{h}.json"


def test_set_de_tuples_serializa_como_lista(tmp_path: Path) -> None:
    """``votos_baixados: set[tuple[str, int]]`` percorre JSON sem perda."""
    cp = _checkpoint_basico()
    arquivo = tmp_path / "cp.json"
    salvar_checkpoint(cp, arquivo)

    # Inspeção bruta do JSON: votos viram lista de pares [str, int].
    import json as _json

    bruto = _json.loads(arquivo.read_text(encoding="utf-8"))
    assert isinstance(bruto["votos_baixados"], list)
    assert all(isinstance(par, list) and len(par) == 2 for par in bruto["votos_baixados"])
    # Após reload, viraram tuples novamente:
    recarregado = carregar_checkpoint(arquivo)
    assert recarregado is not None
    assert all(isinstance(t, tuple) for t in recarregado.votos_baixados)


# ---------------------------------------------------------------------------
# S24c -- ``anos_concluidos: set[tuple[int, int]]`` em CheckpointCamara.
# ---------------------------------------------------------------------------


def test_checkpoint_camara_anos_concluidos_default_vazio() -> None:
    """Construir checkpoint sem ``anos_concluidos`` produz ``set()``."""
    cp = CheckpointCamara(
        iniciado_em=datetime(2026, 4, 28, tzinfo=UTC),
        atualizado_em=datetime(2026, 4, 28, tzinfo=UTC),
        legislaturas=[57],
        tipos=["proposicoes"],
    )
    assert cp.anos_concluidos == set()
    assert isinstance(cp.anos_concluidos, set)


def test_checkpoint_camara_anos_concluidos_round_trip(tmp_path: Path) -> None:
    """Salvar e carregar preserva pares ``(legislatura, ano)`` como tuples."""
    cp = CheckpointCamara(
        iniciado_em=datetime(2026, 4, 28, 10, 0, tzinfo=UTC),
        atualizado_em=datetime(2026, 4, 28, 10, 30, tzinfo=UTC),
        legislaturas=[56, 57],
        tipos=["proposicoes"],
        anos_concluidos={(57, 2023), (57, 2024), (56, 2022)},
    )
    arquivo = tmp_path / "cp.json"
    salvar_checkpoint(cp, arquivo)

    # Inspeciona JSON bruto: anos_concluidos vira lista de pares [int, int].
    import json as _json

    bruto = _json.loads(arquivo.read_text(encoding="utf-8"))
    assert isinstance(bruto["anos_concluidos"], list)
    assert all(isinstance(par, list) and len(par) == 2 for par in bruto["anos_concluidos"])
    # Ordem determinística (sort por (legislatura, ano)):
    assert bruto["anos_concluidos"] == [[56, 2022], [57, 2023], [57, 2024]]

    recarregado = carregar_checkpoint(arquivo)
    assert recarregado is not None
    assert recarregado.anos_concluidos == cp.anos_concluidos
    assert all(isinstance(t, tuple) for t in recarregado.anos_concluidos)


def test_checkpoint_camara_carrega_arquivo_legacy_sem_anos_concluidos(
    tmp_path: Path,
) -> None:
    """Checkpoint legacy (sem ``anos_concluidos``) carrega; campo vira ``set()``.

    Garante back-compat S24 -> S24c: usuários com checkpoint anterior à
    sprint não quebram ao retomar uma coleta.
    """
    import json as _json

    arquivo = tmp_path / "cp_legacy.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    dados_legacy = {
        "iniciado_em": "2026-04-27T10:00:00+00:00",
        "atualizado_em": "2026-04-27T10:30:00+00:00",
        "legislaturas": [57],
        "tipos": ["proposicoes"],
        "proposicoes_baixadas": [1, 2, 3],
        "votacoes_baixadas": [],
        "votos_baixados": [],
        "discursos_baixados": [],
        "deputados_baixados": [],
        "erros": [],
        # NOTA: ``anos_concluidos`` ausente, simulando arquivo pre-S24c.
    }
    arquivo.write_text(_json.dumps(dados_legacy), encoding="utf-8")

    recarregado = carregar_checkpoint(arquivo)
    assert recarregado is not None
    assert recarregado.anos_concluidos == set()
    assert recarregado.proposicoes_baixadas == {1, 2, 3}


@given(
    legislaturas=st.lists(st.integers(min_value=1, max_value=99), min_size=1, max_size=5),
    tipos=st.lists(
        st.sampled_from(["proposicoes", "votacoes", "votos", "discursos", "deputados"]),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    props=st.sets(st.integers(min_value=0, max_value=10**6), max_size=20),
    deps=st.sets(st.integers(min_value=0, max_value=10**6), max_size=20),
)
@settings(max_examples=30, deadline=None)
def test_property_based_via_hypothesis(
    tmp_path_factory: pytest.TempPathFactory,
    legislaturas: list[int],
    tipos: list[str],
    props: set[int],
    deps: set[int],
) -> None:
    """Round-trip de qualquer entrada arbitrária preserva conteúdo.

    Cobre invariante: ``carregar(salvar(cp)) == cp`` para qualquer
    estado válido do checkpoint.
    """
    tmp_dir = tmp_path_factory.mktemp("hyp")
    cp = CheckpointCamara(
        iniciado_em=datetime(2026, 4, 28, tzinfo=UTC),
        atualizado_em=datetime(2026, 4, 28, tzinfo=UTC),
        legislaturas=legislaturas,
        tipos=tipos,
        proposicoes_baixadas=props,
        deputados_baixados=deps,
    )
    arquivo = tmp_dir / "cp.json"
    salvar_checkpoint(cp, arquivo)

    recarregado = carregar_checkpoint(arquivo)
    assert recarregado is not None
    assert recarregado.proposicoes_baixadas == cp.proposicoes_baixadas
    assert recarregado.deputados_baixados == cp.deputados_baixados
    assert recarregado.legislaturas == cp.legislaturas
    assert recarregado.tipos == cp.tipos
