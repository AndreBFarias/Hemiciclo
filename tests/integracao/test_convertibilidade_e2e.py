"""Testes E2E do ML de convertibilidade (S34).

Cobre:

- ``_etapa_convertibilidade`` produz ``convertibilidade_scores.json``
  em sessão real com features S33+S32+S27 já calculadas.
- Sessão sem features (artefatos pré-requisito ausentes) cai em
  SKIPPED graceful.
- CLI ``hemiciclo convertibilidade treinar`` ponta-a-ponta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hemiciclo.sessao.modelo import Camada, Casa, EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import salvar_params, salvar_status
from hemiciclo.sessao.runner import StatusUpdater

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _criar_sessao_pronta(sessao_dir: Path, sessao_id: str) -> StatusUpdater:
    """Cria pasta de sessão com params/status mínimos para StatusUpdater."""
    sessao_dir.mkdir(parents=True, exist_ok=True)
    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
        incluir_convertibilidade=True,
    )
    salvar_params(params, sessao_dir / "params.json")
    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id=sessao_id,
            estado=EstadoSessao.MODELANDO,
            progresso_pct=95.0,
            etapa_atual="modelando",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )
    return StatusUpdater(sessao_dir, sessao_id)


def _historico_grande(n_parlamentares: int = 40, n_com_mudancas: int = 20) -> dict[str, object]:
    """``historico_conversao.json`` sintético com dados suficientes para treino."""
    parlamentares: dict[str, object] = {}
    for idx in range(1, n_parlamentares + 1):
        pid = str(100 + idx)
        eh_mudou = idx <= n_com_mudancas
        bloco: dict[str, object] = {
            "casa": "camara",
            "nome": f"Parlamentar {pid}",
            "historico": [
                {
                    "bucket": 2018,
                    "n_votos": 10,
                    "proporcao_sim": 0.8 if eh_mudou else 0.5,
                    "proporcao_nao": 0.2 if eh_mudou else 0.5,
                    "posicao": "a_favor" if eh_mudou else "neutro",
                },
                {
                    "bucket": 2024,
                    "n_votos": 10,
                    "proporcao_sim": 0.2 if eh_mudou else 0.55,
                    "proporcao_nao": 0.8 if eh_mudou else 0.45,
                    "posicao": "contra" if eh_mudou else "neutro",
                },
            ],
            "mudancas_detectadas": (
                [
                    {
                        "bucket_anterior": 2018,
                        "bucket_posterior": 2024,
                        "proporcao_sim_anterior": 0.8,
                        "proporcao_sim_posterior": 0.2,
                        "delta_pp": -60.0,
                        "posicao_anterior": "a_favor",
                        "posicao_posterior": "contra",
                    }
                ]
                if eh_mudou
                else []
            ),
            "indice_volatilidade": 0.6 if eh_mudou else 0.05 + (idx % 5) * 0.01,
        }
        parlamentares[pid] = bloco
    return {
        "parlamentares": parlamentares,
        "metadata": {
            "granularidade": "ano",
            "threshold_pp": 30.0,
            "n_parlamentares": n_parlamentares,
            "n_com_mudancas": n_com_mudancas,
            "skipped": False,
        },
    }


def _gravar_artefatos_completos(sessao_dir: Path, n: int = 40) -> None:
    """Grava os 3 artefatos pré-requisito da S34."""
    historico = _historico_grande(n_parlamentares=n, n_com_mudancas=n // 2)
    rede: dict[str, object] = {
        "coautoria": {"skipped": True, "motivo": "irrelevante"},
        "voto": {
            "skipped": False,
            "n_nos": n,
            "n_arestas": n * 3,
            "maior_componente": n,
            "n_comunidades": 4,
            "top_centrais": [
                {
                    "parlamentar_id": 100 + idx,
                    "centralidade_grau": 0.1 + (idx % 5) * 0.05,
                    "centralidade_intermediacao": 0.05 + (idx % 7) * 0.02,
                }
                for idx in range(1, n + 1)
            ],
        },
    }
    classif: dict[str, object] = {
        "topico": "aborto",
        "n_props": 50,
        "n_parlamentares": n,
        "camadas": ["regex", "votos", "tfidf"],
        "top_a_favor": [
            {
                "parlamentar_id": 100 + idx,
                "nome": f"Parlamentar {100 + idx}",
                "proporcao_sim": 0.7,
                "n_votos": 15 + idx,
            }
            for idx in range(1, n // 2 + 1)
        ],
        "top_contra": [
            {
                "parlamentar_id": 100 + idx,
                "nome": f"Parlamentar {100 + idx}",
                "proporcao_sim": 0.2,
                "n_votos": 15 + idx,
            }
            for idx in range(n // 2 + 1, n + 1)
        ],
    }
    (sessao_dir / "historico_conversao.json").write_text(
        json.dumps(historico, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sessao_dir / "metricas_rede.json").write_text(
        json.dumps(rede, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sessao_dir / "classificacao_c1_c2.json").write_text(
        json.dumps(classif, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _LogStub:
    def info(self, *args: object, **kwargs: object) -> None: ...
    def warning(self, *args: object, **kwargs: object) -> None: ...
    def exception(self, *args: object, **kwargs: object) -> None: ...


# ---------------------------------------------------------------------------
# Testes E2E
# ---------------------------------------------------------------------------


def test_etapa_convertibilidade_em_sessao_real(tmp_path: Path) -> None:
    """``_etapa_convertibilidade`` produz scores JSON + modelo persistido."""
    from hemiciclo.sessao.pipeline import _etapa_convertibilidade

    sessao_dir = tmp_path / "sessao_conv"
    updater = _criar_sessao_pronta(sessao_dir, "teste_conv")
    _gravar_artefatos_completos(sessao_dir, n=40)

    _etapa_convertibilidade(sessao_dir, updater, _LogStub())

    destino = sessao_dir / "convertibilidade_scores.json"
    assert destino.is_file()
    payload = json.loads(destino.read_text(encoding="utf-8"))
    assert payload["skipped"] is False
    assert payload["n_amostra"] == 40  # noqa: PLR2004
    assert isinstance(payload["scores"], list)
    assert len(payload["scores"]) > 0
    # Modelo persistido
    assert (sessao_dir / "modelo_convertibilidade" / "convertibilidade.joblib").is_file()
    assert (sessao_dir / "modelo_convertibilidade" / "convertibilidade.meta.json").is_file()


def test_etapa_convertibilidade_skip_graceful_sem_artefatos(tmp_path: Path) -> None:
    """Sem features pré-requisito -> JSON com ``skipped=True``, sem levantar."""
    from hemiciclo.sessao.pipeline import _etapa_convertibilidade

    sessao_dir = tmp_path / "sessao_vazia"
    updater = _criar_sessao_pronta(sessao_dir, "teste_skip")
    _etapa_convertibilidade(sessao_dir, updater, _LogStub())

    destino = sessao_dir / "convertibilidade_scores.json"
    assert destino.is_file()
    payload = json.loads(destino.read_text(encoding="utf-8"))
    assert payload["skipped"] is True
    assert payload["scores"] == []


def test_workflow_cli_convertibilidade_treinar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI ``hemiciclo convertibilidade treinar`` ponta-a-ponta."""
    from typer.testing import CliRunner

    from hemiciclo.cli import app

    home = tmp_path / "home_conv"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    sessao_dir = home / "sessoes" / "cli_conv"
    sessao_dir.mkdir(parents=True)
    _gravar_artefatos_completos(sessao_dir, n=40)

    runner = CliRunner()
    resultado = runner.invoke(
        app,
        ["convertibilidade", "treinar", "cli_conv", "--top-n", "20"],
    )
    assert resultado.exit_code == 0, resultado.stdout
    payload = json.loads((sessao_dir / "convertibilidade_scores.json").read_text(encoding="utf-8"))
    assert payload["skipped"] is False
    assert len(payload["scores"]) == 20  # noqa: PLR2004
