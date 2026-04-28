"""Entrypoint do subprocess da Sessão de Pesquisa.

Invocado pelo :class:`hemiciclo.sessao.runner.SessaoRunner` via::

    python -m hemiciclo._sessao_worker \
        --callable hemiciclo.sessao.runner:_pipeline_dummy \
        --sessao-dir /home/usuario/hemiciclo/sessoes/<id>

Mora **fora** de ``hemiciclo.sessao`` propositalmente -- é um cidadão
top-level do pacote pra evitar import circular com o próprio runner que o
spawnsa, e pra que ``python -m hemiciclo._sessao_worker`` resolva sem
nenhum import lazy do submódulo.

Resolve o callable via :mod:`importlib`, carrega ``params.json`` da pasta
da sessão, instancia :class:`StatusUpdater` e invoca o callable. Se algo
levantar exceção, marca a sessão como ``ERRO`` com a mensagem.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from hemiciclo.sessao.modelo import EstadoSessao, ParametrosBusca
from hemiciclo.sessao.persistencia import carregar_params
from hemiciclo.sessao.runner import StatusUpdater

# Assinatura canônica de pipelines de sessão.
PipelineCallable = Callable[[ParametrosBusca, Path, StatusUpdater], None]


def _resolver_callable(spec: str) -> PipelineCallable:
    """Resolve ``modulo.submodulo:funcao`` em callable importável.

    Args:
        spec: Especificação no formato ``modulo:funcao``. Aceita pontos
            no caminho do módulo. Recusa specs sem ``:``.

    Raises:
        ValueError: Se ``spec`` não tem ``:``.
        ImportError / AttributeError: Propaga falhas do importlib.
    """
    if ":" not in spec:
        msg = f"callable_path inválido: {spec!r} (esperado 'modulo:funcao')"
        raise ValueError(msg)
    nome_modulo, nome_func = spec.split(":", 1)
    modulo = importlib.import_module(nome_modulo)
    funcao = getattr(modulo, nome_func)
    if not callable(funcao):
        msg = f"{spec!r} resolveu para objeto não-callable"
        raise TypeError(msg)
    return funcao  # type: ignore[no-any-return]  # contrato é responsabilidade do chamador


def main(argv: list[str] | None = None) -> int:
    """Executa o callable da sessão. Retorna exit code (0 = ok, 1 = erro)."""
    parser = argparse.ArgumentParser(prog="hemiciclo._sessao_worker")
    parser.add_argument("--callable", required=True, dest="callable_path")
    parser.add_argument("--sessao-dir", required=True, dest="sessao_dir")
    args = parser.parse_args(argv)

    sessao_dir = Path(args.sessao_dir)
    params = carregar_params(sessao_dir / "params.json")
    if params is None:
        # Sem params, nem dá pra reportar via StatusUpdater porque o id
        # da sessão derivava do nome da pasta. Recupera via path.
        sys.stderr.write(f"_sessao_worker: params.json ausente ou corrompido em {sessao_dir}\n")
        return 1

    id_sessao = sessao_dir.name
    updater = StatusUpdater(sessao_dir, id_sessao)

    try:
        funcao = _resolver_callable(args.callable_path)
    except (ValueError, TypeError, ImportError, AttributeError) as exc:
        updater.atualizar(
            EstadoSessao.ERRO,
            0.0,
            "erro",
            mensagem="Falha ao resolver callable da sessão.",
            erro=f"{type(exc).__name__}: {exc}",
        )
        sys.stderr.write(f"_sessao_worker: {exc}\n")
        return 1

    try:
        funcao(params, sessao_dir, updater)
    except Exception as exc:  # noqa: BLE001 -- queremos pegar tudo no worker.
        updater.atualizar(
            EstadoSessao.ERRO,
            0.0,
            "erro",
            mensagem="Pipeline falhou com exceção não tratada.",
            erro=f"{type(exc).__name__}: {exc}",
        )
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
