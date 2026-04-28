"""CLI Hemiciclo via Typer.

Entry-points expostos:

- ``hemiciclo --version`` -- imprime ``hemiciclo <versao>`` e sai com código 0.
- ``hemiciclo info`` -- imprime paths configurados, modelo base detectado e
  contagem de sessões existentes.
- ``hemiciclo dashboard`` -- sobe o dashboard Streamlit em localhost:8501
  (equivalente a ``./run.sh``).
- ``hemiciclo coletar camara ...`` -- coleta dados públicos da Câmara
  (proposições, votações, votos, discursos, deputados).
- ``hemiciclo coletar senado ...`` -- coleta dados públicos do Senado
  (matérias, votações, votos, discursos, senadores).
- ``hemiciclo db init ...`` -- cria/atualiza schema do DuckDB analítico.
- ``hemiciclo db consolidar ...`` -- carrega parquets de coleta no DuckDB.
- ``hemiciclo db info ...`` -- mostra contagens por tabela e versão do schema.
- ``hemiciclo classificar ...`` -- classifica um tópico (camadas C1+C2)
  contra o DuckDB unificado e produz JSON com top a-favor / top contra.
- ``hemiciclo modelo base baixar/treinar/carregar/info`` -- modelo base v1
  (C3): bge-m3 + PCA + persistência com integridade SHA256 (S28).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import cast

import typer
from rich.console import Console

from hemiciclo import __version__
from hemiciclo.coleta import ParametrosColeta, TipoColeta
from hemiciclo.config import Configuracao

app = typer.Typer(
    name="hemiciclo",
    help="Plataforma cidadã de perfilamento parlamentar.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console(soft_wrap=True)

coletar_app = typer.Typer(
    name="coletar",
    help="Coleta dados públicos do Congresso Nacional.",
    no_args_is_help=True,
)
app.add_typer(coletar_app, name="coletar")

db_app = typer.Typer(
    name="db",
    help="Banco analítico DuckDB unificado (proposições, votações, votos, discursos).",
    no_args_is_help=True,
)
app.add_typer(db_app, name="db")

sessao_app = typer.Typer(
    name="sessao",
    help="Sessões de Pesquisa: runner subprocess, status, retomada (S29).",
    no_args_is_help=True,
)
app.add_typer(sessao_app, name="sessao")

modelo_app = typer.Typer(
    name="modelo",
    help="Modelo base v1 (C3): bge-m3 + PCA + persistência com SHA256 (S28).",
    no_args_is_help=True,
)
app.add_typer(modelo_app, name="modelo")

rede_app = typer.Typer(
    name="rede",
    help="Grafos de rede parlamentar: coautoria + afinidade de voto (S32).",
    no_args_is_help=True,
)
app.add_typer(rede_app, name="rede")

historico_app = typer.Typer(
    name="historico",
    help="Histórico de conversão por parlamentar (volatilidade -- S33).",
    no_args_is_help=True,
)
app.add_typer(historico_app, name="historico")

convertibilidade_app = typer.Typer(
    name="convertibilidade",
    help="ML de convertibilidade (LogisticRegression sobre features S32+S33+S27 -- S34).",
    no_args_is_help=True,
)
app.add_typer(convertibilidade_app, name="convertibilidade")

modelo_base_app = typer.Typer(
    name="base",
    help="Ações do modelo base v1: baixar bge-m3, treinar, carregar, info.",
    no_args_is_help=True,
)
modelo_app.add_typer(modelo_base_app, name="base")


def _versao_callback(value: bool) -> None:
    """Imprime a versão e encerra o CLI imediatamente."""
    if value:
        console.print(f"hemiciclo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(  # noqa: FBT001 -- flag CLI
        False,
        "--version",
        callback=_versao_callback,
        is_eager=True,
        help="Mostra a versão e sai.",
    ),
) -> None:
    """Hemiciclo -- inteligência política aberta, soberana, local."""


@app.command()
def info() -> None:
    """Mostra paths configurados e estado do ambiente local."""
    cfg = Configuracao()
    cfg.garantir_diretorios()

    modelo_base = cfg.modelos_dir / "base_v1.pkl"
    nome_modelo = modelo_base.name if modelo_base.exists() else "nenhum"

    sessoes = (
        sorted(p for p in cfg.sessoes_dir.iterdir() if p.is_dir())
        if cfg.sessoes_dir.exists()
        else []
    )

    console.print(f"[bold]Hemiciclo[/bold] {__version__}")
    console.print(f"Home: {cfg.home}")
    console.print(f"Modelos: {cfg.modelos_dir}")
    console.print(f"Sessões: {cfg.sessoes_dir}")
    console.print(f"Cache: {cfg.cache_dir}")
    console.print(f"Logs: {cfg.logs_dir}")
    console.print(f"Tópicos: {cfg.topicos_dir}")
    console.print(f"Modelo base: {nome_modelo}")
    console.print(f"Sessões existentes: {len(sessoes)}")
    console.print(f"Random state: {cfg.random_state}")


@app.command()
def dashboard(
    porta: int = typer.Option(8501, "--port", "-p", help="Porta TCP do Streamlit."),
    headless: bool = typer.Option(  # noqa: FBT001 -- flag CLI
        False,
        "--headless",
        help="Não abre o navegador automaticamente (default: abre).",
    ),
) -> None:
    """Sobe o dashboard Streamlit em localhost (default: porta 8501).

    Equivalente ao atalho ``./run.sh``. Útil em ambientes sem shell scripts
    (ex.: Windows fora do WSL, ou contêineres minimalistas).
    """
    streamlit_bin = shutil.which("streamlit")
    if streamlit_bin is None:
        console.print(
            "[red]streamlit não encontrado no PATH. "
            "Rode `make bootstrap` ou `uv sync --all-extras`.[/red]"
        )
        raise typer.Exit(code=1)

    app_path = Path(__file__).parent / "dashboard" / "app.py"
    cmd = [
        streamlit_bin,
        "run",
        str(app_path),
        f"--server.port={porta}",
        f"--server.headless={'true' if headless else 'false'}",
    ]
    console.print(f"[bold]Hemiciclo[/bold] dashboard em http://localhost:{porta}")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        console.print("\n[Hemiciclo] Encerrando dashboard...")
        sys.exit(0)


@coletar_app.command("camara")
def coletar_camara(
    legislatura: list[int] = typer.Option(  # noqa: B008 -- typer pattern
        ...,
        "--legislatura",
        "-l",
        help="Legislatura(s) a coletar. Pode ser repetido: --legislatura 56 --legislatura 57.",
    ),
    tipos: list[str] = typer.Option(  # noqa: B008 -- typer pattern
        ["proposicoes"],
        "--tipos",
        "-t",
        help="Tipos: proposicoes, votacoes, votos, discursos, deputados.",
    ),
    data_inicio: str | None = typer.Option(
        None,
        "--data-inicio",
        help="Data inicial ISO (ex.: 2023-02-01). Necessária para votações e discursos.",
    ),
    data_fim: str | None = typer.Option(
        None,
        "--data-fim",
        help="Data final ISO (ex.: 2026-04-28).",
    ),
    max_itens: int | None = typer.Option(
        None,
        "--max-itens",
        help="Limite total de itens por tipo (útil em smoke tests).",
    ),
    output: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--output",
        "-o",
        help="Diretório de saída dos Parquet. Default: ~/hemiciclo/cache/camara/.",
    ),
    enriquecer_proposicoes: bool = typer.Option(
        True,
        "--enriquecer-proposicoes/--no-enriquecer-proposicoes",
        help=(
            "S24b: após coleta listagem, busca detalhe via "
            "GET /proposicoes/{id} para preencher tema_oficial, "
            "autor_principal, status e url_inteiro_teor. Default: ligado."
        ),
    ),
) -> None:
    """Coleta dados públicos da Câmara dos Deputados.

    Exemplos::

        hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 100
        hemiciclo coletar camara -l 56 -l 57 -t proposicoes -t votacoes
    """
    from hemiciclo.coleta.camara import executar_coleta

    cfg = Configuracao()
    cfg.garantir_diretorios()

    saida = output if output is not None else cfg.cache_dir / "camara"
    saida.mkdir(parents=True, exist_ok=True)

    di = date.fromisoformat(data_inicio) if data_inicio else None
    df_ = date.fromisoformat(data_fim) if data_fim else None

    tipos_validos: set[str] = {"proposicoes", "votacoes", "votos", "discursos", "deputados"}
    for t in tipos:
        if t not in tipos_validos:
            console.print(f"[red]Tipo inválido: {t}. Válidos: {sorted(tipos_validos)}[/red]")
            raise typer.Exit(code=2)

    params = ParametrosColeta(
        legislaturas=list(legislatura),
        tipos=cast(list[TipoColeta], list(tipos)),
        data_inicio=di,
        data_fim=df_,
        max_itens=max_itens,
        dir_saida=saida,
        enriquecer_proposicoes=enriquecer_proposicoes,
    )

    console.print(
        f"[bold]Hemiciclo[/bold] coletar camara: legislaturas={params.legislaturas} "
        f"tipos={params.tipos} max_itens={params.max_itens} -> {saida}"
    )

    inicio = time.monotonic()
    checkpoint = executar_coleta(params, home=cfg.home)
    duracao = time.monotonic() - inicio

    total = checkpoint.total_baixado()
    console.print(
        f"[coleta][camara] {total} itens baixados em {duracao:.1f}s ({len(checkpoint.erros)} erros)"
    )


@coletar_app.command("senado")
def coletar_senado(
    legislatura: list[int] = typer.Option(  # noqa: B008 -- typer pattern
        [],
        "--legislatura",
        "-l",
        help="Legislatura(s) a coletar. Pode ser repetido. Alternativa a --ano.",
    ),
    ano: list[int] = typer.Option(  # noqa: B008 -- typer pattern
        [],
        "--ano",
        "-a",
        help="Ano(s) alvo. Mais granular que legislatura. Pode ser repetido.",
    ),
    tipos: list[str] = typer.Option(  # noqa: B008 -- typer pattern
        ["materias"],
        "--tipos",
        "-t",
        help="Tipos: materias, votacoes, votos, discursos, senadores.",
    ),
    max_itens: int | None = typer.Option(
        None,
        "--max-itens",
        help="Limite total de itens por tipo (útil em smoke tests).",
    ),
    output: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--output",
        "-o",
        help="Diretório de saída dos Parquet. Default: ~/hemiciclo/cache/senado/.",
    ),
) -> None:
    """Coleta dados públicos do Senado Federal.

    Exemplos::

        hemiciclo coletar senado --ano 2024 --tipos materias --max-itens 50
        hemiciclo coletar senado -l 56 -t materias -t votacoes
    """
    from datetime import date as _d

    from hemiciclo.coleta.senado import executar_coleta

    cfg = Configuracao()
    cfg.garantir_diretorios()

    saida = output if output is not None else cfg.cache_dir / "senado"
    saida.mkdir(parents=True, exist_ok=True)

    tipos_validos: set[str] = {"materias", "votacoes", "votos", "discursos", "senadores"}
    for t in tipos:
        if t not in tipos_validos:
            console.print(f"[red]Tipo inválido: {t}. Válidos: {sorted(tipos_validos)}[/red]")
            raise typer.Exit(code=2)

    # Pelo menos um de legislatura ou ano precisa estar presente. Se nenhum,
    # default para legislatura 56 (compatível com ParametrosColeta que exige
    # ``legislaturas`` não vazio).
    legs_finais: list[int] = list(legislatura) if legislatura else []
    if not legs_finais and not ano:
        legs_finais = [56]
    elif not legs_finais and ano:
        legs_finais = [56]  # placeholder; coletor usa data_inicio/data_fim

    di: _d | None = None
    df_: _d | None = None
    if ano:
        anos_ord = sorted(set(ano))
        di = _d(anos_ord[0], 1, 1)
        df_ = _d(anos_ord[-1], 12, 31)

    params = ParametrosColeta(
        legislaturas=legs_finais,
        tipos=cast(list[TipoColeta], list(tipos)),
        data_inicio=di,
        data_fim=df_,
        max_itens=max_itens,
        dir_saida=saida,
    )

    console.print(
        f"[bold]Hemiciclo[/bold] coletar senado: legislaturas={params.legislaturas} "
        f"anos={ano} tipos={params.tipos} max_itens={params.max_itens} -> {saida}"
    )

    inicio = time.monotonic()
    checkpoint = executar_coleta(params, home=cfg.home)
    duracao = time.monotonic() - inicio

    total = checkpoint.total_baixado()
    console.print(
        f"[coleta][senado] {total} itens baixados em {duracao:.1f}s ({len(checkpoint.erros)} erros)"
    )


def _db_path_default(cfg: Configuracao) -> Path:
    """Resolve path canônico ``<home>/cache/hemiciclo.duckdb`` quando flag ausente."""
    return cfg.cache_dir / "hemiciclo.duckdb"


@db_app.command("init")
def db_init(
    db_path: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--db-path",
        help="Caminho do arquivo DuckDB. Default: ~/hemiciclo/cache/hemiciclo.duckdb.",
    ),
) -> None:
    """Cria (ou atualiza) o schema DuckDB aplicando todas as migrations pendentes.

    Idempotente: rodar múltiplas vezes não duplica tabelas nem entradas em
    ``_migrations``.
    """
    import duckdb

    from hemiciclo.etl.migrations import aplicar_migrations, versao_atual

    cfg = Configuracao()
    cfg.garantir_diretorios()
    destino = db_path if db_path is not None else _db_path_default(cfg)
    destino.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(destino))
    try:
        aplicadas = aplicar_migrations(conn)
        versao = versao_atual(conn)
    finally:
        conn.close()
    console.print(
        f"[db][init] schema v{versao} ativo em {destino} "
        f"({aplicadas} migrations aplicadas nesta chamada)"
    )


@db_app.command("consolidar")
def db_consolidar(
    parquets: Path = typer.Option(  # noqa: B008 -- typer pattern com Path
        ...,
        "--parquets",
        help="Diretório com parquets gerados por `hemiciclo coletar`.",
    ),
    db_path: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--db-path",
        help="Caminho do arquivo DuckDB. Default: ~/hemiciclo/cache/hemiciclo.duckdb.",
    ),
) -> None:
    """Carrega parquets de S24/S25 no DuckDB unificado via INSERT OR IGNORE."""
    from hemiciclo.etl.consolidador import consolidar_parquets_em_duckdb

    cfg = Configuracao()
    cfg.garantir_diretorios()
    destino = db_path if db_path is not None else _db_path_default(cfg)

    if not parquets.exists():
        console.print(f"[red]Diretório inexistente: {parquets}[/red]")
        raise typer.Exit(code=2)

    inicio = time.monotonic()
    contagens = consolidar_parquets_em_duckdb(parquets, destino)
    duracao = time.monotonic() - inicio

    if not contagens:
        console.print(f"[db][consolidar] nada novo em {parquets} -> {destino} ({duracao:.2f}s)")
        return
    for tabela, n in sorted(contagens.items()):
        console.print(f"[db][consolidar] {tabela}: +{n} linhas")
    console.print(f"[db][consolidar] concluído em {duracao:.2f}s -> {destino}")


@db_app.command("info")
def db_info(
    db_path: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--db-path",
        help="Caminho do arquivo DuckDB. Default: ~/hemiciclo/cache/hemiciclo.duckdb.",
    ),
) -> None:
    """Mostra a versão do schema e a contagem por tabela."""
    import duckdb

    from hemiciclo.etl.migrations import aplicar_migrations, versao_atual

    cfg = Configuracao()
    cfg.garantir_diretorios()
    destino = db_path if db_path is not None else _db_path_default(cfg)

    conn = duckdb.connect(str(destino))
    try:
        # Aplica migrations antes de ler -- garante info consistente em DB recém-criado.
        aplicar_migrations(conn)
        versao = versao_atual(conn)
        tabelas = ("proposicoes", "votacoes", "votos", "discursos", "parlamentares")
        contagens: dict[str, int] = {}
        for t in tabelas:
            linha = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            contagens[t] = int(linha[0]) if linha else 0
    finally:
        conn.close()

    console.print(f"[db][info] schema v{versao} em {destino}")
    for t in tabelas:
        console.print(f"[db][info] {t}: {contagens[t]}")


@app.command("classificar")
def classificar_cmd(
    topico: Path = typer.Option(  # noqa: B008 -- typer pattern com Path
        ...,
        "--topico",
        help="Caminho do YAML do tópico (ex.: topicos/aborto.yaml).",
    ),
    db_path: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--db-path",
        help="DuckDB analítico. Default: ~/hemiciclo/cache/hemiciclo.duckdb.",
    ),
    camadas: str = typer.Option(
        "regex,votos,tfidf",
        "--camadas",
        help="Camadas a aplicar (csv). Validas: regex, votos, tfidf.",
    ),
    top_n: int = typer.Option(
        100,
        "--top-n",
        help="Tamanho dos rankings top_a_favor / top_contra.",
    ),
    output: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--output",
        "-o",
        help="Se presente, serializa o resultado como JSON em <output>.",
    ),
) -> None:
    """Classifica um tópico contra o DuckDB unificado (C1+C2).

    Exemplos::

        hemiciclo classificar --topico topicos/aborto.yaml
        hemiciclo classificar --topico topicos/aborto.yaml \\
            --camadas regex,votos --output /tmp/r.json
    """
    from hemiciclo.modelos.classificador import (
        CAMADAS_VALIDAS,
        classificar,
        salvar_resultado_json,
    )

    cfg = Configuracao()
    cfg.garantir_diretorios()
    destino_db = db_path if db_path is not None else _db_path_default(cfg)

    if not topico.exists():
        console.print(f"[red]Tópico inexistente: {topico}[/red]")
        raise typer.Exit(code=2)
    if not destino_db.exists():
        console.print(f"[red]DB inexistente: {destino_db}. Rode `hemiciclo db init`.[/red]")
        raise typer.Exit(code=2)

    camadas_lista = [c.strip() for c in camadas.split(",") if c.strip()]
    invalidas = set(camadas_lista) - CAMADAS_VALIDAS
    if invalidas:
        console.print(
            f"[red]Camadas inválidas: {sorted(invalidas)}. "
            f"Válidas: {sorted(CAMADAS_VALIDAS)}.[/red]"
        )
        raise typer.Exit(code=2)

    inicio = time.monotonic()
    resultado = classificar(
        topico_yaml=topico,
        db_path=destino_db,
        camadas=camadas_lista,
        top_n=top_n,
    )
    duracao = time.monotonic() - inicio

    console.print(
        f"[classificar] topico={resultado['topico']} "
        f"props={resultado['n_props']} "
        f"parlamentares={resultado['n_parlamentares']} "
        f"em {duracao:.2f}s "
        f"camadas={resultado['camadas']}"
    )

    if output is not None:
        salvar_resultado_json(resultado, output)
        console.print(f"[classificar] topico={resultado['topico']} JSON em {output}")


# ---------------------------------------------------------------------------
# Subcomando `hemiciclo sessao` (S29)
# ---------------------------------------------------------------------------


_PIPELINE_DUMMY_PATH = "hemiciclo.sessao.runner:_pipeline_dummy"
_PIPELINE_REAL_PATH = "hemiciclo.sessao.pipeline:pipeline_real"


@sessao_app.command("iniciar")
def sessao_iniciar(
    topico: str = typer.Option(
        ...,
        "--topico",
        help="Texto livre OU id de YAML curado em ~/hemiciclo/topicos/.",
    ),
    casas: list[str] = typer.Option(  # noqa: B008 -- typer pattern
        ["camara", "senado"],
        "--casas",
        "-c",
        help="Casas legislativas alvo. Pode ser repetido. Default: camara senado.",
    ),
    legislaturas: list[int] = typer.Option(  # noqa: B008 -- typer pattern
        [57],
        "--legislatura",
        "-l",
        help="Legislatura(s) alvo. Default: 57.",
    ),
    ufs: list[str] = typer.Option(  # noqa: B008 -- typer pattern
        [],
        "--uf",
        "-u",
        help="UF(s) alvo. Pode ser repetido. Default: todas as 27.",
    ),
    partidos: list[str] = typer.Option(  # noqa: B008 -- typer pattern
        [],
        "--partido",
        "-p",
        help="Sigla(s) de partido. Pode ser repetido. Default: todos.",
    ),
    max_itens: int | None = typer.Option(
        None,
        "--max-itens",
        help=(
            "Limite de itens por tipo coletado por casa (default sem limite). "
            "Útil para smoke local e dashboards rápidos. "
            "Ex.: --max-itens 50 coleta até 50 proposições da Câmara e 50 do Senado."
        ),
    ),
    dummy: bool = typer.Option(  # noqa: FBT001 -- typer flag
        False,
        "--dummy",
        help="Usa pipeline DUMMY (compat S29) em vez do pipeline real.",
    ),
) -> None:
    """Cria sessão e dispara pipeline em subprocess detached.

    Default: pipeline REAL (S30) com coleta -> ETL -> C1+C2+C3 -> relatório.
    Use ``--dummy`` para forçar o pipeline DUMMY herdado da S29 (útil em
    testes locais sem rede ou sem modelo base treinado).

    Filtros (S30.2): ``--uf`` e ``--partido`` são repetíveis e aplicados
    no pipeline pós-ETL (etapa C1+C2). Lista vazia = sem filtro nesse
    eixo. Combinação é AND lógico.
    """
    from pydantic import ValidationError

    from hemiciclo.sessao import Casa, ParametrosBusca, SessaoRunner

    cfg = Configuracao()
    cfg.garantir_diretorios()

    try:
        casas_enum = [Casa(c) for c in casas]
    except ValueError as exc:
        console.print(f"[red]Casa inválida: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    try:
        params = ParametrosBusca(
            topico=topico,
            casas=casas_enum,
            legislaturas=list(legislaturas),
            ufs=ufs if ufs else None,
            partidos=partidos if partidos else None,
            max_itens=max_itens,
        )
    except ValidationError as exc:
        console.print(f"[red]Parâmetros inválidos: {exc}[/red]")
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        console.print(f"[red]Parâmetros inválidos: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    runner = SessaoRunner(cfg.home, params)
    callable_path = _PIPELINE_DUMMY_PATH if dummy else _PIPELINE_REAL_PATH
    pid = runner.iniciar(callable_path)
    console.print(
        f"sessao iniciar: sessao={runner.id_sessao} pid={pid} pipeline="
        f"{'dummy' if dummy else 'real'} ufs={ufs or '(todas)'} "
        f"partidos={partidos or '(todos)'}"
    )


@sessao_app.command("listar")
def sessao_listar() -> None:
    """Lista todas as sessões em ``~/hemiciclo/sessoes/`` ordenadas por data desc."""
    from hemiciclo.sessao import listar_sessoes

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessoes = listar_sessoes(cfg.home)
    if not sessoes:
        console.print("sessao listar: nenhuma sessão encontrada")
        return

    console.print(f"{'ID':<48} {'ESTADO':<14} {'PROGRESSO':<10} INICIADA_EM")
    for id_sessao, _params, status in sessoes:
        progresso = f"{status.progresso_pct:.1f}%"
        iniciada = status.iniciada_em.strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"{id_sessao:<48} {status.estado.value:<14} {progresso:<10} {iniciada}")


@sessao_app.command("status")
def sessao_status(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão (ver listar)."),
) -> None:
    """Mostra o ``status.json`` da sessão formatado em JSON indentado."""
    import json as _json

    from hemiciclo.sessao import caminho_sessao, carregar_status

    cfg = Configuracao()
    cfg.garantir_diretorios()
    status = carregar_status(caminho_sessao(cfg.home, id_sessao) / "status.json")
    if status is None:
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)
    console.print(_json.dumps(status.model_dump(mode="json"), ensure_ascii=False, indent=2))


@sessao_app.command("retomar")
def sessao_retomar(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão a retomar."),
) -> None:
    """Spawnsa novo subprocess do pipeline DUMMY pra sessão informada.

    Em S30 o callable será o pipeline real. Aqui retomamos o dummy só
    pra exercitar o caminho.
    """
    from hemiciclo.sessao import retomar

    cfg = Configuracao()
    cfg.garantir_diretorios()
    try:
        pid = retomar(cfg.home, id_sessao, _PIPELINE_DUMMY_PATH)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"sessao retomar: sessao={id_sessao} pid={pid}")


def _enviar_sinal(id_sessao: str, sinal: int, marcar_erro: bool) -> None:
    """Helper interno que mata o subprocess da sessão.

    Lê o ``pid.lock`` da pasta da sessão, envia ``sinal`` ao PID e
    opcionalmente marca a sessão como ``INTERROMPIDA``.
    """
    import os as _os

    from hemiciclo.sessao import caminho_sessao, marcar_interrompida

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    lock = sessao_dir / "pid.lock"
    if not lock.exists():
        console.print(f"[red]pid.lock ausente em {sessao_dir}[/red]")
        raise typer.Exit(code=2)
    try:
        pid = int(lock.read_text(encoding="utf-8").split("\n")[0].strip())
    except ValueError as exc:
        console.print(f"[red]pid.lock corrompido: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    try:
        _os.kill(pid, sinal)
    except ProcessLookupError:
        console.print(f"sessao: PID {pid} já não existe; só atualizando status.")
    except PermissionError as exc:
        console.print(f"[red]sem permissão pra sinalizar PID {pid}: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if marcar_erro:
        marcar_interrompida(sessao_dir, "Cancelada via CLI (SIGKILL)")


@sessao_app.command("pausar")
def sessao_pausar(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão a pausar."),
) -> None:
    """Envia SIGTERM ao subprocess da sessão (graceful)."""
    import signal as _signal

    sinal = (
        getattr(_signal, "SIGTERM", _signal.SIGINT) if sys.platform != "win32" else _signal.SIGTERM
    )
    _enviar_sinal(id_sessao, int(sinal), marcar_erro=False)
    console.print(f"sessao pausar: sessao={id_sessao} SIGTERM enviado")


@sessao_app.command("cancelar")
def sessao_cancelar(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão a cancelar."),
) -> None:
    """Envia SIGKILL ao subprocess e marca a sessão como INTERROMPIDA."""
    import signal as _signal

    sinal = (
        getattr(_signal, "SIGKILL", _signal.SIGTERM) if sys.platform != "win32" else _signal.SIGTERM
    )
    _enviar_sinal(id_sessao, int(sinal), marcar_erro=True)
    console.print(f"sessao cancelar: sessao={id_sessao} SIGKILL enviado")


@sessao_app.command("exportar")
def sessao_exportar(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão a exportar."),
    destino: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--destino",
        "-d",
        help="Caminho do .zip de saída. Default: ~/Downloads/<id>.zip.",
    ),
) -> None:
    """Exporta sessão como zip portável (sem dados.duckdb nem modelos_locais).

    O zip inclui ``params.json``, ``status.json``, ``manifesto.json``,
    ``relatorio_state.json``, ``classificacao_c1_c2.json`` e parquets de
    coleta. Caches pesados (DuckDB, modelos_locais) são reconstruídos no
    destino via ``hemiciclo db consolidar`` quando necessário.
    """
    from hemiciclo.sessao import caminho_sessao, exportar_zip

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    if not sessao_dir.is_dir():
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)

    if destino is None:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        destino = downloads / f"{id_sessao}.zip"

    saida = exportar_zip(sessao_dir, destino)
    tamanho_kb = saida.stat().st_size / 1024
    import zipfile as _zipfile

    with _zipfile.ZipFile(saida, "r") as zf:
        n_artefatos = len(zf.namelist())
    console.print(
        f"sessao exportar: zip={saida} tamanho={tamanho_kb:.1f}KB artefatos={n_artefatos}"
    )


@sessao_app.command("importar")
def sessao_importar(
    zip_path: Path = typer.Argument(  # noqa: B008 -- typer pattern com Path
        ..., help="Caminho do .zip exportado por `hemiciclo sessao exportar`."
    ),
    sem_validar: bool = typer.Option(  # noqa: FBT001 -- typer flag
        False,
        "--sem-validar",
        help="Pula a verificação de hashes contra manifesto.json (debug ou sessões antigas).",
    ),
) -> None:
    """Importa zip pra ``~/hemiciclo/sessoes/<id>/`` validando integridade.

    Se já existe sessão de mesmo id, sufixa ``_2``, ``_3`` etc até achar
    nome livre -- nunca sobrescreve.
    """
    import zipfile as _zipfile

    from hemiciclo.sessao import IntegridadeImportadaInvalida, importar_zip

    cfg = Configuracao()
    cfg.garantir_diretorios()

    if not zip_path.exists():
        console.print(f"[red]zip não encontrado: {zip_path}[/red]")
        raise typer.Exit(code=2)

    try:
        id_final = importar_zip(zip_path, cfg.home, validar=not sem_validar)
    except _zipfile.BadZipFile as exc:
        console.print(f"[red]zip inválido: {exc}[/red]")
        raise typer.Exit(code=2) from exc
    except IntegridadeImportadaInvalida as exc:
        console.print(f"[red]integridade violada: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    estado_validacao = "pulada" if sem_validar else "OK"
    console.print(f"sessao importar: sessao={id_final} validacao={estado_validacao}")


# ---------------------------------------------------------------------------
# Subcomando `hemiciclo modelo base` (S28)
# ---------------------------------------------------------------------------


@modelo_base_app.command("baixar")
def modelo_base_baixar() -> None:
    """Pré-baixa o modelo bge-m3 em ``~/hemiciclo/modelos/bge-m3/`` (~2GB).

    Útil para preparar ambiente offline. Faz lazy import do FlagEmbedding
    e instancia ``BGEM3FlagModel`` -- isso baixa pesos via huggingface_hub.
    """
    from hemiciclo.modelos.embeddings import WrapperEmbeddings, embeddings_disponivel

    cfg = Configuracao()
    cfg.garantir_diretorios()

    dir_bge = cfg.modelos_dir / "bge-m3"
    if embeddings_disponivel(dir_bge):
        console.print(f"modelo base baixar: bge-m3 já presente em {dir_bge}")
        return

    console.print(f"modelo base baixar: iniciando download de bge-m3 em {dir_bge} (~2GB).")
    wrapper = WrapperEmbeddings(dir_modelo=dir_bge)
    # Força o carregamento (que dispara o download via FlagEmbedding/huggingface).
    wrapper._garantir_modelo()  # noqa: SLF001 -- ponto único que força download
    console.print(f"modelo base baixar: bge-m3 disponível em {dir_bge}")


@modelo_base_app.command("treinar")
def modelo_base_treinar(
    n_amostra: int = typer.Option(
        30000,
        "--n-amostra",
        help="Tamanho da amostra estratificada de discursos (default: 30000).",
    ),
    n_componentes: int = typer.Option(
        50,
        "--n-componentes",
        help="Numero de componentes principais do PCA (default: 50).",
    ),
    db_path: Path | None = typer.Option(  # noqa: B008 -- typer pattern com Path
        None,
        "--db-path",
        help="Caminho do DuckDB analitico. Default: ~/hemiciclo/cache/hemiciclo.duckdb.",
    ),
) -> None:
    """Treina o modelo base v1 (C3) e persiste em ``~/hemiciclo/modelos/``.

    Pipeline: amostra estratificada DuckDB -> embed bge-m3 (batches 64) ->
    PCA com random_state fixo -> joblib + meta.json + SHA256.
    """
    import duckdb

    from hemiciclo.modelos.base import treinar_base_v1
    from hemiciclo.modelos.embeddings import WrapperEmbeddings
    from hemiciclo.modelos.persistencia_modelo import salvar_modelo_base

    cfg = Configuracao()
    cfg.garantir_diretorios()
    destino_db = db_path if db_path is not None else _db_path_default(cfg)
    if not destino_db.exists():
        console.print(
            f"[red]DB inexistente: {destino_db}. Rode `hemiciclo db init` primeiro.[/red]"
        )
        raise typer.Exit(code=2)

    conn = duckdb.connect(str(destino_db))
    try:
        wrapper = WrapperEmbeddings()
        inicio = time.monotonic()
        modelo = treinar_base_v1(
            conn=conn,
            embeddings=wrapper,
            n_amostra=n_amostra,
            n_componentes=n_componentes,
        )
        duracao = time.monotonic() - inicio
    finally:
        conn.close()

    meta = salvar_modelo_base(modelo, cfg.modelos_dir)
    console.print(
        f"modelo base treinar: n_amostra={n_amostra} n_componentes={n_componentes} "
        f"duracao={duracao:.1f}s hash={str(meta['hash_sha256'])[:12]}"
    )


@modelo_base_app.command("carregar")
def modelo_base_carregar() -> None:
    """Carrega o modelo base validando integridade SHA256 e mostra stats."""
    from hemiciclo.modelos.persistencia_modelo import (
        IntegridadeViolada,
        carregar_modelo_base,
    )

    cfg = Configuracao()
    cfg.garantir_diretorios()
    try:
        modelo = carregar_modelo_base(cfg.modelos_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except IntegridadeViolada as exc:
        console.print(f"[red]integridade violada: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"modelo base carregar: versao={modelo.versao} "
        f"n_componentes={modelo.n_componentes} "
        f"treinado_em={modelo.treinado_em.isoformat()} "
        f"hash_amostra={modelo.hash_amostra[:12]}"
    )


@modelo_base_app.command("info")
def modelo_base_info() -> None:
    """Mostra estado do modelo base e do bge-m3 sem carregar artefatos pesados."""
    from hemiciclo.modelos.embeddings import embeddings_disponivel
    from hemiciclo.modelos.persistencia_modelo import info_modelo_base

    cfg = Configuracao()
    cfg.garantir_diretorios()

    meta = info_modelo_base(cfg.modelos_dir)
    if meta is None:
        console.print("modelo base v1: ainda não treinado")
    else:
        console.print(
            f"modelo base v1: versao={meta.get('versao')} "
            f"n_componentes={meta.get('n_componentes')} "
            f"treinado_em={meta.get('treinado_em')} "
            f"hash={str(meta.get('hash_sha256', ''))[:12]}"
        )

    dir_bge = cfg.modelos_dir / "bge-m3"
    if embeddings_disponivel(dir_bge):
        console.print(f"modelo bge-m3: presente em {dir_bge}")
    else:
        console.print("modelo bge-m3: não baixado (use 'hemiciclo modelo base baixar')")


# ---------------------------------------------------------------------------
# Subcomando `hemiciclo rede` (S32)
# ---------------------------------------------------------------------------


@rede_app.command("analisar")
def rede_analisar(
    id_sessao: str = typer.Argument(
        ..., help="Identificador da sessão (ver `hemiciclo sessao listar`)."
    ),
    tipo: str = typer.Option(
        "ambos",
        "--tipo",
        "-t",
        help="Qual grafo gerar: coautoria, voto ou ambos (default).",
    ),
) -> None:
    """Constrói grafos de coautoria e/ou voto para uma sessão existente.

    Útil para sessões antigas (anteriores à S32) ou para regenerar
    grafos sem rodar o pipeline inteiro. Persiste em
    ``~/hemiciclo/sessoes/<id>/grafo_*.html`` + ``metricas_rede.json``.

    Exit code 0 mesmo quando SKIPPED graceful (amostra insuficiente).
    Exit code 2 só para sessão inexistente ou ``dados.duckdb`` ausente.
    """
    import json as _json

    import duckdb

    from hemiciclo.modelos.grafo import (
        AmostraInsuficiente,
        GrafoCoautoria,
        GrafoVoto,
    )
    from hemiciclo.sessao import caminho_sessao

    if tipo not in {"coautoria", "voto", "ambos"}:
        console.print(f"[red]Tipo inválido: {tipo}. Válidos: coautoria, voto, ambos.[/red]")
        raise typer.Exit(code=2)

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    if not sessao_dir.is_dir():
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)

    db_path = sessao_dir / "dados.duckdb"
    if not db_path.exists():
        console.print(
            f"[rede] dados.duckdb ausente em {sessao_dir}. "
            "Pipeline da sessão pode não ter rodado a etapa de ETL ainda."
        )
        # Persistimos metricas SKIPPED para o dashboard nao quebrar
        (sessao_dir / "metricas_rede.json").write_text(
            _json.dumps(
                {
                    "coautoria": {"skipped": True, "motivo": "dados.duckdb ausente"},
                    "voto": {"skipped": True, "motivo": "dados.duckdb ausente"},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return

    metricas: dict[str, dict[str, object]] = {
        "coautoria": {"skipped": True, "motivo": "não solicitado"},
        "voto": {"skipped": True, "motivo": "não solicitado"},
    }
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        if tipo in {"coautoria", "ambos"}:
            metricas["coautoria"] = _gerar_grafo(
                conn, sessao_dir, "coautoria", GrafoCoautoria, AmostraInsuficiente
            )
        if tipo in {"voto", "ambos"}:
            metricas["voto"] = _gerar_grafo(
                conn, sessao_dir, "voto", GrafoVoto, AmostraInsuficiente
            )
    finally:
        conn.close()

    (sessao_dir / "metricas_rede.json").write_text(
        _json.dumps(metricas, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    # Sumario amigavel
    for nome in ("coautoria", "voto"):
        bloco = metricas[nome]
        if bloco.get("skipped"):
            console.print(f"[rede] {nome}: SKIPPED -- {bloco.get('motivo', '')}")
        else:
            console.print(
                f"[rede] {nome}: {bloco.get('n_nos', 0)} nós, "
                f"{bloco.get('n_arestas', 0)} arestas, "
                f"{bloco.get('n_comunidades', 0)} comunidades"
            )


def _gerar_grafo(
    conn: object,
    sessao_dir: Path,
    nome: str,
    classe_grafo: object,
    excecao_skip: type[Exception],
) -> dict[str, object]:
    """Helper: constrói um grafo, persiste HTML e retorna métricas resumidas.

    Em caso de :class:`AmostraInsuficiente` ou erro genérico, retorna dict
    SKIPPED (nunca propaga). Mantém o CLI exit 0.
    """
    from hemiciclo.modelos.grafo import MetricasGrafo
    from hemiciclo.modelos.grafo_pyvis import renderizar_pyvis

    try:
        grafo = classe_grafo.construir(conn)  # type: ignore[attr-defined]
        MetricasGrafo.aplicar_atributos(grafo)
        destino = sessao_dir / f"grafo_{nome}.html"
        renderizar_pyvis(
            MetricasGrafo.filtrar_top(grafo),
            destino,
            titulo=f"Rede de {nome}",
        )
        return {
            "skipped": False,
            "n_nos": len(grafo.nodes()),
            "n_arestas": len(grafo.edges()),
            "maior_componente": MetricasGrafo.tamanho_maior_componente(grafo),
            "n_comunidades": len(set(MetricasGrafo.detectar_comunidades(grafo).values())),
            "top_centrais": MetricasGrafo.top_centrais(grafo, top_n=10),
        }
    except excecao_skip as exc:
        return {"skipped": True, "motivo": str(exc)}
    except Exception as exc:  # noqa: BLE001 -- skip graceful
        return {"skipped": True, "motivo": f"erro: {exc}"}


# ---------------------------------------------------------------------------
# Subcomando `hemiciclo historico` (S33)
# ---------------------------------------------------------------------------


@historico_app.command("calcular")
def historico_calcular(
    id_sessao: str = typer.Argument(
        ..., help="Identificador da sessão (ver `hemiciclo sessao listar`)."
    ),
    granularidade: str = typer.Option(
        "ano",
        "--granularidade",
        "-g",
        help="Bucket temporal: ano (default) ou legislatura.",
    ),
    threshold_pp: float = typer.Option(
        30.0,
        "--threshold-pp",
        help="Mudança mínima em pontos percentuais (default 30).",
    ),
    top_n: int = typer.Option(
        100,
        "--top-n",
        help="Quantos parlamentares mais ativos processar (default 100).",
    ),
) -> None:
    """Calcula histórico de conversão para uma sessão existente.

    Útil para sessões antigas (anteriores à S33) ou para recalcular com
    granularidade/threshold diferentes sem rodar o pipeline inteiro.
    Persiste em ``~/hemiciclo/sessoes/<id>/historico_conversao.json``.

    Exit code 0 mesmo quando SKIPPED graceful (sem dados.duckdb / sem
    votos / amostra insuficiente). Exit code 2 para sessão inexistente
    ou granularidade inválida.
    """
    import json as _json

    import duckdb

    from hemiciclo.modelos.historico import (
        GRANULARIDADES_VALIDAS,
        calcular_historico_top,
    )
    from hemiciclo.sessao import caminho_sessao

    if granularidade not in GRANULARIDADES_VALIDAS:
        console.print(
            f"[red]Granularidade inválida: {granularidade}. "
            f"Válidas: {sorted(GRANULARIDADES_VALIDAS)}.[/red]"
        )
        raise typer.Exit(code=2)

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    if not sessao_dir.is_dir():
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)

    db_path = sessao_dir / "dados.duckdb"
    destino = sessao_dir / "historico_conversao.json"
    if not db_path.exists():
        console.print(f"[historico] dados.duckdb ausente em {sessao_dir}. SKIPPED.")
        destino.write_text(
            _json.dumps(
                {
                    "parlamentares": {},
                    "metadata": {
                        "skipped": True,
                        "motivo": "dados.duckdb ausente",
                        "granularidade": granularidade,
                        "threshold_pp": float(threshold_pp),
                        "n_parlamentares": 0,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return

    inicio = time.monotonic()
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        resultado = calcular_historico_top(
            conn,
            top_n=top_n,
            granularidade=granularidade,
            threshold_pp=threshold_pp,
        )
    finally:
        conn.close()
    duracao = time.monotonic() - inicio

    destino.write_text(
        _json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    meta_obj = resultado.get("metadata", {})
    meta = meta_obj if isinstance(meta_obj, dict) else {}
    if meta.get("skipped"):
        console.print(
            f"[historico] SKIPPED -- {meta.get('motivo', 'sem motivo')} (em {duracao:.2f}s)"
        )
    else:
        console.print(
            f"[historico] {meta.get('n_parlamentares', 0)} parlamentares "
            f"processados ({meta.get('n_com_mudancas', 0)} com mudanças "
            f"detectadas) em {duracao:.2f}s -> {destino}"
        )


# ---------------------------------------------------------------------------
# Subcomando `hemiciclo convertibilidade` (S34)
# ---------------------------------------------------------------------------


@convertibilidade_app.command("treinar")
def convertibilidade_treinar(
    id_sessao: str = typer.Argument(
        ..., help="Identificador da sessão (ver `hemiciclo sessao listar`)."
    ),
    top_n: int = typer.Option(
        100,
        "--top-n",
        help="Tamanho do ranking persistido em convertibilidade_scores.json.",
    ),
) -> None:
    """Treina modelo de convertibilidade para uma sessão existente.

    Útil para sessões antigas (anteriores à S34) ou para retreinar com
    ``top_n`` diferente sem rodar o pipeline inteiro. Persiste em
    ``~/hemiciclo/sessoes/<id>/modelo_convertibilidade/`` (joblib + meta)
    e ``~/hemiciclo/sessoes/<id>/convertibilidade_scores.json``.

    Exit code 0 mesmo quando SKIPPED graceful (amostra insuficiente,
    sem features). Exit code 2 só para sessão inexistente.
    """
    from hemiciclo.modelos.convertibilidade import (
        treinar_convertibilidade_sessao,
    )
    from hemiciclo.sessao import caminho_sessao

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    if not sessao_dir.is_dir():
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)

    inicio = time.monotonic()
    resultado = treinar_convertibilidade_sessao(sessao_dir, top_n=top_n)
    duracao = time.monotonic() - inicio

    if resultado.get("skipped"):
        console.print(
            f"[convertibilidade] SKIPPED -- {resultado.get('motivo', 'sem motivo')} "
            f"(em {duracao:.2f}s)"
        )
        return

    metricas_obj = resultado.get("metricas", {})
    metricas = metricas_obj if isinstance(metricas_obj, dict) else {}
    n_amostra_raw = resultado.get("n_amostra", 0)
    n_amostra = int(n_amostra_raw) if isinstance(n_amostra_raw, int | float) else 0
    console.print(
        f"[convertibilidade] amostra={n_amostra} "
        f"accuracy={float(metricas.get('accuracy', 0.0) or 0.0):.2f} "
        f"f1={float(metricas.get('f1', 0.0) or 0.0):.2f} "
        f"roc_auc={float(metricas.get('roc_auc', 0.0) or 0.0):.2f} "
        f"em {duracao:.2f}s"
    )
    console.print(
        f"[convertibilidade] modelo persistido em {sessao_dir / 'modelo_convertibilidade'} "
        f"+ scores em {sessao_dir / 'convertibilidade_scores.json'}"
    )


@convertibilidade_app.command("prever")
def convertibilidade_prever(
    id_sessao: str = typer.Argument(..., help="Identificador da sessão com modelo já treinado."),
) -> None:
    """Recarrega modelo treinado e regenera scores JSON para a sessão.

    Útil para regenerar ``convertibilidade_scores.json`` após edição
    manual de artefatos sem refazer o treino. Valida integridade SHA256
    do joblib persistido (precedente S28).

    Exit code 0 em sucesso. Exit code 2 para sessão inexistente.
    Exit code 1 para integridade violada.
    """
    import json as _json

    from hemiciclo.modelos.convertibilidade import (
        FEATURE_NAMES_PADRAO,
        ExtratorFeatures,
        IntegridadeViolada,
        ModeloConvertibilidade,
    )
    from hemiciclo.sessao import caminho_sessao

    cfg = Configuracao()
    cfg.garantir_diretorios()
    sessao_dir = caminho_sessao(cfg.home, id_sessao)
    if not sessao_dir.is_dir():
        console.print(f"[red]sessão não encontrada: {id_sessao}[/red]")
        raise typer.Exit(code=2)

    dir_modelo = sessao_dir / "modelo_convertibilidade"
    try:
        modelo = ModeloConvertibilidade.carregar(dir_modelo)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except IntegridadeViolada as exc:
        console.print(f"[red]integridade violada: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    df = ExtratorFeatures.extrair(sessao_dir)
    if len(df) == 0:
        console.print("[convertibilidade] features vazias; nada a prever")
        return

    df_x = df.select(list(FEATURE_NAMES_PADRAO))
    proba = modelo.prever_proba(df_x)
    df_scores = (
        df.with_columns(proba.alias("proba"))
        .select(["parlamentar_id", "nome", "casa", "proba", "indice_volatilidade"])
        .sort("proba", descending=True)
    )

    destino = sessao_dir / "convertibilidade_scores.json"
    payload = {
        "skipped": False,
        "motivo": None,
        "n_amostra": int(len(df)),
        "metricas": dict(modelo.metricas),
        "coeficientes": modelo.coeficientes(),
        "feature_names": list(modelo.feature_names),
        "scores": df_scores.to_dicts(),
    }
    destino.write_text(
        _json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    console.print(f"[convertibilidade] {len(df)} parlamentares ranqueados -> {destino}")
