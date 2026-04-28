"""Testes de :mod:`hemiciclo.sessao.persistencia` (S29).

Cobre escrita atômica, round-trip Pydantic, listagem ordenada, deleção
segura contra path traversal e tolerância a arquivo corrompido.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hemiciclo.sessao.modelo import (
    Casa,
    EstadoSessao,
    ParametrosBusca,
    StatusSessao,
)
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    carregar_params,
    carregar_status,
    deletar_sessao,
    gerar_id_sessao,
    listar_sessoes,
    salvar_params,
    salvar_status,
)


def _params(topico: str = "aborto") -> ParametrosBusca:
    """Helper de construção de params válidos."""
    return ParametrosBusca(topico=topico, casas=[Casa.CAMARA], legislaturas=[57])


def _status(id_sessao: str, *, iniciada_em: datetime | None = None) -> StatusSessao:
    """Helper de construção de status com defaults razoáveis."""
    agora = iniciada_em or datetime.now(UTC)
    return StatusSessao(
        id=id_sessao,
        estado=EstadoSessao.CRIADA,
        progresso_pct=0.0,
        etapa_atual="criada",
        mensagem="ok",
        iniciada_em=agora,
        atualizada_em=agora,
    )


def test_gerar_id_unico() -> None:
    """Dois ids gerados em sequência são distintos (timestamp em microssegundos)."""
    id1 = gerar_id_sessao(_params())
    id2 = gerar_id_sessao(_params())
    assert id1 != id2
    assert id1.startswith("aborto_")


def test_gerar_id_slugifica_topico_com_acento() -> None:
    """Tópico com acento vira slug ASCII puro."""
    params = _params(topico="reforma tributária 2026")
    id_ = gerar_id_sessao(params)
    # Slug não pode ter acento nem espaço
    assert " " not in id_
    assert "á" not in id_
    assert id_.startswith("reforma_tribut")


def test_salvar_carregar_params_round_trip(tmp_path: Path) -> None:
    """Round-trip ParametrosBusca: campos preservados e reidratáveis."""
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA, Casa.SENADO],
        legislaturas=[56, 57],
        ufs=["SP", "RJ"],
    )
    destino = tmp_path / "params.json"
    salvar_params(params, destino)
    assert destino.exists()

    carregado = carregar_params(destino)
    assert carregado is not None
    assert carregado.topico == "aborto"
    assert set(carregado.casas) == {Casa.CAMARA, Casa.SENADO}
    assert carregado.legislaturas == [56, 57]
    assert carregado.ufs == ["SP", "RJ"]


def test_salvar_status_atomico_sem_tmpfile_orfao(tmp_path: Path) -> None:
    """Após escrita atômica, não sobra arquivo .tmp na pasta destino."""
    status = _status("aborto_test")
    destino = tmp_path / "status.json"
    salvar_status(status, destino)
    assert destino.exists()

    # Nenhum .tmp órfão -- escrita atômica via NamedTemporaryFile + replace.
    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == [], f"resíduo tmp: {tmps}"


def test_listar_sessoes_ordenadas_por_iniciada_em_desc(tmp_path: Path) -> None:
    """Listar devolve sessões da mais recente pra mais antiga."""
    base = datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC)
    home = tmp_path

    for i, delta in enumerate([0, 60, 30]):  # ordens propositais misturadas
        id_ = f"sessao_{i}"
        d = caminho_sessao(home, id_)
        d.mkdir(parents=True)
        salvar_params(_params(), d / "params.json")
        salvar_status(_status(id_, iniciada_em=base + timedelta(seconds=delta)), d / "status.json")

    lista = listar_sessoes(home)
    assert len(lista) == 3
    # Mais nova primeiro: idx=1 (60s) > idx=2 (30s) > idx=0 (0s).
    assert [t[0] for t in lista] == ["sessao_1", "sessao_2", "sessao_0"]


def test_deletar_remove_pasta(tmp_path: Path) -> None:
    """``deletar_sessao`` remove a pasta inteira; chamada seguinte é no-op."""
    home = tmp_path
    id_ = "x_test"
    d = caminho_sessao(home, id_)
    d.mkdir(parents=True)
    (d / "params.json").write_text("{}", encoding="utf-8")

    deletar_sessao(home, id_)
    assert not d.exists()

    # Idempotente: deletar de novo não levanta.
    deletar_sessao(home, id_)


def test_deletar_recusa_path_traversal(tmp_path: Path) -> None:
    """``deletar_sessao`` recusa id_sessao malicioso fora da raiz sessoes/."""
    home = tmp_path
    (home / "sessoes").mkdir()
    # Cria arquivo fora da raiz sessoes/ que NÃO deve ser deletável.
    (home / "fora.txt").write_text("nao_deletar", encoding="utf-8")

    with pytest.raises(ValueError, match="fora da pasta sessoes"):
        deletar_sessao(home, "../fora.txt")
    assert (home / "fora.txt").exists()


def test_arquivo_corrompido_retorna_none(tmp_path: Path) -> None:
    """Status/params com JSON inválido ou schema incompatível retornam None."""
    bad = tmp_path / "bad.json"
    bad.write_text("{nao eh json valido", encoding="utf-8")
    assert carregar_status(bad) is None
    assert carregar_params(bad) is None

    # JSON válido mas schema incompatível.
    ruim = tmp_path / "ruim.json"
    ruim.write_text(json.dumps({"campo_estranho": 1}), encoding="utf-8")
    assert carregar_status(ruim) is None
    assert carregar_params(ruim) is None


def test_listar_sessoes_pula_corrompida(tmp_path: Path) -> None:
    """Sessão com status inválido é silenciosamente ignorada na listagem."""
    home = tmp_path
    d = caminho_sessao(home, "boa")
    d.mkdir(parents=True)
    salvar_params(_params(), d / "params.json")
    salvar_status(_status("boa"), d / "status.json")

    ruim = caminho_sessao(home, "ruim")
    ruim.mkdir(parents=True)
    salvar_params(_params(), ruim / "params.json")
    (ruim / "status.json").write_text("{xxx", encoding="utf-8")

    lista = listar_sessoes(home)
    ids = [t[0] for t in lista]
    assert ids == ["boa"]
