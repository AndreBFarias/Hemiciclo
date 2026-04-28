"""Grafos parlamentares (S32) -- coautoria + voto + métricas.

Dois grafos complementares construídos a partir de ``dados.duckdb`` da
sessão. Ambos são :class:`networkx.Graph` não-dirigidos com nós =
parlamentares (id inteiro) e atributos ``nome``, ``partido``, ``uf``.

- :class:`GrafoCoautoria` -- aresta = "votaram juntos na mesma votação".
  É o melhor proxy disponível enquanto S27.1 não vem (não temos ainda
  ``votacoes.proposicao_id`` para coautoria de proposição real). Peso da
  aresta = número de votações em comum (mínimo 5 por padrão).
- :class:`GrafoVoto` -- aresta = afinidade de voto (mesma posição em N
  votações). Peso = proporção de coincidência ([0, 1]).

:class:`MetricasGrafo` calcula centralidade de grau, comunidades (Louvain
quando ``community`` está disponível, fallback ``greedy_modularity_communities``)
e tamanho da maior componente conexa.

**Skip graceful** rigoroso (S32 §3.1):

- Tabela ``votos`` ausente / coluna inesperada -> WARNING + grafo vazio.
- Menos de 5 nós -> levanta :class:`AmostraInsuficiente` para o caller
  registrar ``SKIPPED``.
- ``community`` ausente em runtime -> fallback automático para o
  algoritmo de :func:`networkx.community.greedy_modularity_communities`.

Determinismo: Louvain recebe ``random_state=42`` quando suportado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    import duckdb
    import networkx as nx


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PESO_MINIMO_COAUTORIA: int = 5
"""Número mínimo de votações em comum para criar aresta no grafo de coautoria."""

PESO_MINIMO_VOTO: float = 0.5
"""Coincidência mínima (50%) para aresta no grafo de afinidade de voto."""

MIN_NOS_GRAFO: int = 5
"""Abaixo deste número de nós o grafo é considerado amostra insuficiente."""

LIMITE_NOS_PYVIS: int = 200
"""Acima disto, pyvis fica pesado: filtramos top-N por centralidade."""

RANDOM_STATE: int = 42
"""Seed determinística (I3 do BRIEF)."""


# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------


class AmostraInsuficiente(Exception):  # noqa: N818 -- nome PT-BR, precedente IntegridadeViolada
    """Levantada quando o grafo tem menos de :data:`MIN_NOS_GRAFO` nós.

    O caller deve tratar como SKIPPED graceful, não como erro fatal.
    """


# ---------------------------------------------------------------------------
# Helpers de schema
# ---------------------------------------------------------------------------


def _tabela_existe(conn: duckdb.DuckDBPyConnection, nome: str) -> bool:
    """Retorna ``True`` se a tabela existe no schema atual."""
    sql = "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1"
    linha = conn.execute(sql, [nome]).fetchone()
    return linha is not None


def _enriquecer_metadados(conn: duckdb.DuckDBPyConnection, grafo: nx.Graph) -> None:
    """Agrega ``nome``, ``partido``, ``uf`` em cada nó a partir de ``parlamentares``.

    Tolera tabela ausente: nó fica só com id como label.
    """
    if not grafo.nodes() or not _tabela_existe(conn, "parlamentares"):
        return
    ids = list(grafo.nodes())
    placeholders = ", ".join("?" * len(ids))
    sql = f"SELECT id, nome, partido, uf FROM parlamentares WHERE id IN ({placeholders})"
    rows = conn.execute(sql, ids).fetchall()
    for parl_id, nome, partido, uf in rows:
        if parl_id in grafo.nodes:
            grafo.nodes[parl_id]["nome"] = nome or str(parl_id)
            grafo.nodes[parl_id]["partido"] = partido or ""
            grafo.nodes[parl_id]["uf"] = uf or ""


# ---------------------------------------------------------------------------
# GrafoCoautoria
# ---------------------------------------------------------------------------


class GrafoCoautoria:
    """Grafo de coautoria por proxy: parlamentares que votaram nas mesmas votações.

    Limitação documentada: enquanto S27.1 não entrega ``votacoes.proposicao_id``,
    "coautoria de PL" é aproximada por "co-presença em votação". O peso é a
    contagem de votações compartilhadas, com corte mínimo
    :data:`PESO_MINIMO_COAUTORIA` para não inflar o grafo.
    """

    @staticmethod
    def construir(
        conn: duckdb.DuckDBPyConnection,
        peso_minimo: int = PESO_MINIMO_COAUTORIA,
    ) -> nx.Graph:
        """Constrói o grafo a partir de ``dados.duckdb``.

        Args:
            conn: Conexão DuckDB ativa, com tabela ``votos`` populada.
            peso_minimo: Corte mínimo de votações em comum (default 5).

        Returns:
            ``networkx.Graph`` com nós = parlamentares, arestas com
            atributo ``weight``.

        Raises:
            AmostraInsuficiente: Se o grafo final tem menos de
                :data:`MIN_NOS_GRAFO` nós.
        """
        import networkx as nx  # noqa: PLC0415 -- lazy

        grafo = nx.Graph()
        if not _tabela_existe(conn, "votos"):
            logger.warning("[grafo][coautoria] tabela 'votos' ausente; grafo vazio")
            raise AmostraInsuficiente("tabela votos ausente")

        sql = """
        SELECT v1.parlamentar_id AS u, v2.parlamentar_id AS v, COUNT(*) AS peso
        FROM votos v1
        JOIN votos v2 ON v1.votacao_id = v2.votacao_id AND v1.casa = v2.casa
        WHERE v1.parlamentar_id < v2.parlamentar_id
        GROUP BY u, v
        HAVING peso >= ?
        """
        rows = conn.execute(sql, [peso_minimo]).fetchall()
        for u, v, peso in rows:
            grafo.add_edge(int(u), int(v), weight=int(peso))

        _enriquecer_metadados(conn, grafo)

        if len(grafo.nodes()) < MIN_NOS_GRAFO:
            raise AmostraInsuficiente(
                f"grafo coautoria com {len(grafo.nodes())} nós (< {MIN_NOS_GRAFO})"
            )
        logger.info(
            "[grafo][coautoria] construido: nos={n} arestas={a}",
            n=len(grafo.nodes()),
            a=len(grafo.edges()),
        )
        return grafo


# ---------------------------------------------------------------------------
# GrafoVoto
# ---------------------------------------------------------------------------


class GrafoVoto:
    """Grafo de afinidade por voto nominal.

    Para cada par (u, v) de parlamentares que votaram nas mesmas votações,
    calcula a fração de votações em que tiveram a mesma posição (SIM, NÃO,
    ABSTENÇÃO, etc). Aresta criada apenas se afinidade >=
    :data:`PESO_MINIMO_VOTO`.
    """

    @staticmethod
    def construir(
        conn: duckdb.DuckDBPyConnection,
        peso_minimo: float = PESO_MINIMO_VOTO,
    ) -> nx.Graph:
        """Constrói o grafo de afinidade de voto.

        Args:
            conn: Conexão DuckDB ativa, com tabela ``votos`` populada.
            peso_minimo: Coincidência mínima (default 0.5 = 50%).

        Returns:
            ``networkx.Graph`` com peso = fração de coincidência [0, 1].

        Raises:
            AmostraInsuficiente: Se o grafo final tem menos de
                :data:`MIN_NOS_GRAFO` nós.
        """
        import networkx as nx  # noqa: PLC0415 -- lazy

        grafo = nx.Graph()
        if not _tabela_existe(conn, "votos"):
            logger.warning("[grafo][voto] tabela 'votos' ausente; grafo vazio")
            raise AmostraInsuficiente("tabela votos ausente")

        sql = """
        WITH pares AS (
            SELECT
                v1.parlamentar_id AS u,
                v2.parlamentar_id AS v,
                SUM(CASE WHEN v1.voto = v2.voto THEN 1 ELSE 0 END) AS coincidencias,
                COUNT(*) AS total
            FROM votos v1
            JOIN votos v2 ON v1.votacao_id = v2.votacao_id AND v1.casa = v2.casa
            WHERE v1.parlamentar_id < v2.parlamentar_id
            GROUP BY u, v
            HAVING total >= 5
        )
        SELECT u, v, CAST(coincidencias AS DOUBLE) / total AS afinidade
        FROM pares
        WHERE CAST(coincidencias AS DOUBLE) / total >= ?
        """
        rows = conn.execute(sql, [peso_minimo]).fetchall()
        for u, v, afinidade in rows:
            grafo.add_edge(int(u), int(v), weight=float(afinidade))

        _enriquecer_metadados(conn, grafo)

        if len(grafo.nodes()) < MIN_NOS_GRAFO:
            raise AmostraInsuficiente(
                f"grafo voto com {len(grafo.nodes())} nós (< {MIN_NOS_GRAFO})"
            )
        logger.info(
            "[grafo][voto] construido: nos={n} arestas={a}",
            n=len(grafo.nodes()),
            a=len(grafo.edges()),
        )
        return grafo


# ---------------------------------------------------------------------------
# MetricasGrafo
# ---------------------------------------------------------------------------


class MetricasGrafo:
    """Métricas derivadas: centralidade, comunidades, componentes."""

    @staticmethod
    def calcular_centralidade(grafo: nx.Graph) -> dict[Any, float]:
        """Centralidade de grau (proporção de vizinhos sobre N-1).

        Retorna ``{node_id: float em [0, 1]}``. Em grafo vazio retorna ``{}``.
        """
        import networkx as nx  # noqa: PLC0415 -- lazy

        if len(grafo.nodes()) == 0:
            return {}
        return dict(nx.degree_centrality(grafo))

    @staticmethod
    def detectar_comunidades(grafo: nx.Graph) -> dict[Any, int]:
        """Detecta comunidades via Louvain (se disponível) ou modularity.

        Returns:
            Mapa ``{node_id: comunidade_id_inteiro}``. Em grafo vazio
            retorna ``{}``. Determinismo: ``random_state=42``.
        """
        import networkx as nx  # noqa: PLC0415 -- lazy

        if len(grafo.nodes()) == 0:
            return {}

        try:
            import community as community_louvain  # noqa: PLC0415 -- lazy

            return dict(community_louvain.best_partition(grafo, random_state=RANDOM_STATE))
        except ImportError:
            logger.warning(
                "[grafo][comunidades] python-louvain ausente; usando fallback "
                "networkx.greedy_modularity_communities"
            )
            comunidades_iter = nx.community.greedy_modularity_communities(grafo)
            mapa: dict[Any, int] = {}
            for idx, conjunto in enumerate(comunidades_iter):
                for node in conjunto:
                    mapa[node] = idx
            return mapa

    @staticmethod
    def tamanho_maior_componente(grafo: nx.Graph) -> int:
        """Retorna o tamanho (número de nós) da maior componente conexa.

        Em grafo vazio retorna ``0``.
        """
        import networkx as nx  # noqa: PLC0415 -- lazy

        if len(grafo.nodes()) == 0:
            return 0
        componentes = list(nx.connected_components(grafo))
        if not componentes:
            return 0
        return max(len(c) for c in componentes)

    @staticmethod
    def aplicar_atributos(grafo: nx.Graph) -> None:
        """Anota cada nó com ``centralidade`` e ``comunidade`` in-place.

        Útil para a renderização pyvis colorir e dimensionar nós sem
        precisar receber os mapas separadamente.
        """
        cent = MetricasGrafo.calcular_centralidade(grafo)
        com = MetricasGrafo.detectar_comunidades(grafo)
        for node in grafo.nodes():
            grafo.nodes[node]["centralidade"] = float(cent.get(node, 0.0))
            grafo.nodes[node]["comunidade"] = int(com.get(node, 0))

    @staticmethod
    def top_centrais(grafo: nx.Graph, top_n: int = 10) -> list[dict[str, Any]]:
        """Retorna lista ordenada (desc) de top N nós por centralidade.

        Cada item: ``{"id": int, "nome": str, "partido": str, "uf": str,
        "centralidade": float, "comunidade": int}``.
        """
        cent = MetricasGrafo.calcular_centralidade(grafo)
        com = MetricasGrafo.detectar_comunidades(grafo)
        ordenados = sorted(cent.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        saida: list[dict[str, Any]] = []
        for node_id, valor in ordenados:
            atrs = grafo.nodes[node_id]
            saida.append(
                {
                    "id": int(node_id),
                    "nome": str(atrs.get("nome", str(node_id))),
                    "partido": str(atrs.get("partido", "")),
                    "uf": str(atrs.get("uf", "")),
                    "centralidade": float(valor),
                    "comunidade": int(com.get(node_id, 0)),
                }
            )
        return saida

    @staticmethod
    def filtrar_top(grafo: nx.Graph, max_nos: int = LIMITE_NOS_PYVIS) -> nx.Graph:
        """Retorna subgrafo com top ``max_nos`` por centralidade.

        Necessário para pyvis: HTML com 500+ nós fica pesado e perde
        legibilidade.
        """
        if len(grafo.nodes()) <= max_nos:
            return grafo
        cent = MetricasGrafo.calcular_centralidade(grafo)
        ordenados = sorted(cent.items(), key=lambda kv: kv[1], reverse=True)
        nos_manter = {node for node, _ in ordenados[:max_nos]}
        return grafo.subgraph(nos_manter).copy()
