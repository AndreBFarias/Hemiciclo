"""Histórico de conversão por parlamentar (S33).

Eixo ``volatilidade`` da assinatura multidimensional (D4 / ADR-004).
Para cada parlamentar agrupa votos em buckets temporais (ano ou
legislatura), calcula proporção SIM por bucket, detecta mudanças
significativas entre buckets adjacentes e devolve um índice de
volatilidade normalizado em ``[0, 1]``.

Decisões fundamentais:

- **Granularidade dupla:** ``"ano"`` (mais fino) e ``"legislatura"``
  (mais robusto a anos de baixa atividade). Legislaturas mapeadas
  manualmente: 55 (2015-2018), 56 (2019-2022), 57 (2023+).
- **JOIN votos x votacoes via ``(votacao_id, casa)``** -- precedente
  S32 (:mod:`hemiciclo.modelos.grafo`). Schema atual S26 não tem
  ``votacoes.proposicao_id`` -- limitação documentada em S27.1.
- **Voto SIM case-insensitive** -- valores brutos: ``Sim``, ``Nao``,
  ``Abstencao``, ``Obstrucao``, ``Art.17``. Comparação via ``UPPER()``.
- **HAVING n_votos >= 5** por bucket: filtro contra buckets pobres
  que distorcem a proporção.
- **Posição dominante:** ``A_FAVOR >= 0.70``, ``CONTRA <= 0.30``,
  ``NEUTRO`` no meio (precedente :mod:`hemiciclo.modelos.classificador_c1`).
- **Threshold padrão de mudança:** 30 pontos percentuais em ``proporcao_sim``
  entre buckets adjacentes.
- **Volatilidade:** ``std(proporcao_sim) / 0.5`` saturado em 1.0. Std
  máxima teórica de uma série binária 0/1 é 0.5.

Skip graceful:

- Tabela ``votos`` ausente -> :class:`AmostraInsuficiente`.
- Menos de :data:`MIN_BUCKETS` buckets retornados -> ``empty DataFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
from loguru import logger

if TYPE_CHECKING:
    import duckdb


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

GRANULARIDADES_VALIDAS: frozenset[str] = frozenset({"ano", "legislatura"})
"""Granularidades aceitas em :meth:`HistoricoConversao.calcular`."""

MIN_VOTOS_POR_BUCKET: int = 5
"""Bucket com menos votos é descartado pelo HAVING."""

MIN_BUCKETS: int = 2
"""Histórico precisa de pelo menos 2 buckets pra calcular volatilidade."""

THRESHOLD_PP_PADRAO: float = 30.0
"""Mudança significativa default em pontos percentuais."""

LIMIAR_A_FAVOR: float = 0.70
"""``proporcao_sim >= 0.70`` -> posição A_FAVOR."""

LIMIAR_CONTRA: float = 0.30
"""``proporcao_sim <= 0.30`` -> posição CONTRA."""

STD_MAX_TEORICA: float = 0.5
"""Std máxima teórica de série binária (alternar 0 e 1)."""


# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------


class AmostraInsuficiente(Exception):  # noqa: N818 -- nome PT-BR, precedente :mod:`grafo`
    """Levantada quando histórico não pode ser calculado.

    Casos:

    - Tabela ``votos`` ausente no DB.
    - Parlamentar sem votos no DB.

    O caller (pipeline / dashboard / CLI) deve tratar como SKIPPED
    graceful, jamais como erro fatal.
    """


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _tabela_existe(conn: duckdb.DuckDBPyConnection, nome: str) -> bool:
    """Retorna ``True`` se a tabela existe no schema atual.

    Precedente: idêntica a :func:`hemiciclo.modelos.grafo._tabela_existe`.
    """
    sql = "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1"
    linha = conn.execute(sql, [nome]).fetchone()
    return linha is not None


def _classificar_posicao(proporcao_sim: float) -> str:
    """Classifica posição dominante a partir da proporção de SIM.

    Precedente: ``classificador_c1.posicao_agregada`` usa os mesmos
    limiares (0.70 / 0.30).
    """
    if proporcao_sim >= LIMIAR_A_FAVOR:
        return "a_favor"
    if proporcao_sim <= LIMIAR_CONTRA:
        return "contra"
    return "neutro"


# ---------------------------------------------------------------------------
# HistoricoConversao
# ---------------------------------------------------------------------------


class HistoricoConversao:
    """Calcula histórico temporal de proporção SIM por parlamentar."""

    @staticmethod
    def calcular(
        conn: duckdb.DuckDBPyConnection,
        parlamentar_id: int,
        casa: str,
        granularidade: str = "ano",
    ) -> pl.DataFrame:
        """Constrói histórico do parlamentar agrupado por bucket temporal.

        Args:
            conn: Conexão DuckDB com tabelas ``votos`` e ``votacoes``.
            parlamentar_id: Id do parlamentar (mesmo id do schema S26).
            casa: ``"camara"`` ou ``"senado"`` (string discriminadora).
            granularidade: ``"ano"`` ou ``"legislatura"``.

        Returns:
            ``polars.DataFrame`` com colunas:

            - ``bucket`` (Int64): ano ou número da legislatura.
            - ``n_votos`` (Int64): total de votos do parlamentar no bucket.
            - ``proporcao_sim`` (Float64): SIM/total em [0, 1].
            - ``proporcao_nao`` (Float64): NAO/total em [0, 1].
            - ``posicao_dominante`` (Utf8): ``"a_favor"`` / ``"contra"``
              / ``"neutro"``.

            DataFrame vazio se parlamentar sem votos ou todos os buckets
            ficaram abaixo de :data:`MIN_VOTOS_POR_BUCKET`.

        Raises:
            ValueError: ``granularidade`` fora de
                :data:`GRANULARIDADES_VALIDAS`.
            AmostraInsuficiente: Tabela ``votos`` ausente no schema.
        """
        if granularidade not in GRANULARIDADES_VALIDAS:
            raise ValueError(
                f"granularidade inválida: {granularidade!r}. "
                f"Válidas: {sorted(GRANULARIDADES_VALIDAS)}"
            )

        if not _tabela_existe(conn, "votos"):
            raise AmostraInsuficiente("tabela votos ausente")

        bucket_expr = _bucket_expr(granularidade)
        # Campo `data` em `votacoes` é VARCHAR (schema v1 S26). Convertemos
        # via TRY_CAST -> DATE pra extrair YEAR. TRY_CAST devolve NULL em
        # string mal-formada e o WHERE filtra NULL, evitando falha em
        # registros anômalos.
        sql = f"""
            SELECT
                {bucket_expr} AS bucket,
                COUNT(*) AS n_votos,
                CAST(
                    SUM(CASE WHEN UPPER(v.voto) = 'SIM' THEN 1 ELSE 0 END) AS DOUBLE
                ) / COUNT(*) AS proporcao_sim,
                CAST(
                    SUM(CASE WHEN UPPER(v.voto) = 'NAO' THEN 1 ELSE 0 END) AS DOUBLE
                ) / COUNT(*) AS proporcao_nao
            FROM votos v
            JOIN votacoes vt ON vt.id = v.votacao_id AND vt.casa = v.casa
            WHERE v.parlamentar_id = ?
              AND v.casa = ?
              AND TRY_CAST(vt.data AS DATE) IS NOT NULL
            GROUP BY bucket
            HAVING COUNT(*) >= ?
            ORDER BY bucket
        """
        rows = conn.execute(
            sql,
            [parlamentar_id, casa, MIN_VOTOS_POR_BUCKET],
        ).fetchall()

        if not rows:
            return pl.DataFrame(
                schema={
                    "bucket": pl.Int64,
                    "n_votos": pl.Int64,
                    "proporcao_sim": pl.Float64,
                    "proporcao_nao": pl.Float64,
                    "posicao_dominante": pl.Utf8,
                }
            )

        buckets: list[int] = [int(r[0]) for r in rows]
        n_votos: list[int] = [int(r[1]) for r in rows]
        prop_sim: list[float] = [float(r[2]) for r in rows]
        prop_nao: list[float] = [float(r[3]) for r in rows]
        posicao: list[str] = [_classificar_posicao(p) for p in prop_sim]

        return pl.DataFrame(
            {
                "bucket": buckets,
                "n_votos": n_votos,
                "proporcao_sim": prop_sim,
                "proporcao_nao": prop_nao,
                "posicao_dominante": posicao,
            }
        )


def _bucket_expr(granularidade: str) -> str:
    """Retorna a expressão SQL de bucket conforme granularidade.

    Helper isolado para evitar repetir o ``CASE WHEN`` em cada chamada
    e para que :mod:`tests` possa exercitar as duas formas com a mesma
    fonte da verdade.
    """
    if granularidade == "ano":
        return "EXTRACT(YEAR FROM CAST(vt.data AS DATE))::INTEGER"
    # legislatura -- mapa fixo conforme convenção da Câmara/Senado.
    return """CASE
        WHEN EXTRACT(YEAR FROM CAST(vt.data AS DATE)) BETWEEN 2015 AND 2018 THEN 55
        WHEN EXTRACT(YEAR FROM CAST(vt.data AS DATE)) BETWEEN 2019 AND 2022 THEN 56
        WHEN EXTRACT(YEAR FROM CAST(vt.data AS DATE)) >= 2023 THEN 57
        ELSE 0
    END"""


# ---------------------------------------------------------------------------
# DetectorMudancas
# ---------------------------------------------------------------------------


class DetectorMudancas:
    """Detecta mudanças significativas entre buckets adjacentes."""

    @staticmethod
    def detectar(
        historico: pl.DataFrame,
        threshold_pp: float = THRESHOLD_PP_PADRAO,
    ) -> list[dict[str, object]]:
        """Compara buckets adjacentes e retorna eventos de mudança.

        Args:
            historico: DataFrame produzido por
                :meth:`HistoricoConversao.calcular`.
            threshold_pp: Mudança mínima em pontos percentuais (0-100).
                Default :data:`THRESHOLD_PP_PADRAO`.

        Returns:
            Lista (ordenada cronologicamente) de dicts com:

            - ``bucket_anterior`` (int)
            - ``bucket_posterior`` (int)
            - ``proporcao_sim_anterior`` (float)
            - ``proporcao_sim_posterior`` (float)
            - ``delta_pp`` (float, sinal preservado)
            - ``posicao_anterior`` (str)
            - ``posicao_posterior`` (str)

            Lista vazia se ``len(historico) < 2`` ou nenhuma mudança
            atinge o threshold.
        """
        if len(historico) < MIN_BUCKETS:
            return []

        buckets = historico["bucket"].to_list()
        prop_sim = historico["proporcao_sim"].to_list()
        posicao = historico["posicao_dominante"].to_list()

        eventos: list[dict[str, object]] = []
        for idx in range(1, len(historico)):
            anterior = float(prop_sim[idx - 1])
            posterior = float(prop_sim[idx])
            # Delta em pontos percentuais (0-100), sinal preservado.
            delta_pp = (posterior - anterior) * 100.0
            if abs(delta_pp) < threshold_pp:
                continue
            eventos.append(
                {
                    "bucket_anterior": int(buckets[idx - 1]),
                    "bucket_posterior": int(buckets[idx]),
                    "proporcao_sim_anterior": anterior,
                    "proporcao_sim_posterior": posterior,
                    "delta_pp": round(delta_pp, 2),
                    "posicao_anterior": str(posicao[idx - 1]),
                    "posicao_posterior": str(posicao[idx]),
                }
            )
        return eventos


# ---------------------------------------------------------------------------
# IndiceVolatilidade
# ---------------------------------------------------------------------------


class IndiceVolatilidade:
    """Mede volatilidade da posição ao longo dos buckets."""

    @staticmethod
    def calcular(historico: pl.DataFrame) -> float:
        """Volatilidade normalizada em [0, 1].

        Args:
            historico: DataFrame produzido por
                :meth:`HistoricoConversao.calcular`.

        Returns:
            ``std(proporcao_sim) / STD_MAX_TEORICA`` saturado em 1.0.
            Retorna 0.0 se ``len(historico) < 2`` (sem variação possível).
        """
        if len(historico) < MIN_BUCKETS:
            return 0.0
        # std populacional manual (ddof=0) -- evitamos `Series.std` cuja
        # tipagem inclui `timedelta` (mypy strict reclama em union ampla).
        valores = [float(x) for x in historico["proporcao_sim"].to_list()]
        if not valores:
            return 0.0
        media = sum(valores) / len(valores)
        var = sum((x - media) ** 2 for x in valores) / len(valores)
        desvio = float(var**0.5)
        return float(min(desvio / STD_MAX_TEORICA, 1.0))


# ---------------------------------------------------------------------------
# Função de conveniência -- batch sobre top N parlamentares
# ---------------------------------------------------------------------------


def calcular_historico_top(
    conn: duckdb.DuckDBPyConnection,
    top_n: int = 100,
    granularidade: str = "ano",
    threshold_pp: float = THRESHOLD_PP_PADRAO,
) -> dict[str, object]:
    """Calcula histórico para os ``top_n`` parlamentares mais ativos.

    Helper consumido pelo pipeline (``_etapa_historico``) e pela CLI
    (``hemiciclo historico calcular``).

    Args:
        conn: Conexão DuckDB com ``votos``, ``votacoes`` e
            ``parlamentares``.
        top_n: Quantos parlamentares processar, ordenados por
            ``COUNT(votos)`` desc.
        granularidade: ``"ano"`` ou ``"legislatura"``.
        threshold_pp: Threshold passado a :class:`DetectorMudancas`.

    Returns:
        Dict serializável compatível com ``historico_conversao.json``::

            {
                "parlamentares": {<id>: {...}, ...},
                "metadata": {
                    "granularidade": "ano",
                    "threshold_pp": 30.0,
                    "n_parlamentares": 100,
                    "n_com_mudancas": 12,
                    "skipped": false
                }
            }

        Em caso de skip graceful (tabela ausente / sem votos), retorna
        ``parlamentares={}`` e ``metadata.skipped=True`` + motivo.
    """
    if not _tabela_existe(conn, "votos"):
        logger.warning("[historico] tabela 'votos' ausente; SKIPPED")
        return _resultado_skipped(granularidade, threshold_pp, top_n, "tabela votos ausente")

    sql_top = """
        SELECT v.parlamentar_id, v.casa, COUNT(*) AS n
        FROM votos v
        GROUP BY v.parlamentar_id, v.casa
        ORDER BY n DESC
        LIMIT ?
    """
    pares = conn.execute(sql_top, [top_n]).fetchall()
    if not pares:
        logger.warning("[historico] nenhum voto registrado; SKIPPED")
        return _resultado_skipped(granularidade, threshold_pp, top_n, "sem votos no DB")

    nomes = _carregar_nomes(conn, [(int(pid), str(casa)) for pid, casa, _ in pares])

    parlamentares: dict[str, object] = {}
    n_com_mudancas = 0
    for parl_id, casa, _ in pares:
        try:
            historico = HistoricoConversao.calcular(
                conn, int(parl_id), str(casa), granularidade=granularidade
            )
        except AmostraInsuficiente:
            continue
        if len(historico) < MIN_BUCKETS:
            # Skip graceful por parlamentar -- só 1 bucket disponível.
            continue
        mudancas = DetectorMudancas.detectar(historico, threshold_pp=threshold_pp)
        volatilidade = IndiceVolatilidade.calcular(historico)
        if mudancas:
            n_com_mudancas += 1
        parlamentares[str(int(parl_id))] = {
            "casa": str(casa),
            "nome": nomes.get((int(parl_id), str(casa)), str(parl_id)),
            "historico": [
                {
                    "bucket": int(b),
                    "n_votos": int(n),
                    "proporcao_sim": float(ps),
                    "proporcao_nao": float(pn),
                    "posicao": str(pos),
                }
                for b, n, ps, pn, pos in zip(
                    historico["bucket"].to_list(),
                    historico["n_votos"].to_list(),
                    historico["proporcao_sim"].to_list(),
                    historico["proporcao_nao"].to_list(),
                    historico["posicao_dominante"].to_list(),
                    strict=True,
                )
            ],
            "mudancas_detectadas": mudancas,
            "indice_volatilidade": round(float(volatilidade), 4),
        }

    return {
        "parlamentares": parlamentares,
        "metadata": {
            "granularidade": granularidade,
            "threshold_pp": float(threshold_pp),
            "n_parlamentares": len(parlamentares),
            "n_com_mudancas": n_com_mudancas,
            "skipped": False,
        },
    }


def _resultado_skipped(
    granularidade: str, threshold_pp: float, top_n: int, motivo: str
) -> dict[str, object]:
    """Resultado canônico de skip graceful."""
    return {
        "parlamentares": {},
        "metadata": {
            "granularidade": granularidade,
            "threshold_pp": float(threshold_pp),
            "n_parlamentares": 0,
            "n_com_mudancas": 0,
            "skipped": True,
            "motivo": motivo,
            "top_n_solicitado": top_n,
        },
    }


def _carregar_nomes(
    conn: duckdb.DuckDBPyConnection,
    pares: list[tuple[int, str]],
) -> dict[tuple[int, str], str]:
    """Resolve ``(id, casa) -> nome`` consultando ``parlamentares`` em lote.

    Tolera tabela ausente (retorna ``{}``).
    """
    if not pares or not _tabela_existe(conn, "parlamentares"):
        return {}
    ids = [pid for pid, _ in pares]
    placeholders = ", ".join("?" * len(ids))
    sql = f"SELECT id, casa, nome FROM parlamentares WHERE id IN ({placeholders})"
    rows = conn.execute(sql, ids).fetchall()
    saida: dict[tuple[int, str], str] = {}
    for parl_id, casa, nome in rows:
        saida[(int(parl_id), str(casa))] = str(nome) if nome else str(parl_id)
    return saida
