"""Testes E2E dos grafos de rede (S32).

Cobrem:
- Pipeline gera HTMLs + metricas_rede.json em sessão mockada com votos.
- Sessão sem dados.duckdb gera metricas SKIPPED graceful, sem quebrar.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.sessao.modelo import Camada, Casa, EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import salvar_params, salvar_status
from hemiciclo.sessao.runner import StatusUpdater


def _popular_db_com_votos(db_path: Path, n_parl: int = 8, n_votacoes: int = 10) -> None:
    """Cria dados.duckdb com votos suficientes para grafos."""
    conn = duckdb.connect(str(db_path))
    aplicar_migrations(conn)
    for pid in range(1, n_parl + 1):
        partido = "PT" if pid <= n_parl // 2 else "PL"
        conn.execute(
            "INSERT INTO parlamentares (id, casa, nome, partido, uf, ativo) "
            "VALUES (?, 'camara', ?, ?, 'SP', TRUE)",
            [pid, f"Parlamentar {pid}", partido],
        )
    for vid in range(1, n_votacoes + 1):
        conn.execute(
            "INSERT INTO votacoes (id, casa, data, descricao, resultado) "
            "VALUES (?, 'camara', '2024-01-01', ?, 'aprovado')",
            [f"v{vid}", f"Votacao {vid}"],
        )
        for pid in range(1, n_parl + 1):
            voto = "Sim" if pid <= n_parl // 2 else "Nao"
            conn.execute(
                "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                "VALUES (?, ?, 'camara', ?, '2024-01-01')",
                [f"v{vid}", pid, voto],
            )
    conn.close()


def test_pipeline_gera_grafos_em_sessao(tmp_path: Path) -> None:
    """``_etapa_grafos`` produz 2 HTMLs + metricas_rede.json em sessão real."""
    from hemiciclo.sessao.pipeline import _etapa_grafos

    sessao_dir = tmp_path / "sessao"
    sessao_dir.mkdir()
    db_path = sessao_dir / "dados.duckdb"
    _popular_db_com_votos(db_path)

    # StatusUpdater real precisa de status.json existente
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
    )
    salvar_params(params, sessao_dir / "params.json")

    from datetime import UTC, datetime

    agora = datetime.now(UTC)
    status = StatusSessao(
        id="teste",
        estado=EstadoSessao.MODELANDO,
        progresso_pct=80.0,
        etapa_atual="modelando",
        mensagem="",
        iniciada_em=agora,
        atualizada_em=agora,
    )
    salvar_status(status, sessao_dir / "status.json")
    updater = StatusUpdater(sessao_dir, "teste")

    class _LogStub:
        def info(self, *args: object, **kwargs: object) -> None: ...
        def warning(self, *args: object, **kwargs: object) -> None: ...
        def exception(self, *args: object, **kwargs: object) -> None: ...

    _etapa_grafos(sessao_dir, updater, _LogStub())

    assert (sessao_dir / "grafo_coautoria.html").is_file()
    assert (sessao_dir / "grafo_voto.html").is_file()
    metricas_path = sessao_dir / "metricas_rede.json"
    assert metricas_path.is_file()
    metricas = json.loads(metricas_path.read_text(encoding="utf-8"))
    assert metricas["coautoria"]["skipped"] is False
    assert metricas["voto"]["skipped"] is False
    assert metricas["coautoria"]["n_nos"] == 8


def test_pipeline_grafos_skip_graceful_sem_db(tmp_path: Path) -> None:
    """Sem ``dados.duckdb`` o pipeline persiste métricas SKIPPED, não levanta."""
    from hemiciclo.sessao.pipeline import _etapa_grafos

    sessao_dir = tmp_path / "sessao_sem_db"
    sessao_dir.mkdir()

    from datetime import UTC, datetime

    agora = datetime.now(UTC)
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX],
    )
    salvar_params(params, sessao_dir / "params.json")
    status = StatusSessao(
        id="teste2",
        estado=EstadoSessao.MODELANDO,
        progresso_pct=80.0,
        etapa_atual="modelando",
        mensagem="",
        iniciada_em=agora,
        atualizada_em=agora,
    )
    salvar_status(status, sessao_dir / "status.json")
    updater = StatusUpdater(sessao_dir, "teste2")

    class _LogStub:
        def info(self, *args: object, **kwargs: object) -> None: ...
        def warning(self, *args: object, **kwargs: object) -> None: ...
        def exception(self, *args: object, **kwargs: object) -> None: ...

    # Não deve levantar
    _etapa_grafos(sessao_dir, updater, _LogStub())

    metricas_path = sessao_dir / "metricas_rede.json"
    assert metricas_path.is_file()
    metricas = json.loads(metricas_path.read_text(encoding="utf-8"))
    assert metricas["coautoria"]["skipped"] is True
    assert metricas["voto"]["skipped"] is True
    # Nenhum HTML gerado
    assert not (sessao_dir / "grafo_coautoria.html").exists()
    assert not (sessao_dir / "grafo_voto.html").exists()


def test_pipeline_grafos_amostra_insuficiente_skip_graceful(tmp_path: Path) -> None:
    """DB com 3 parlamentares (< MIN_NOS_GRAFO=5) -> ambos SKIPPED gracefully."""
    from hemiciclo.sessao.pipeline import _etapa_grafos

    sessao_dir = tmp_path / "sessao_amostra_pequena"
    sessao_dir.mkdir()
    db_path = sessao_dir / "dados.duckdb"
    _popular_db_com_votos(db_path, n_parl=3, n_votacoes=10)

    from datetime import UTC, datetime

    agora = datetime.now(UTC)
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX],
    )
    salvar_params(params, sessao_dir / "params.json")
    salvar_status(
        StatusSessao(
            id="teste3",
            estado=EstadoSessao.MODELANDO,
            progresso_pct=80.0,
            etapa_atual="modelando",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )
    updater = StatusUpdater(sessao_dir, "teste3")

    class _LogStub:
        def info(self, *args: object, **kwargs: object) -> None: ...
        def warning(self, *args: object, **kwargs: object) -> None: ...
        def exception(self, *args: object, **kwargs: object) -> None: ...

    _etapa_grafos(sessao_dir, updater, _LogStub())

    metricas = json.loads((sessao_dir / "metricas_rede.json").read_text(encoding="utf-8"))
    assert metricas["coautoria"]["skipped"] is True
    assert metricas["voto"]["skipped"] is True
    # Nenhum HTML gerado
    assert not (sessao_dir / "grafo_coautoria.html").exists()


def test_cli_rede_analisar_sessao_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI ``hemiciclo rede analisar`` em sessão real gera HTMLs."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_hemiciclo"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "teste_cli"
    sessao_dir.mkdir(parents=True)
    db_path = sessao_dir / "dados.duckdb"
    _popular_db_com_votos(db_path, n_parl=8, n_votacoes=10)

    runner = CliRunner()
    resultado = runner.invoke(app, ["rede", "analisar", "teste_cli", "--tipo", "ambos"])
    assert resultado.exit_code == 0, resultado.stdout
    assert (sessao_dir / "grafo_coautoria.html").is_file()
    assert (sessao_dir / "grafo_voto.html").is_file()
    metricas = json.loads((sessao_dir / "metricas_rede.json").read_text(encoding="utf-8"))
    assert metricas["coautoria"]["skipped"] is False
    assert metricas["voto"]["skipped"] is False


def test_cli_rede_analisar_sem_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI ``rede analisar`` em sessão sem dados.duckdb -> exit 0 + métricas SKIPPED."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_cli2"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "vazia"
    sessao_dir.mkdir(parents=True)

    runner = CliRunner()
    resultado = runner.invoke(app, ["rede", "analisar", "vazia"])
    assert resultado.exit_code == 0
    assert "ausente" in resultado.stdout.lower()
    metricas = json.loads((sessao_dir / "metricas_rede.json").read_text(encoding="utf-8"))
    assert metricas["coautoria"]["skipped"] is True


def test_cli_rede_analisar_apenas_coautoria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI com ``--tipo coautoria`` gera só HTML de coautoria."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_cli3"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "so_coa"
    sessao_dir.mkdir(parents=True)
    _popular_db_com_votos(sessao_dir / "dados.duckdb", n_parl=8, n_votacoes=10)

    runner = CliRunner()
    resultado = runner.invoke(app, ["rede", "analisar", "so_coa", "--tipo", "coautoria"])
    assert resultado.exit_code == 0, resultado.stdout
    assert (sessao_dir / "grafo_coautoria.html").is_file()
    # Voto não rodou
    metricas = json.loads((sessao_dir / "metricas_rede.json").read_text(encoding="utf-8"))
    assert metricas["voto"]["skipped"] is True


def test_dashboard_renderiza_secao_redes_concluida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sessão concluída com métricas_rede.json renderiza tabs sem quebrar.

    Usa monkeypatch sobre os pontos do streamlit que abrem UI real.
    """
    import streamlit as st_real

    from hemiciclo.dashboard.paginas import sessao_detalhe as paginas

    sessao_dir = tmp_path / "sessao_renderiza"
    sessao_dir.mkdir()

    metricas = {
        "coautoria": {
            "skipped": False,
            "n_nos": 6,
            "n_arestas": 8,
            "maior_componente": 6,
            "n_comunidades": 2,
            "top_centrais": [
                {
                    "id": 1,
                    "nome": "P1",
                    "partido": "PT",
                    "uf": "SP",
                    "centralidade": 0.8,
                    "comunidade": 0,
                },
            ],
        },
        "voto": {"skipped": True, "motivo": "amostra insuficiente"},
    }
    (sessao_dir / "metricas_rede.json").write_text(
        json.dumps(metricas, ensure_ascii=False), encoding="utf-8"
    )
    # HTML coautoria existe; voto não (testa o info amigável)
    (sessao_dir / "grafo_coautoria.html").write_text(
        "<html><body>OK</body></html>", encoding="utf-8"
    )

    chamadas: list[str] = []

    class _FakeContextManager:
        def __enter__(self) -> object:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_tabs(_rotulos: list[str]) -> tuple[object, object, object]:
        chamadas.append("tabs")
        return _FakeContextManager(), _FakeContextManager(), _FakeContextManager()

    def _fake_markdown(*_args: object, **_kwargs: object) -> None:
        chamadas.append("markdown")

    def _fake_caption(*_args: object, **_kwargs: object) -> None:
        chamadas.append("caption")

    def _fake_info(*_args: object, **_kwargs: object) -> None:
        chamadas.append("info")

    def _fake_dataframe(*_args: object, **_kwargs: object) -> None:
        chamadas.append("dataframe")

    def _fake_html(*_args: object, **_kwargs: object) -> None:
        chamadas.append("components_html")

    monkeypatch.setattr(st_real, "tabs", _fake_tabs)
    monkeypatch.setattr(st_real, "markdown", _fake_markdown)
    monkeypatch.setattr(st_real, "caption", _fake_caption)
    monkeypatch.setattr(st_real, "info", _fake_info)
    monkeypatch.setattr(st_real, "dataframe", _fake_dataframe)
    monkeypatch.setattr(st_real.components.v1, "html", _fake_html)

    paginas._renderizar_secao_redes(sessao_dir)

    # Pelo menos: tabs criadas, e markdown chamado várias vezes
    assert "tabs" in chamadas
    assert chamadas.count("markdown") >= 1
