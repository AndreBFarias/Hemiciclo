"""Testes unit da página ``sessao_detalhe`` (S31).

A página é exercitada via ``streamlit.testing.v1.AppTest`` carregando uma
home temporária com sessões fake. Cada teste cria a sessão direto no
disco (sem rodar o pipeline) e seta ``session_state`` para o id alvo.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from hemiciclo.sessao.modelo import Camada, Casa, EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import salvar_params, salvar_status

_APP = "src/hemiciclo/dashboard/app.py"
_TIMEOUT = 15


@pytest.fixture
def home_com_sessoes(tmp_hemiciclo_home: Path) -> Path:
    """Cria a home temporária e devolve o path raiz."""
    (tmp_hemiciclo_home / "sessoes").mkdir(parents=True, exist_ok=True)
    return tmp_hemiciclo_home


def _criar_sessao(
    home: Path,
    sessao_id: str,
    estado: EstadoSessao,
    *,
    relatorio: dict[str, Any] | None = None,
    manifesto: dict[str, Any] | None = None,
    erro: str | None = None,
) -> Path:
    """Helper que cria sessão sintética com params + status + artefatos opcionais."""
    pasta = home / "sessoes" / sessao_id
    pasta.mkdir(parents=True, exist_ok=True)

    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
    )
    salvar_params(params, pasta / "params.json")

    agora = datetime.now(UTC)
    status = StatusSessao(
        id=sessao_id,
        estado=estado,
        progresso_pct=100.0 if estado == EstadoSessao.CONCLUIDA else 30.0,
        etapa_atual="teste",
        mensagem="msg",
        iniciada_em=agora,
        atualizada_em=agora,
        pid=None,
        erro=erro,
    )
    salvar_status(status, pasta / "status.json")

    if relatorio is not None:
        (pasta / "relatorio_state.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if manifesto is not None:
        (pasta / "manifesto.json").write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return pasta


def _linha(
    id_: int, nome: str, partido: str, uf: str, prop: float, intens: float
) -> dict[str, Any]:
    """Helper para construir uma linha de parlamentar com 7 campos canônicos."""
    return {
        "id": id_,
        "nome": nome,
        "partido": partido,
        "uf": uf,
        "proporcao_sim": prop,
        "posicao": prop,
        "intensidade": intens,
    }


def _relatorio_completo() -> dict[str, Any]:
    """Relatório com 2 a-favor e 2 contra para exercitar widgets."""
    top_a_favor = [
        _linha(1, "Sâmia", "PSOL", "SP", 0.95, 0.7),
        _linha(2, "Talíria", "PSOL", "RJ", 0.92, 0.5),
    ]
    top_contra = [
        _linha(3, "Eros", "PL", "MG", 0.05, 0.6),
        _linha(4, "Sóstenes", "PL", "RJ", 0.10, 0.4),
    ]
    return {
        "topico": "aborto",
        "n_props": 87,
        "n_parlamentares": 513,
        "top_a_favor": top_a_favor,
        "top_contra": top_contra,
        "c3": {"skipped": True, "motivo": "teste"},
    }


def _manifesto_seed() -> dict[str, Any]:
    return {
        "criado_em": "2026-04-28T12:00:00+00:00",
        "versao_pipeline": "1",
        "artefatos": {"params.json": "abc"},
        "limitacoes_conhecidas": ["S24b", "S27.1"],
    }


def _abrir_sessao(home: Path, sessao_id: str) -> AppTest:  # noqa: ARG001 -- home isolada via fixture
    """Constrói AppTest com session_state apontando para a sessão alvo."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = sessao_id
    return app


def test_pagina_carrega_sessao_concluida(home_com_sessoes: Path) -> None:
    """Sessão CONCLUIDA com relatório carrega sem exceção."""
    _criar_sessao(
        home_com_sessoes,
        "_t_concluida",
        EstadoSessao.CONCLUIDA,
        relatorio=_relatorio_completo(),
        manifesto=_manifesto_seed(),
    )
    app = _abrir_sessao(home_com_sessoes, "_t_concluida")
    app.run()
    assert not app.exception, f"app levantou exceção: {app.exception}"


def test_pagina_concluida_renderiza_top_a_favor_e_contra(home_com_sessoes: Path) -> None:
    """Sessão concluída renderiza títulos das duas tabelas."""
    _criar_sessao(
        home_com_sessoes,
        "_t_top",
        EstadoSessao.CONCLUIDA,
        relatorio=_relatorio_completo(),
        manifesto=_manifesto_seed(),
    )
    app = _abrir_sessao(home_com_sessoes, "_t_top")
    app.run()
    assert not app.exception
    todos = " ".join(m.value for m in app.markdown)
    assert "Top a-favor" in todos
    assert "Top contra" in todos


def test_pagina_concluida_renderiza_radar(home_com_sessoes: Path) -> None:
    """Concluída inclui o título do radar e o storytelling da sessão."""
    _criar_sessao(
        home_com_sessoes,
        "_t_radar",
        EstadoSessao.CONCLUIDA,
        relatorio=_relatorio_completo(),
        manifesto=_manifesto_seed(),
    )
    app = _abrir_sessao(home_com_sessoes, "_t_radar")
    app.run()
    assert not app.exception
    todos = " ".join(m.value for m in app.markdown)
    assert "Assinatura multidimensional" in todos
    assert "Relatório multidimensional" in todos


def test_pagina_erro_renderiza_mensagem_clara(home_com_sessoes: Path) -> None:
    """Sessão em ERRO mostra mensagem do campo ``erro`` ao usuário."""
    _criar_sessao(
        home_com_sessoes,
        "_t_erro",
        EstadoSessao.ERRO,
        erro="HTTPError: 503 Service Unavailable",
    )
    app = _abrir_sessao(home_com_sessoes, "_t_erro")
    app.run()
    assert not app.exception
    erros = " ".join(e.value for e in app.error)
    assert "HTTPError" in erros


def test_pagina_interrompida_oferece_retomar(home_com_sessoes: Path) -> None:
    """Sessão INTERROMPIDA mostra warning e botão 'Retomar pesquisa'."""
    _criar_sessao(home_com_sessoes, "_t_int", EstadoSessao.INTERROMPIDA)
    app = _abrir_sessao(home_com_sessoes, "_t_int")
    app.run()
    assert not app.exception
    keys = {b.key for b in app.button}
    assert "sessao_detalhe_retomar" in keys


def test_artefato_ausente_nao_quebra_pagina(home_com_sessoes: Path) -> None:
    """Sessão CONCLUIDA mas sem ``relatorio_state.json`` mostra warning, não quebra."""
    _criar_sessao(home_com_sessoes, "_t_sem_relatorio", EstadoSessao.CONCLUIDA)
    app = _abrir_sessao(home_com_sessoes, "_t_sem_relatorio")
    app.run()
    assert not app.exception
    warnings = " ".join(w.value for w in app.warning)
    assert "relatorio_state.json" in warnings


def test_manifesto_lista_limitacoes(home_com_sessoes: Path) -> None:
    """Manifesto com lista de limitações exibe a seção em linguagem cidadã.

    A S38.6 substituiu a enumeração de IDs de sprint (S24b, S27.1, ...)
    por um texto único e amigável. O teste verifica a presença do
    cabeçalho da seção e a ausência de jargão de roadmap.
    """
    _criar_sessao(
        home_com_sessoes,
        "_t_lim",
        EstadoSessao.CONCLUIDA,
        relatorio=_relatorio_completo(),
        manifesto=_manifesto_seed(),
    )
    app = _abrir_sessao(home_com_sessoes, "_t_lim")
    app.run()
    assert not app.exception
    todos = " ".join(m.value for m in app.markdown)
    assert "Limitações conhecidas" in todos
    # Sprint S38.6: jargão de sprint não deve mais aparecer ao usuário.
    assert "S24b" not in todos
    assert "S27.1" not in todos
    # Texto cidadão deve estar presente.
    assert "limites conhecidos" in todos


def test_pagina_sem_sessao_id_mostra_aviso(home_com_sessoes: Path) -> None:  # noqa: ARG001
    """Sem ``session_state['sessao_id']``, exibe warning e link de volta."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.run()
    assert not app.exception
    warnings = " ".join(w.value for w in app.warning)
    assert "Nenhuma sessão" in warnings


def test_pagina_sessao_inexistente(home_com_sessoes: Path) -> None:  # noqa: ARG001
    """Sessao_id apontando para pasta inexistente exibe erro."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = "nao_existe_xyz"
    app.run()
    assert not app.exception
    erros = " ".join(e.value for e in app.error)
    assert "não encontrada" in erros


def test_pagina_params_corrompido(home_com_sessoes: Path) -> None:
    """Sessão com params.json corrompido (ausente) exibe erro claro."""
    pasta = home_com_sessoes / "sessoes" / "_t_corrompido"
    pasta.mkdir(parents=True, exist_ok=True)
    # Nem params.json nem status.json -- carregar_params retorna None
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = "_t_corrompido"
    app.run()
    assert not app.exception
    erros = " ".join(e.value for e in app.error)
    assert "params.json" in erros


def test_pagina_status_ausente_mostra_warning(home_com_sessoes: Path) -> None:
    """Sessão com params.json mas sem status.json mostra aviso de inicialização."""
    pasta = home_com_sessoes / "sessoes" / "_t_sem_status"
    pasta.mkdir(parents=True, exist_ok=True)
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
    )
    salvar_params(params, pasta / "params.json")

    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = "_t_sem_status"
    app.run()
    assert not app.exception
    warnings = " ".join(w.value for w in app.warning)
    assert "status.json" in warnings


def test_pagina_pausada_oferece_retomar(home_com_sessoes: Path) -> None:
    """Sessão PAUSADA também exibe botão retomar."""
    _criar_sessao(home_com_sessoes, "_t_pausada", EstadoSessao.PAUSADA)
    app = _abrir_sessao(home_com_sessoes, "_t_pausada")
    app.run()
    assert not app.exception
    keys = {b.key for b in app.button}
    assert "sessao_detalhe_retomar" in keys


def test_carregar_json_corrompido_retorna_none(home_com_sessoes: Path) -> None:
    """``_carregar_json`` retorna ``None`` para JSON inválido (cobertura do except)."""
    from hemiciclo.dashboard.paginas.sessao_detalhe import _carregar_json

    arquivo = home_com_sessoes / "json_corrompido.json"
    arquivo.write_text("{ isto não é json válido", encoding="utf-8")
    assert _carregar_json(arquivo) is None
    assert _carregar_json(home_com_sessoes / "ausente.json") is None


def test_polling_termina_em_estado_terminal(
    home_com_sessoes: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_renderizar_em_andamento`` sai do loop quando o status vira terminal.

    Mockamos ``time.sleep`` para acelerar o loop, ``carregar_status`` para
    simular transição COLETANDO -> CONCLUIDA, e ``st.rerun`` para evitar
    que pytest receba ``RerunException``.
    """
    from hemiciclo.dashboard.paginas import sessao_detalhe as sd

    pasta = _criar_sessao(home_com_sessoes, "_t_polling", EstadoSessao.COLETANDO)

    chamadas = {"sleep": 0, "rerun": 0}

    def _fake_sleep(_segundos: float) -> None:
        chamadas["sleep"] += 1

    def _fake_rerun() -> None:
        chamadas["rerun"] += 1

    # Sequência de status retornados pelo polling: 1 em coleta, depois concluida.
    agora = datetime.now(UTC)
    status_concluida = StatusSessao(
        id="_t_polling",
        estado=EstadoSessao.CONCLUIDA,
        progresso_pct=100.0,
        etapa_atual="concluida",
        mensagem="ok",
        iniciada_em=agora,
        atualizada_em=agora,
    )
    sequencia = [status_concluida]

    def _fake_carregar_status(_path: Path) -> StatusSessao | None:
        return sequencia.pop(0) if sequencia else None

    monkeypatch.setattr(sd.time, "sleep", _fake_sleep)
    monkeypatch.setattr(sd.st, "rerun", _fake_rerun)
    monkeypatch.setattr(sd.st, "empty", lambda: _FakeEmpty())
    monkeypatch.setattr(sd, "carregar_status", _fake_carregar_status)

    status_inicial = StatusSessao(
        id="_t_polling",
        estado=EstadoSessao.COLETANDO,
        progresso_pct=20.0,
        etapa_atual="coleta",
        mensagem="msg",
        iniciada_em=agora,
        atualizada_em=agora,
    )
    sd._renderizar_em_andamento(pasta, status_inicial)
    assert chamadas["sleep"] == 1
    assert chamadas["rerun"] == 1


def test_polling_status_some_emite_erro(
    home_com_sessoes: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quando o status some no meio do polling, o widget exibe ``st.error``."""
    from hemiciclo.dashboard.paginas import sessao_detalhe as sd

    pasta = _criar_sessao(home_com_sessoes, "_t_polling_some", EstadoSessao.ETL)

    monkeypatch.setattr(sd.time, "sleep", lambda _s: None)
    monkeypatch.setattr(sd.st, "rerun", lambda: None)
    monkeypatch.setattr(sd.st, "empty", lambda: _FakeEmpty())
    monkeypatch.setattr(sd, "carregar_status", lambda _p: None)

    agora = datetime.now(UTC)
    status_inicial = StatusSessao(
        id="_t_polling_some",
        estado=EstadoSessao.ETL,
        progresso_pct=40.0,
        etapa_atual="etl",
        mensagem="msg",
        iniciada_em=agora,
        atualizada_em=agora,
    )
    # Não deve levantar -- caminho do "novo is None".
    sd._renderizar_em_andamento(pasta, status_inicial)


class _FakeEmpty:
    """Dummy de ``st.empty()`` que aceita ``container`` como context manager."""

    def container(self) -> _FakeEmpty:
        return self

    def __enter__(self) -> _FakeEmpty:
        return self

    def __exit__(self, *_args: object) -> None:
        return None
