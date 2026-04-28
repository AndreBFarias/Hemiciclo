"""Testes de :mod:`hemiciclo._sessao_worker` (S29).

Cobre resolução do callable, propagação de erro e fluxo feliz quando
invocado em-processo (sem subprocess), pra exercitar todos os ramos.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import pytest

from hemiciclo._sessao_worker import _resolver_callable, main
from hemiciclo.sessao.modelo import Casa, EstadoSessao, ParametrosBusca
from hemiciclo.sessao.persistencia import carregar_status, salvar_params


def test_resolver_callable_ok() -> None:
    """Spec ``modulo:funcao`` válida resolve para o callable."""
    funcao = _resolver_callable("hemiciclo.sessao.runner:_pipeline_dummy")
    assert callable(funcao)


def test_resolver_callable_sem_dois_pontos_levanta() -> None:
    """Spec sem ``:`` é rejeitada."""
    with pytest.raises(ValueError, match="callable_path inválido"):
        _resolver_callable("hemiciclo.sessao.runner._pipeline_dummy")


def test_resolver_callable_modulo_inexistente() -> None:
    """Módulo inexistente -> ImportError."""
    with pytest.raises(ImportError):
        _resolver_callable("hemiciclo.modulo_que_nao_existe:func")


def test_resolver_callable_atributo_inexistente() -> None:
    """Função inexistente no módulo -> AttributeError."""
    with pytest.raises(AttributeError):
        _resolver_callable("hemiciclo.sessao.runner:funcao_que_nao_existe")


def test_resolver_callable_nao_callable() -> None:
    """Spec apontando pra objeto não callable -> TypeError."""
    with pytest.raises(TypeError, match="não-callable"):
        _resolver_callable("hemiciclo.sessao.runner:UTC")  # constante, não função


def _prepara_pasta_sessao(sessao_dir: Path) -> None:
    """Cria pasta da sessão com params + status iniciais válidos."""
    sessao_dir.mkdir(parents=True)
    salvar_params(
        ParametrosBusca(topico="aborto", casas=[Casa.CAMARA], legislaturas=[57]),
        sessao_dir / "params.json",
    )


def test_worker_sem_params_falha(tmp_path: Path) -> None:
    """Pasta sem ``params.json`` -> exit 1, stderr informativo."""
    sessao_dir = tmp_path / "vazia"
    sessao_dir.mkdir()
    rc = main(
        [
            "--callable",
            "hemiciclo.sessao.runner:_pipeline_dummy",
            "--sessao-dir",
            str(sessao_dir),
        ]
    )
    assert rc == 1


def test_worker_callable_invalido_marca_erro(tmp_path: Path) -> None:
    """Spec inválida do callable -> exit 1 + status ERRO."""
    sessao_dir = tmp_path / "alvo"
    _prepara_pasta_sessao(sessao_dir)
    # Cria status inicial pro StatusUpdater encontrar.
    from datetime import datetime

    from hemiciclo.sessao.modelo import StatusSessao
    from hemiciclo.sessao.persistencia import salvar_status

    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id="alvo",
            estado=EstadoSessao.CRIADA,
            progresso_pct=0.0,
            etapa_atual="criada",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )

    rc = main(
        [
            "--callable",
            "spec_invalida_sem_dois_pontos",
            "--sessao-dir",
            str(sessao_dir),
        ]
    )
    assert rc == 1

    status = carregar_status(sessao_dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.ERRO
    assert status.erro is not None
    assert "ValueError" in status.erro


def test_worker_callable_que_levanta_marca_erro(tmp_path: Path) -> None:
    """Pipeline que levanta exceção -> exit 1 + status ERRO."""
    from datetime import datetime

    from hemiciclo.sessao.modelo import StatusSessao
    from hemiciclo.sessao.persistencia import salvar_status

    sessao_dir = tmp_path / "erra"
    _prepara_pasta_sessao(sessao_dir)
    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id="erra",
            estado=EstadoSessao.CRIADA,
            progresso_pct=0.0,
            etapa_atual="criada",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )

    rc = main(
        [
            "--callable",
            "tests.unit.test_sessao_worker:_pipeline_que_levanta",
            "--sessao-dir",
            str(sessao_dir),
        ]
    )
    assert rc == 1
    status = carregar_status(sessao_dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.ERRO
    assert "RuntimeError" in (status.erro or "")


def _pipeline_que_levanta(*_args: object, **_kwargs: object) -> None:
    """Pipeline propositalmente quebrado -- pra exercitar caminho ERRO."""
    msg = "boom proposital"
    raise RuntimeError(msg)


def test_worker_pipeline_dummy_em_processo(tmp_path: Path) -> None:
    """Roda o pipeline dummy via worker em-processo e verifica CONCLUIDA."""
    from datetime import datetime

    from hemiciclo.sessao.modelo import StatusSessao
    from hemiciclo.sessao.persistencia import salvar_status

    sessao_dir = tmp_path / "feliz"
    _prepara_pasta_sessao(sessao_dir)
    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id="feliz",
            estado=EstadoSessao.CRIADA,
            progresso_pct=0.0,
            etapa_atual="criada",
            mensagem="",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        sessao_dir / "status.json",
    )

    rc = main(
        [
            "--callable",
            "hemiciclo.sessao.runner:_pipeline_dummy",
            "--sessao-dir",
            str(sessao_dir),
        ]
    )
    assert rc == 0
    status = carregar_status(sessao_dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.CONCLUIDA
    assert status.progresso_pct == 100.0
    assert (sessao_dir / "dummy_artefato.txt").exists()
