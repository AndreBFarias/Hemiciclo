"""Testes E2E do histórico de conversão (S33).

Cobre:

- ``_etapa_historico`` produz ``historico_conversao.json`` em sessão real.
- Sessão sem ``dados.duckdb`` cai em SKIPPED graceful (não quebra).
- CLI ``hemiciclo historico calcular`` ponta-a-ponta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.sessao.modelo import Camada, Casa, EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import salvar_params, salvar_status
from hemiciclo.sessao.runner import StatusUpdater


def _popular_db_temporal(db_path: Path) -> None:
    """Cria DB com 6 parlamentares votando em 3 anos distintos.

    Layout: 6 parlamentares, 30 votações (10 por ano), 3 anos
    (2018, 2022, 2024). Garante 2+ buckets por parlamentar.
    """
    conn = duckdb.connect(str(db_path))
    aplicar_migrations(conn)
    for pid in range(1, 7):
        partido = "PT" if pid <= 3 else "PL"  # noqa: PLR2004
        conn.execute(
            "INSERT INTO parlamentares (id, casa, nome, partido, uf, ativo) "
            "VALUES (?, 'camara', ?, ?, 'SP', TRUE)",
            [pid, f"Parlamentar {pid}", partido],
        )
    anos = (("2018", "2018-03-15"), ("2022", "2022-09-10"), ("2024", "2024-05-05"))
    vid = 1
    for _ano, data_iso in anos:
        for _ in range(10):
            conn.execute(
                "INSERT INTO votacoes (id, casa, data, descricao, resultado) "
                "VALUES (?, 'camara', ?, ?, 'aprovado')",
                [f"v{vid}", data_iso, f"Vot {vid}"],
            )
            for pid in range(1, 7):
                # P1-3 votam SIM em 2018, NAO em 2022+ (mudança forte)
                # P4-6 votam SIM sempre (estável)
                if pid <= 3 and data_iso.startswith("2018"):  # noqa: PLR2004
                    voto = "Sim"
                elif pid <= 3:  # noqa: PLR2004
                    voto = "Nao"
                else:
                    voto = "Sim"
                conn.execute(
                    "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                    "VALUES (?, ?, 'camara', ?, ?)",
                    [f"v{vid}", pid, voto, data_iso],
                )
            vid += 1
    conn.close()


def _criar_sessao_pronta(sessao_dir: Path, sessao_id: str) -> StatusUpdater:
    """Cria pasta da sessão com params/status mínimos pra StatusUpdater."""
    sessao_dir.mkdir(parents=True, exist_ok=True)
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
    )
    salvar_params(params, sessao_dir / "params.json")
    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id=sessao_id,
            estado=EstadoSessao.MODELANDO,
            progresso_pct=90.0,
            etapa_atual="modelando",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )
    return StatusUpdater(sessao_dir, sessao_id)


class _LogStub:
    def info(self, *args: object, **kwargs: object) -> None: ...
    def warning(self, *args: object, **kwargs: object) -> None: ...
    def exception(self, *args: object, **kwargs: object) -> None: ...


def test_pipeline_gera_historico_em_sessao(tmp_path: Path) -> None:
    """``_etapa_historico`` produz ``historico_conversao.json`` em sessão real."""
    from hemiciclo.sessao.pipeline import _etapa_historico

    sessao_dir = tmp_path / "sessao"
    updater = _criar_sessao_pronta(sessao_dir, "teste_hist")
    db_path = sessao_dir / "dados.duckdb"
    _popular_db_temporal(db_path)

    _etapa_historico(sessao_dir, updater, _LogStub())

    destino = sessao_dir / "historico_conversao.json"
    assert destino.is_file()
    payload = json.loads(destino.read_text(encoding="utf-8"))
    assert "parlamentares" in payload
    assert "metadata" in payload
    meta = payload["metadata"]
    assert meta["skipped"] is False
    assert meta["granularidade"] == "ano"
    assert meta["n_parlamentares"] >= 6  # noqa: PLR2004
    # Pelo menos um parlamentar tem mudança detectada (P1-P3 mudaram).
    assert meta["n_com_mudancas"] >= 1
    parls = payload["parlamentares"]
    assert "1" in parls
    bloco_p1 = parls["1"]
    assert isinstance(bloco_p1["historico"], list)
    assert len(bloco_p1["historico"]) >= 2  # noqa: PLR2004
    assert float(bloco_p1["indice_volatilidade"]) > 0.0


def test_pipeline_historico_skip_graceful_sem_db(tmp_path: Path) -> None:
    """Sem ``dados.duckdb`` -> JSON com ``skipped=True``, sem levantar."""
    from hemiciclo.sessao.pipeline import _etapa_historico

    sessao_dir = tmp_path / "sessao_sem_db"
    updater = _criar_sessao_pronta(sessao_dir, "teste_skip")
    _etapa_historico(sessao_dir, updater, _LogStub())

    destino = sessao_dir / "historico_conversao.json"
    assert destino.is_file()
    payload = json.loads(destino.read_text(encoding="utf-8"))
    assert payload["metadata"]["skipped"] is True
    assert payload["parlamentares"] == {}


def test_workflow_cli_historico_calcular(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI ``hemiciclo historico calcular`` ponta-a-ponta em sessão real."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_hist"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "cli_hist"
    sessao_dir.mkdir(parents=True)
    db_path = sessao_dir / "dados.duckdb"
    _popular_db_temporal(db_path)

    runner = CliRunner()
    resultado = runner.invoke(
        app,
        ["historico", "calcular", "cli_hist", "--granularidade", "ano"],
    )
    assert resultado.exit_code == 0, resultado.stdout

    destino = sessao_dir / "historico_conversao.json"
    assert destino.is_file()
    payload = json.loads(destino.read_text(encoding="utf-8"))
    assert payload["metadata"]["skipped"] is False
    assert payload["metadata"]["n_parlamentares"] >= 1


def test_workflow_cli_historico_calcular_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI ``historico calcular`` em sessão sem dados.duckdb -> exit 0 + SKIPPED."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_hist2"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "vazia"
    sessao_dir.mkdir(parents=True)

    runner = CliRunner()
    resultado = runner.invoke(app, ["historico", "calcular", "vazia"])
    assert resultado.exit_code == 0
    assert "SKIPPED" in resultado.stdout
    payload = json.loads((sessao_dir / "historico_conversao.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["skipped"] is True


def test_dashboard_renderiza_secao_historico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_renderizar_secao_historico`` chama tudo corretamente em sessão real."""
    import streamlit as st_real

    from hemiciclo.dashboard.paginas import sessao_detalhe as paginas

    sessao_dir = tmp_path / "sessao_dash"
    sessao_dir.mkdir()
    historico = {
        "metadata": {
            "skipped": False,
            "granularidade": "ano",
            "threshold_pp": 30.0,
            "n_parlamentares": 1,
        },
        "parlamentares": {
            "101": {
                "casa": "camara",
                "nome": "Parlamentar 101",
                "historico": [
                    {
                        "bucket": 2018,
                        "n_votos": 10,
                        "proporcao_sim": 0.8,
                        "proporcao_nao": 0.2,
                        "posicao": "a_favor",
                    },
                    {
                        "bucket": 2024,
                        "n_votos": 12,
                        "proporcao_sim": 0.2,
                        "proporcao_nao": 0.8,
                        "posicao": "contra",
                    },
                ],
                "mudancas_detectadas": [
                    {
                        "bucket_anterior": 2018,
                        "bucket_posterior": 2024,
                        "proporcao_sim_anterior": 0.8,
                        "proporcao_sim_posterior": 0.2,
                        "delta_pp": -60.0,
                        "posicao_anterior": "a_favor",
                        "posicao_posterior": "contra",
                    }
                ],
                "indice_volatilidade": 0.6,
            },
        },
    }
    (sessao_dir / "historico_conversao.json").write_text(
        json.dumps(historico, ensure_ascii=False), encoding="utf-8"
    )

    chamadas: list[str] = []

    def _fake_markdown(*_args: object, **_kwargs: object) -> None:
        chamadas.append("markdown")

    def _fake_caption(*_args: object, **_kwargs: object) -> None:
        chamadas.append("caption")

    def _fake_info(*_args: object, **_kwargs: object) -> None:
        chamadas.append("info")

    def _fake_selectbox(*_args: object, **kwargs: object) -> str | None:
        chamadas.append("selectbox")
        opcoes = kwargs.get("options")
        if isinstance(opcoes, list) and opcoes:
            return str(opcoes[0])
        return None

    def _fake_plotly(*_args: object, **_kwargs: object) -> None:
        chamadas.append("plotly_chart")

    monkeypatch.setattr(st_real, "markdown", _fake_markdown)
    monkeypatch.setattr(st_real, "caption", _fake_caption)
    monkeypatch.setattr(st_real, "info", _fake_info)
    monkeypatch.setattr(st_real, "selectbox", _fake_selectbox)
    monkeypatch.setattr(st_real, "plotly_chart", _fake_plotly)

    paginas._renderizar_secao_historico(sessao_dir)

    # Renderizou cabeçalho + selectbox + chart Plotly do timeline
    assert "selectbox" in chamadas
    assert "plotly_chart" in chamadas
