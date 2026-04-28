"""Testes unit do CheckpointSenado (S25).

Garantem round-trip JSON, idempotência, coexistência com CheckpointCamara
e propriedades fundamentais via Hypothesis.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from hemiciclo.coleta.checkpoint import (
    CheckpointCamara,
    CheckpointSenado,
    caminho_checkpoint,
    caminho_checkpoint_senado,
    carregar_checkpoint,
    carregar_checkpoint_senado,
    hash_params,
    hash_params_senado,
    salvar_checkpoint,
    salvar_checkpoint_senado,
)


def _cp_minimo() -> CheckpointSenado:
    """Constrói um CheckpointSenado mínimo válido."""
    return CheckpointSenado(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        anos=[2024],
        tipos=["materias"],
    )


def test_serializacao_round_trip_senado(tmp_path: Path) -> None:
    """Salvar e recarregar o checkpoint do Senado preserva todos os campos."""
    cp = _cp_minimo()
    cp.materias_baixadas.update({101, 102, 103})
    cp.votacoes_baixadas.update({501, 502})
    cp.discursos_baixados.update({"abc123", "def456"})
    cp.senadores_baixados.update({7001, 7002})

    h = hash_params_senado(cp.anos, cp.tipos)
    path = caminho_checkpoint_senado(tmp_path, h)
    salvar_checkpoint_senado(cp, path)

    rec = carregar_checkpoint_senado(path)
    assert rec is not None
    assert rec.materias_baixadas == {101, 102, 103}
    assert rec.votacoes_baixadas == {501, 502}
    assert rec.discursos_baixados == {"abc123", "def456"}
    assert rec.senadores_baixados == {7001, 7002}
    assert rec.tipos == ["materias"]
    assert rec.anos == [2024]


def test_set_de_tuples_serializa_como_lista(tmp_path: Path) -> None:
    """``votos_baixados: set[tuple[int, int]]`` sobrevive round-trip JSON."""
    cp = _cp_minimo()
    cp.votos_baixados.add((501, 7001))
    cp.votos_baixados.add((501, 7002))
    cp.votos_baixados.add((502, 7001))

    h = hash_params_senado(cp.anos, cp.tipos)
    path = caminho_checkpoint_senado(tmp_path, h)
    salvar_checkpoint_senado(cp, path)

    rec = carregar_checkpoint_senado(path)
    assert rec is not None
    assert (501, 7001) in rec.votos_baixados
    assert (501, 7002) in rec.votos_baixados
    assert (502, 7001) in rec.votos_baixados
    assert all(isinstance(t, tuple) for t in rec.votos_baixados)
    assert all(len(t) == 2 for t in rec.votos_baixados)


def test_carregar_inexistente_retorna_none(tmp_path: Path) -> None:
    """Carregar checkpoint de path inexistente retorna ``None`` sem exceção."""
    path = tmp_path / "nao_existe.json"
    assert carregar_checkpoint_senado(path) is None


@given(
    materias=st.sets(st.integers(min_value=1, max_value=10_000), max_size=20),
    senadores=st.sets(st.integers(min_value=1, max_value=10_000), max_size=20),
)
def test_property_based_via_hypothesis(
    materias: set[int],
    senadores: set[int],
    tmp_path_factory: object,
) -> None:
    """Para qualquer conjunto de IDs, salvar+carregar é identidade."""
    # tmp_path_factory injetado pelo pytest é callable com getbasetemp; usamos
    # diretório local mktemp baseado na execução. Hypothesis gera múltiplos casos.
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        cp = _cp_minimo()
        cp.materias_baixadas = set(materias)
        cp.senadores_baixados = set(senadores)
        path = Path(td) / "cp.json"
        salvar_checkpoint_senado(cp, path)
        rec = carregar_checkpoint_senado(path)
        assert rec is not None
        assert rec.materias_baixadas == materias
        assert rec.senadores_baixados == senadores


def test_cohabita_com_checkpoint_camara(tmp_path: Path) -> None:
    """Ambos checkpoints podem coexistir no mesmo diretório de cache."""
    # Checkpoint Câmara
    cp_camara = CheckpointCamara(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        legislaturas=[57],
        tipos=["proposicoes"],
        proposicoes_baixadas={1, 2, 3},
    )
    h_c = hash_params(cp_camara.legislaturas, cp_camara.tipos)
    path_c = caminho_checkpoint(tmp_path, h_c)
    salvar_checkpoint(cp_camara, path_c)

    # Checkpoint Senado
    cp_senado = _cp_minimo()
    cp_senado.materias_baixadas = {10, 20, 30}
    h_s = hash_params_senado(cp_senado.anos, cp_senado.tipos)
    path_s = caminho_checkpoint_senado(tmp_path, h_s)
    salvar_checkpoint_senado(cp_senado, path_s)

    # Ambos no mesmo diretório, com prefixo distinto
    assert path_c.parent == path_s.parent
    assert path_c.name.startswith("camara_")
    assert path_s.name.startswith("senado_")
    assert path_c.exists()
    assert path_s.exists()

    # Recargar não confunde:
    rec_c = carregar_checkpoint(path_c)
    rec_s = carregar_checkpoint_senado(path_s)
    assert rec_c is not None
    assert rec_s is not None
    assert rec_c.proposicoes_baixadas == {1, 2, 3}
    assert rec_s.materias_baixadas == {10, 20, 30}


def test_hash_params_senado_determinismo() -> None:
    """A ordem das listas de entrada não altera o hash."""
    h1 = hash_params_senado([2024, 2025], ["materias", "votacoes"])
    h2 = hash_params_senado([2025, 2024], ["votacoes", "materias"])
    assert h1 == h2


def test_hash_senado_distinto_de_hash_camara() -> None:
    """Mesmos parâmetros numéricos produzem hash diferente entre casas."""
    h_c = hash_params([57], ["materias"])
    h_s = hash_params_senado([57], ["materias"])
    assert h_c != h_s
