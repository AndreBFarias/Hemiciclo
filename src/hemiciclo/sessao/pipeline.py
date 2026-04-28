"""Pipeline integrado real da Sessão de Pesquisa (S30).

Substitui o ``_pipeline_dummy`` da S29 conectando todos os subsistemas
anteriores em sequência dentro da pasta da sessão:

1. **Validação** -- resolve YAML do tópico antes de qualquer rede.
2. **Coleta (5--30%)** -- Câmara (S24) e/ou Senado (S25) gravando
   parquets em ``sessao_dir/raw/``.
3. **ETL (30--50%)** -- consolida em ``sessao_dir/dados.duckdb`` via
   :func:`hemiciclo.etl.consolidador.consolidar_parquets_em_duckdb` (S26).
4. **Camadas 1+2 (50--65%)** -- regex + voto + TF-IDF via
   :func:`hemiciclo.modelos.classificador.classificar` (S27).
5. **Camada 3 (65--90%)** -- projeção do recorte no modelo base v1
   (S28). SKIPPED *graceful* se ``bge-m3`` ausente ou se o modelo base
   não foi treinado -- a sessão segue até CONCLUIDA.
6. **Persistência (90--100%)** -- ``relatorio_state.json`` agregado +
   ``manifesto.json`` com SHA256 truncado em 16 chars de cada artefato
   da sessão e lista ``limitacoes_conhecidas`` (precedente S25.1).

Cada etapa é guardada por ``try/except`` no nível do orquestrador:
qualquer falha não mascarada vira ``EstadoSessao.ERRO`` com mensagem
``"<tipo>: <mensagem>"`` em ``status.json`` e re-raise para o worker.

Limitações conhecidas registradas em ``manifesto.json``:

- ``S24b`` -- 4 colunas vazias em proposições (S24).
- ``S24c`` -- coletor da Câmara só pega ano inicial da legislatura.
- ``S25.3`` -- schema dual da API Senado tratado defensivamente.
- ``S27.1`` -- ``votacoes.proposicao_id`` ainda ausente -- C1 voto
  retorna agregação vazia mas não falha.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from hemiciclo.coleta import ParametrosColeta, TipoColeta
from hemiciclo.config import Configuracao
from hemiciclo.sessao.modelo import (
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
)
from hemiciclo.sessao.runner import StatusUpdater

LIMITACOES_CONHECIDAS: tuple[str, ...] = ("S24b", "S24c", "S25.3", "S27.1")
"""Sprints novas READY que documentam limites herdados do pipeline.

Registradas em ``manifesto.json`` para tornar explícito ao usuário e
ao auditor o que esta versão *ainda* não cobre.
"""

VERSAO_PIPELINE = "1"


# ---------------------------------------------------------------------------
# Orquestrador principal
# ---------------------------------------------------------------------------


def pipeline_real(params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater) -> None:
    """Pipeline integrado real -- coleta -> ETL -> C1+C2+C3 -> relatório.

    Mesma assinatura de ``_pipeline_dummy`` (S29) para que o
    :class:`hemiciclo.sessao.runner.SessaoRunner` chame indistintamente.

    Args:
        params: Parâmetros validados da sessão. Quando ``params.max_itens``
            é fornecido (default ``None``), a etapa de coleta limita N
            itens por tipo por casa. Etapas posteriores (ETL, C1+C2, C3,
            grafos, histórico, convertibilidade) operam sobre toda a
            amostra coletada -- sem propagação adicional.
        sessao_dir: Pasta da sessão (já criada pelo runner).
        updater: Publicador de progresso em ``status.json``.
    """
    log = logger.bind(sessao_dir=str(sessao_dir), topico=params.topico)
    try:
        _etapa_validar(params, sessao_dir, updater, log)
        _etapa_coleta(params, sessao_dir, updater, log)
        _etapa_etl(sessao_dir, updater, log)
        _etapa_classificacao_c1_c2(params, sessao_dir, updater, log)
        if Camada.EMBEDDINGS in params.camadas:
            _etapa_embeddings_c3(params, sessao_dir, updater, log)
        else:
            log.info("[pipeline] camada EMBEDDINGS desligada nos params -- C3 pulada")
        if params.incluir_grafo:
            _etapa_grafos(sessao_dir, updater, log)
        else:
            log.info("[pipeline] incluir_grafo=False -- grafos pulados")
        _etapa_historico(sessao_dir, updater, log)
        if params.incluir_convertibilidade:
            _etapa_convertibilidade(sessao_dir, updater, log)
        else:
            log.info("[pipeline] incluir_convertibilidade=False -- S34 pulada")
        _etapa_relatorio(params, sessao_dir, updater, log)
        updater.atualizar(
            EstadoSessao.CONCLUIDA,
            100.0,
            "concluida",
            "Pipeline real concluído",
        )
    except Exception as exc:  # noqa: BLE001 -- queremos capturar tudo aqui
        log.exception("[pipeline] erro fatal")
        updater.atualizar(
            EstadoSessao.ERRO,
            0.0,
            "erro",
            f"{type(exc).__name__}: {exc}",
            erro=f"{type(exc).__name__}: {exc}",
        )
        raise


# ---------------------------------------------------------------------------
# Etapa 0 -- validação
# ---------------------------------------------------------------------------


def _etapa_validar(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Resolve YAML do tópico e cria pasta ``raw/`` antes de qualquer rede."""
    updater.atualizar(EstadoSessao.COLETANDO, 2.0, "validar", "Validando parâmetros")
    topico_path = _resolver_topico(params.topico)
    log.info("[pipeline] tópico resolvido em {p}", p=topico_path)
    (sessao_dir / "raw").mkdir(exist_ok=True)


def _resolver_topico(topico: str) -> Path:
    """Resolve string do tópico em ``Path`` do YAML curado.

    Aceita:

    - Path absoluto/relativo apontando para arquivo ``.yaml`` / ``.yml``.
    - Slug (ex: ``"aborto"``) -- procura em ``<repo>/topicos/<slug>.yaml``
      via ``Path.cwd()``.

    Raises:
        FileNotFoundError: Tópico não localizado em nenhuma estratégia.
    """
    p = Path(topico)
    if p.suffix in {".yaml", ".yml"} and p.exists():
        return p
    repo_topico = Path.cwd() / "topicos" / f"{topico}.yaml"
    if repo_topico.exists():
        return repo_topico
    raise FileNotFoundError(f"Tópico YAML não encontrado: {topico}")


# ---------------------------------------------------------------------------
# Etapa 1 -- coleta
# ---------------------------------------------------------------------------


def _etapa_coleta(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 1 (5--30%): coleta Câmara e/ou Senado em ``sessao_dir/raw/``."""
    raw = sessao_dir / "raw"
    raw.mkdir(exist_ok=True)
    cfg = Configuracao()
    cfg.garantir_diretorios()

    if Casa.CAMARA in params.casas:
        updater.atualizar(EstadoSessao.COLETANDO, 10.0, "coleta_camara", "Coletando Câmara")
        from hemiciclo.coleta.camara import (  # noqa: PLC0415 -- lazy
            executar_coleta as exec_camara,
        )

        params_camara = ParametrosColeta(
            legislaturas=list(params.legislaturas),
            tipos=_tipos_camara(),
            data_inicio=params.data_inicio,
            data_fim=params.data_fim,
            max_itens=params.max_itens,
            dir_saida=raw,
        )
        log.info("[pipeline][coleta_camara] iniciando coleta da Câmara")
        exec_camara(params_camara, cfg.home)

    if Casa.SENADO in params.casas:
        updater.atualizar(EstadoSessao.COLETANDO, 22.0, "coleta_senado", "Coletando Senado")
        from hemiciclo.coleta.senado import (  # noqa: PLC0415 -- lazy
            executar_coleta as exec_senado,
        )

        params_senado = ParametrosColeta(
            legislaturas=list(params.legislaturas),
            tipos=_tipos_senado(),
            data_inicio=params.data_inicio,
            data_fim=params.data_fim,
            max_itens=params.max_itens,
            dir_saida=raw,
        )
        log.info("[pipeline][coleta_senado] iniciando coleta do Senado")
        exec_senado(params_senado, cfg.home)


def _tipos_camara() -> list[TipoColeta]:
    """Tipos canônicos coletados da Câmara para o pipeline integrado."""
    return ["proposicoes", "deputados", "votacoes", "votos", "discursos"]


def _tipos_senado() -> list[TipoColeta]:
    """Tipos canônicos coletados do Senado para o pipeline integrado."""
    return ["materias", "senadores", "votacoes", "votos", "discursos"]


# ---------------------------------------------------------------------------
# Etapa 2 -- ETL
# ---------------------------------------------------------------------------


def _etapa_etl(sessao_dir: Path, updater: StatusUpdater, log: Any) -> None:
    """Etapa 2 (30--50%): consolida parquets em ``sessao_dir/dados.duckdb``."""
    updater.atualizar(EstadoSessao.ETL, 35.0, "etl", "Consolidando em DuckDB")
    from hemiciclo.etl.consolidador import (  # noqa: PLC0415 -- lazy
        consolidar_parquets_em_duckdb,
    )

    db_path = sessao_dir / "dados.duckdb"
    contagens = consolidar_parquets_em_duckdb(sessao_dir / "raw", db_path)
    log.info("[pipeline][etl] contagens={c}", c=contagens)


# ---------------------------------------------------------------------------
# Etapa 3 -- camadas 1 e 2
# ---------------------------------------------------------------------------


def _montar_clausula_subset_parlamentares(
    conn: Any,
    ufs: list[str] | None,
    partidos: list[str] | None,
) -> set[tuple[int, str]] | None:
    """Resolve ``(ufs, partidos)`` em conjunto de pares ``(parlamentar_id, casa)``.

    Helper interno do pipeline (S30.2). Aplica o filtro ``WHERE uf IN
    (...) AND UPPER(partido) IN (...)`` na tabela ``parlamentares`` (schema
    v1+, ver ``etl/schema.py``) com placeholders parametrizados (defesa
    em profundidade contra injeção, mesmo com o validador Pydantic
    ``ParametrosBusca._ufs_canonicas`` já restringindo UFs ao conjunto
    canônico ``UFS_BRASIL``).

    Args:
        conn: Conexão DuckDB ativa (``read_only`` recomendado).
        ufs: Lista de siglas de UF (ex.: ``["SP", "RJ"]``) ou ``None``.
        partidos: Lista de siglas de partido (ex.: ``["PT"]``) ou ``None``.

    Returns:
        ``None`` quando ``ufs`` e ``partidos`` são ambos ``None`` --
        sentinela "sem filtro": classificador segue com todos os
        parlamentares da DB.

        ``set[tuple[int, str]]`` caso contrário -- conjunto possivelmente
        vazio. Set vazio sinaliza "filtro casou ninguém"; o classificador
        deve curto-circuitar para ``schema_vazio``.

    Notas:
        - O filtro usa o partido **registrado no momento da coleta** da
          tabela ``parlamentares``. Auditoria histórica de migrações
          partidárias é sprint futura.
        - ``UPPER(partido)`` defensivo: a API da Câmara devolve ``"PT"``,
          mas o Senado historicamente mistura caixa.

    Loga em ``INFO`` o tamanho do recorte; em ``WARNING`` quando
    ``0 < n < 10`` (recorte estreito) ou ``n == 0`` (recorte vazio).
    """
    if ufs is None and partidos is None:
        return None

    where: list[str] = []
    sql_params: list[str] = []
    if ufs:
        where.append("uf IN (" + ", ".join(["?"] * len(ufs)) + ")")
        sql_params.extend(ufs)
    if partidos:
        where.append("UPPER(partido) IN (" + ", ".join(["UPPER(?)"] * len(partidos)) + ")")
        sql_params.extend(partidos)

    sql = "SELECT id, casa FROM parlamentares"
    if where:
        sql += " WHERE " + " AND ".join(where)

    rows = conn.execute(sql, sql_params).fetchall()
    subset: set[tuple[int, str]] = {(int(r[0]), str(r[1])) for r in rows}
    n = len(subset)
    logger.info(
        "[pipeline][filtro] ufs={u} partidos={p} -> {n} parlamentares",
        u=ufs,
        p=partidos,
        n=n,
    )
    if n == 0:
        logger.warning(
            "[pipeline][filtro] recorte vazio -- nenhum parlamentar casou ufs={u} AND partidos={p}",
            u=ufs,
            p=partidos,
        )
    elif n < 10:
        logger.warning(
            "[pipeline][filtro] recorte muito estreito: apenas {n} "
            "parlamentares -- estatísticas podem ser ruidosas",
            n=n,
        )
    return subset


def _etapa_classificacao_c1_c2(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 3 (50--65%): aplica camadas regex + voto + TF-IDF.

    Quando ``params.ufs`` ou ``params.partidos`` são informados (S30.2),
    resolve o ``parlamentares_subset`` via
    :func:`_montar_clausula_subset_parlamentares` antes de chamar
    ``classificar``. O filtro acontece **após** o ETL: cache transversal
    SHA256 (S26) deduplica a coleta global, então sessões diferentes
    compartilham parquets brutos e o recorte por UF/partido restringe
    apenas o JOIN da agregação de voto.
    """
    updater.atualizar(EstadoSessao.ETL, 55.0, "classificar_c1_c2", "Classificando C1+C2")
    import duckdb  # noqa: PLC0415 -- lazy

    from hemiciclo.modelos.classificador import (  # noqa: PLC0415 -- lazy
        classificar,
    )

    db_path = sessao_dir / "dados.duckdb"
    topico_path = _resolver_topico(params.topico)
    cfg = Configuracao()

    subset: set[tuple[int, str]] | None = None
    if params.ufs is not None or params.partidos is not None:
        conn_filtro = duckdb.connect(str(db_path), read_only=True)
        try:
            subset = _montar_clausula_subset_parlamentares(conn_filtro, params.ufs, params.partidos)
        finally:
            conn_filtro.close()

    resultado = classificar(
        topico_yaml=topico_path,
        db_path=db_path,
        camadas=["regex", "votos", "tfidf"],
        top_n=100,
        home=cfg.home,
        parlamentares_subset=subset,
    )
    destino = sessao_dir / "classificacao_c1_c2.json"
    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    log.info(
        "[pipeline][c1c2] n_props={p} n_parlamentares={n} subset={s}",
        p=resultado.get("n_props", 0),
        n=resultado.get("n_parlamentares", 0),
        s=resultado.get("n_parlamentares_subset"),
    )


# ---------------------------------------------------------------------------
# Etapa 4 -- camada 3 (embeddings + projeção)
# ---------------------------------------------------------------------------


def _etapa_embeddings_c3(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 4 (65--90%): projeta recorte no modelo base v1.

    SKIP graceful em três casos: bge-m3 ausente, modelo base não
    treinado, ou modelo base com integridade violada. Em todos eles a
    sessão continua até CONCLUIDA -- a UI tem como saber via campo
    ``c3_skipped`` no relatório.
    """
    updater.atualizar(EstadoSessao.EMBEDDINGS, 70.0, "embeddings_c3", "Projetando em base v1")
    from hemiciclo.modelos.embeddings import (  # noqa: PLC0415 -- lazy
        embeddings_disponivel,
    )
    from hemiciclo.modelos.persistencia_modelo import (  # noqa: PLC0415 -- lazy
        IntegridadeViolada,
        carregar_modelo_base,
    )

    cfg = Configuracao()
    motivo_skip: str | None = None
    if not embeddings_disponivel():
        motivo_skip = "bge-m3 não disponível"
    else:
        try:
            carregar_modelo_base(cfg.modelos_dir)
        except FileNotFoundError:
            motivo_skip = "modelo base não treinado"
        except IntegridadeViolada as exc:
            motivo_skip = f"modelo base corrompido: {exc}"

    estado_path = sessao_dir / "c3_status.json"
    if motivo_skip is not None:
        log.warning("[pipeline][c3] SKIPPED -- motivo: {m}", m=motivo_skip)
        estado_path.write_text(
            json.dumps(
                {"skipped": True, "motivo": motivo_skip},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        updater.atualizar(
            EstadoSessao.EMBEDDINGS,
            85.0,
            "embeddings_c3_skipped",
            f"C3 SKIPPED: {motivo_skip}",
        )
        return

    # Caminho real só roda se o modelo está disponível. Em CI sempre cai
    # no SKIP graceful acima -- testes unitários cobrem ambos os ramos.
    log.info("[pipeline][c3] modelo base carregado; projeção pendente em S31")
    estado_path.write_text(
        json.dumps(
            {"skipped": False, "motivo": None, "params_topico": params.topico},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    updater.atualizar(
        EstadoSessao.EMBEDDINGS,
        88.0,
        "embeddings_c3",
        "C3 modelo base carregado",
    )


# ---------------------------------------------------------------------------
# Etapa 4.5 -- grafos de rede (S32)
# ---------------------------------------------------------------------------


def _etapa_grafos(
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 4.5 (88--93%): gera grafo de coautoria + grafo de voto + métricas.

    Skip graceful em três níveis:

    - ``dados.duckdb`` ausente -> SKIPPED (etapa nem roda)
    - Tabela ``votos`` ausente / amostra < 5 nós -> SKIPPED por tipo
    - Erro inesperado dentro de um tipo -> WARNING + segue para o outro

    Persiste em ``sessao_dir/``:
    - ``grafo_coautoria.html`` (pyvis) ou nada se SKIPPED
    - ``grafo_voto.html`` (pyvis) ou nada se SKIPPED
    - ``metricas_rede.json`` com top 10 mais centrais + tamanho da
      maior componente + número de comunidades, sempre.
    """
    import duckdb  # noqa: PLC0415 -- lazy

    from hemiciclo.modelos.grafo import (  # noqa: PLC0415 -- lazy
        AmostraInsuficiente,
        GrafoCoautoria,
        GrafoVoto,
        MetricasGrafo,
    )
    from hemiciclo.modelos.grafo_pyvis import (  # noqa: PLC0415 -- lazy
        renderizar_pyvis,
    )

    updater.atualizar(EstadoSessao.MODELANDO, 88.0, "grafos", "Construindo redes")
    db_path = sessao_dir / "dados.duckdb"
    metricas: dict[str, Any] = {
        "coautoria": {"skipped": True, "motivo": "não rodou"},
        "voto": {"skipped": True, "motivo": "não rodou"},
    }

    if not db_path.exists():
        log.warning("[pipeline][grafos] dados.duckdb ausente; SKIPPED")
        metricas["coautoria"]["motivo"] = "dados.duckdb ausente"
        metricas["voto"]["motivo"] = "dados.duckdb ausente"
        _persistir_metricas_rede(sessao_dir, metricas)
        return

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        # Coautoria
        try:
            grafo_co = GrafoCoautoria.construir(conn)
            MetricasGrafo.aplicar_atributos(grafo_co)
            destino_co = sessao_dir / "grafo_coautoria.html"
            renderizar_pyvis(
                MetricasGrafo.filtrar_top(grafo_co),
                destino_co,
                titulo="Rede de coautoria (proxy: votar nas mesmas votações)",
            )
            metricas["coautoria"] = _resumir(grafo_co)
            log.info(
                "[pipeline][grafos] coautoria gerado: nos={n} arestas={a}",
                n=len(grafo_co.nodes()),
                a=len(grafo_co.edges()),
            )
        except AmostraInsuficiente as exc:
            log.warning("[pipeline][grafos] coautoria SKIPPED: {e}", e=exc)
            metricas["coautoria"] = {"skipped": True, "motivo": str(exc)}
        except Exception as exc:  # noqa: BLE001 -- skip graceful
            log.warning("[pipeline][grafos] coautoria erro: {e}", e=exc)
            metricas["coautoria"] = {"skipped": True, "motivo": f"erro: {exc}"}

        # Voto
        try:
            grafo_v = GrafoVoto.construir(conn)
            MetricasGrafo.aplicar_atributos(grafo_v)
            destino_v = sessao_dir / "grafo_voto.html"
            renderizar_pyvis(
                MetricasGrafo.filtrar_top(grafo_v),
                destino_v,
                titulo="Rede de afinidade por voto",
            )
            metricas["voto"] = _resumir(grafo_v)
            log.info(
                "[pipeline][grafos] voto gerado: nos={n} arestas={a}",
                n=len(grafo_v.nodes()),
                a=len(grafo_v.edges()),
            )
        except AmostraInsuficiente as exc:
            log.warning("[pipeline][grafos] voto SKIPPED: {e}", e=exc)
            metricas["voto"] = {"skipped": True, "motivo": str(exc)}
        except Exception as exc:  # noqa: BLE001 -- skip graceful
            log.warning("[pipeline][grafos] voto erro: {e}", e=exc)
            metricas["voto"] = {"skipped": True, "motivo": f"erro: {exc}"}
    finally:
        conn.close()

    _persistir_metricas_rede(sessao_dir, metricas)
    updater.atualizar(EstadoSessao.MODELANDO, 93.0, "grafos_concluidos", "Redes prontas")


def _resumir(grafo: Any) -> dict[str, Any]:
    """Resume métricas de um grafo construído em dict serializável."""
    from hemiciclo.modelos.grafo import MetricasGrafo  # noqa: PLC0415 -- lazy

    return {
        "skipped": False,
        "n_nos": len(grafo.nodes()),
        "n_arestas": len(grafo.edges()),
        "maior_componente": MetricasGrafo.tamanho_maior_componente(grafo),
        "n_comunidades": len(set(MetricasGrafo.detectar_comunidades(grafo).values())),
        "top_centrais": MetricasGrafo.top_centrais(grafo, top_n=10),
    }


def _persistir_metricas_rede(sessao_dir: Path, metricas: dict[str, Any]) -> None:
    """Grava ``metricas_rede.json`` com indentação e UTF-8."""
    (sessao_dir / "metricas_rede.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Etapa 4.7 -- histórico de conversão por parlamentar (S33)
# ---------------------------------------------------------------------------


def _etapa_historico(
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 4.7 (93--95%): histórico temporal por parlamentar.

    Para os 100 parlamentares mais ativos da sessão, calcula histórico
    de proporção SIM por bucket (ano), detecta mudanças (>= 30pp) e
    grava em ``<sessao_dir>/historico_conversao.json``. Skip graceful
    rigoroso em três níveis:

    - ``dados.duckdb`` ausente -> SKIPPED (etapa nem roda).
    - Tabela ``votos`` ausente / sem votos -> SKIPPED com motivo.
    - Erro inesperado -> WARNING + JSON com ``skipped=True``.

    Por design alimenta:

    - Eixo ``volatilidade`` da assinatura multidimensional (D4).
    - Sprint S34 (ML de convertibilidade) que consome
      ``indice_volatilidade`` como feature.
    """
    import duckdb  # noqa: PLC0415 -- lazy

    from hemiciclo.modelos.historico import (  # noqa: PLC0415 -- lazy
        calcular_historico_top,
    )

    updater.atualizar(
        EstadoSessao.MODELANDO,
        93.0,
        "historico",
        "Calculando histórico de conversão",
    )
    db_path = sessao_dir / "dados.duckdb"
    destino = sessao_dir / "historico_conversao.json"
    if not db_path.exists():
        log.warning("[pipeline][historico] dados.duckdb ausente; SKIPPED")
        destino.write_text(
            json.dumps(
                {
                    "parlamentares": {},
                    "metadata": {
                        "skipped": True,
                        "motivo": "dados.duckdb ausente",
                        "granularidade": "ano",
                        "threshold_pp": 30.0,
                        "n_parlamentares": 0,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        try:
            resultado = calcular_historico_top(
                conn,
                top_n=100,
                granularidade="ano",
                threshold_pp=30.0,
            )
        except Exception as exc:  # noqa: BLE001 -- skip graceful
            log.warning("[pipeline][historico] erro inesperado: {e}", e=exc)
            resultado = {
                "parlamentares": {},
                "metadata": {
                    "skipped": True,
                    "motivo": f"erro: {exc}",
                    "granularidade": "ano",
                    "threshold_pp": 30.0,
                    "n_parlamentares": 0,
                },
            }
    finally:
        conn.close()

    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    meta_obj = resultado.get("metadata", {})
    meta = meta_obj if isinstance(meta_obj, dict) else {}
    log.info(
        "[pipeline][historico] n_parlamentares={n} n_com_mudancas={m} skipped={s}",
        n=meta.get("n_parlamentares", 0),
        m=meta.get("n_com_mudancas", 0),
        s=meta.get("skipped", False),
    )
    updater.atualizar(
        EstadoSessao.MODELANDO,
        95.0,
        "historico_concluido",
        "Histórico calculado",
    )


# ---------------------------------------------------------------------------
# Etapa 4.8 -- ML de convertibilidade (S34)
# ---------------------------------------------------------------------------


def _etapa_convertibilidade(
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 4.8 (95--98%): ML de convertibilidade via LogisticRegression.

    Consome features das etapas anteriores:

    - ``historico_conversao.json`` (S33) -- ``indice_volatilidade``.
    - ``metricas_rede.json`` (S32) -- centralidades.
    - ``classificacao_c1_c2.json`` (S27) -- ``proporcao_sim_topico``.

    Skip graceful rigoroso (exit 0 sempre):

    - Artefatos pré-requisito ausentes -> features vazias -> SKIPPED.
    - Amostra < 30 -> SKIPPED com mensagem clara.
    - Apenas 1 classe em y -> SKIPPED.

    Persiste:

    - ``<sessao_dir>/convertibilidade_scores.json`` (top 100 ranqueado).
    - ``<sessao_dir>/modelo_convertibilidade/convertibilidade.joblib``
      (+ meta.json com SHA256).
    """
    from hemiciclo.modelos.convertibilidade import (  # noqa: PLC0415 -- lazy
        treinar_convertibilidade_sessao,
    )

    updater.atualizar(
        EstadoSessao.MODELANDO,
        95.0,
        "convertibilidade",
        "Treinando convertibilidade (S34)",
    )
    try:
        resultado = treinar_convertibilidade_sessao(sessao_dir, top_n=100)
    except Exception as exc:  # noqa: BLE001 -- skip graceful
        log.warning("[pipeline][convertibilidade] erro inesperado: {e}", e=exc)
        # Persiste skip explícito para o dashboard mostrar mensagem.
        (sessao_dir / "convertibilidade_scores.json").write_text(
            json.dumps(
                {
                    "skipped": True,
                    "motivo": f"erro: {exc}",
                    "n_amostra": 0,
                    "metricas": {},
                    "coeficientes": {},
                    "feature_names": [],
                    "scores": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        updater.atualizar(
            EstadoSessao.MODELANDO,
            98.0,
            "convertibilidade_erro",
            f"S34 SKIPPED: {exc}",
        )
        return

    if resultado.get("skipped"):
        log.warning(
            "[pipeline][convertibilidade] SKIPPED -- {m}",
            m=resultado.get("motivo", "sem motivo"),
        )
        # Persiste skip explícito para o dashboard mostrar mensagem.
        # treinar_convertibilidade_sessao só grava JSON em caminhos
        # bem-sucedidos -- aqui forçamos o JSON sentinela.
        (sessao_dir / "convertibilidade_scores.json").write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        updater.atualizar(
            EstadoSessao.MODELANDO,
            98.0,
            "convertibilidade_skipped",
            f"S34 SKIPPED: {resultado.get('motivo', '')}",
        )
        return

    metricas = resultado.get("metricas") or {}
    metricas_dict: dict[str, Any] = metricas if isinstance(metricas, dict) else {}
    log.info(
        "[pipeline][convertibilidade] amostra={n} accuracy={a:.2f} f1={f:.2f}",
        n=resultado.get("n_amostra", 0),
        a=float(metricas_dict.get("accuracy", 0.0) or 0.0),
        f=float(metricas_dict.get("f1", 0.0) or 0.0),
    )
    updater.atualizar(
        EstadoSessao.MODELANDO,
        98.0,
        "convertibilidade_concluida",
        "S34 modelo treinado",
    )


# ---------------------------------------------------------------------------
# Etapa 5 -- relatório + manifesto
# ---------------------------------------------------------------------------


def _etapa_relatorio(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    """Etapa 5 (90--100%): persiste ``relatorio_state.json`` + ``manifesto.json``."""
    updater.atualizar(EstadoSessao.MODELANDO, 95.0, "relatorio", "Persistindo relatório")
    relatorio = _agregar_relatorio(params, sessao_dir)
    (sessao_dir / "relatorio_state.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    manifesto = _gerar_manifesto(sessao_dir)
    (sessao_dir / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    log.info("[pipeline][relatorio] artefatos={n}", n=len(manifesto["artefatos"]))


def _agregar_relatorio(params: ParametrosBusca, sessao_dir: Path) -> dict[str, Any]:
    """Combina classificação C1+C2 e estado de C3 em um relatório único."""
    classif_path = sessao_dir / "classificacao_c1_c2.json"
    classif: dict[str, Any] = {}
    if classif_path.exists():
        classif = json.loads(classif_path.read_text(encoding="utf-8"))

    c3_path = sessao_dir / "c3_status.json"
    c3: dict[str, Any] = {"skipped": True, "motivo": "etapa não executada"}
    if c3_path.exists():
        c3 = json.loads(c3_path.read_text(encoding="utf-8"))

    return {
        "topico": params.topico,
        "casas": [c.value for c in params.casas],
        "legislaturas": list(params.legislaturas),
        "camadas_solicitadas": [c.value for c in params.camadas],
        "ufs": list(params.ufs) if params.ufs else None,
        "partidos": list(params.partidos) if params.partidos else None,
        "n_parlamentares_subset": classif.get("n_parlamentares_subset"),
        "n_props": classif.get("n_props", 0),
        "n_parlamentares": classif.get("n_parlamentares", 0),
        "top_a_favor": classif.get("top_a_favor", []),
        "top_contra": classif.get("top_contra", []),
        "c3": c3,
        "gerado_em": datetime.now(UTC).isoformat(),
    }


def _gerar_manifesto(sessao_dir: Path) -> dict[str, Any]:
    """Hash SHA256 truncado em 16 chars de cada artefato + limitações.

    Precedente: S24/S25 usam SHA256 16-char truncado para
    ``hash_conteudo`` (S25.1 confirma a convenção). Mantemos o mesmo
    formato em ``manifesto.json`` para consistência cross-sprint.
    """
    artefatos: dict[str, str] = {}
    extensoes_alvo = {".parquet", ".duckdb", ".json"}
    for caminho in sorted(sessao_dir.rglob("*")):
        if not caminho.is_file():
            continue
        if caminho.suffix not in extensoes_alvo:
            continue
        if caminho.name == "manifesto.json":
            continue
        try:
            sha = hashlib.sha256(caminho.read_bytes()).hexdigest()[:16]
        except OSError:
            continue
        rel = caminho.relative_to(sessao_dir).as_posix()
        artefatos[rel] = sha
    return {
        "criado_em": datetime.now(UTC).isoformat(),
        "versao_pipeline": VERSAO_PIPELINE,
        "artefatos": artefatos,
        "limitacoes_conhecidas": list(LIMITACOES_CONHECIDAS),
    }
