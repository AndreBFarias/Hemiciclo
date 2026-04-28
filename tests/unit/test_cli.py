"""Testes da CLI ``hemiciclo sessao iniciar`` -- flags S30.2.

Cobre as flags repetíveis ``--uf``/``-u`` e ``--partido``/``-p`` adicionadas
nesta sprint. Não dispara subprocess real: monkeypatch em
``SessaoRunner.iniciar`` para capturar os ``ParametrosBusca`` construídos.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hemiciclo.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """Runner Typer reutilizável."""
    return CliRunner()


def _patch_sessao_runner(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Monkeypatch ``SessaoRunner.__init__`` + ``.iniciar`` para captura.

    Devolve a lista que recebe o ``params`` capturado em cada invocação
    -- útil para asserções sobre os campos finais do
    :class:`ParametrosBusca` repassado.
    """
    from hemiciclo.sessao import runner as runner_module

    chamadas: list[object] = []
    original_init = runner_module.SessaoRunner.__init__

    def _fake_init(self: object, home: Path, params: object, **_: object) -> None:
        chamadas.append(params)
        original_init(self, home, params)  # type: ignore[arg-type]

    monkeypatch.setattr(runner_module.SessaoRunner, "__init__", _fake_init)
    monkeypatch.setattr(
        runner_module.SessaoRunner,
        "iniciar",
        lambda self, _path: 99999,
    )
    return chamadas


def test_sessao_iniciar_com_uf_repetido_passa_para_params(
    runner: CliRunner,
    tmp_hemiciclo_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--uf SP --uf RJ`` chega como ``params.ufs == ['SP', 'RJ']``."""
    chamadas = _patch_sessao_runner(monkeypatch)
    resultado = runner.invoke(
        app,
        [
            "sessao",
            "iniciar",
            "--topico",
            "aborto",
            "--uf",
            "SP",
            "--uf",
            "RJ",
            "--dummy",
        ],
    )
    assert resultado.exit_code == 0, resultado.stdout
    assert "pid=99999" in resultado.stdout
    assert chamadas, "SessaoRunner não foi instanciado"
    params_capturados = chamadas[0]
    assert getattr(params_capturados, "ufs") == ["SP", "RJ"]  # noqa: B009
    assert getattr(params_capturados, "partidos") is None  # noqa: B009


def test_sessao_iniciar_com_partido_repetido_passa_para_params(
    runner: CliRunner,
    tmp_hemiciclo_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--partido PT --partido PSOL`` chega como ``params.partidos``."""
    chamadas = _patch_sessao_runner(monkeypatch)
    resultado = runner.invoke(
        app,
        [
            "sessao",
            "iniciar",
            "--topico",
            "aborto",
            "--partido",
            "PT",
            "--partido",
            "PSOL",
            "--dummy",
        ],
    )
    assert resultado.exit_code == 0, resultado.stdout
    assert chamadas, "SessaoRunner não foi instanciado"
    params_capturados = chamadas[0]
    assert getattr(params_capturados, "partidos") == ["PT", "PSOL"]  # noqa: B009
    assert getattr(params_capturados, "ufs") is None  # noqa: B009


def test_sessao_iniciar_uf_invalida_emite_erro_amigavel(
    runner: CliRunner,
    tmp_hemiciclo_home: Path,
) -> None:
    """``--uf XX`` é rejeitado pelo validador Pydantic com mensagem amigável.

    Pós S30.2 a CLI captura ``ValidationError`` e converte em
    ``typer.Exit(2)`` com texto em vermelho contendo "UF inválida".
    """
    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--uf", "XX", "--dummy"],
    )
    assert resultado.exit_code == 2
    saida = resultado.stdout.lower()
    assert "parâmetros inválidos" in saida
    assert "uf" in saida


def test_sessao_iniciar_sem_filtros_default_eh_none(
    runner: CliRunner,
    tmp_hemiciclo_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem ``--uf`` nem ``--partido``, ambos os campos viram ``None``.

    Sentinela complementar (não conta para a aritmética da sprint, mas
    documenta o comportamento default explicitamente).
    """
    chamadas = _patch_sessao_runner(monkeypatch)
    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--dummy"],
    )
    assert resultado.exit_code == 0, resultado.stdout
    params_capturados = chamadas[0]
    assert getattr(params_capturados, "ufs") is None  # noqa: B009
    assert getattr(params_capturados, "partidos") is None  # noqa: B009
