"""Consolida parquets de coleta (S24/S25) em um DB DuckDB unificado (S26).

Função pública: :func:`consolidar_parquets_em_duckdb`.

Estratégia geral:

1. Conecta no DB (cria se necessário).
2. Aplica migrations pendentes (idempotente).
3. Para cada parquet detectado em ``dir_parquets``, mapeia para a tabela
   unificada correspondente do DuckDB e roda ``INSERT OR IGNORE``
   (idempotência ao reconsolidar).
4. Retorna ``dict[tabela, linhas_inseridas]`` somando *novas* linhas por
   tabela.

Mapeamento canônico:

- ``proposicoes.parquet`` (Câmara) -> tabela ``proposicoes`` (casa='camara' do parquet)
- ``materias.parquet`` (Senado) -> mesma tabela ``proposicoes`` (casa='senado' do parquet)
- ``votacoes.parquet`` (Câmara) -> tabela ``votacoes``
- ``votacoes_senado.parquet`` (Senado) -> mesma tabela ``votacoes``
- ``votos.parquet`` (Câmara) -> tabela ``votos``
- ``votos_senado.parquet`` (Senado) -> mesma tabela ``votos``
- ``discursos.parquet`` (Câmara) -> tabela ``discursos``
- ``discursos_senado.parquet`` (Senado) -> mesma tabela ``discursos``
- ``deputados.parquet`` (Câmara) -> tabela ``parlamentares`` (casa='camara' inferida)
- ``senadores.parquet`` (Senado) -> mesma tabela ``parlamentares`` (casa='senado' inferida)

Os schemas dos parquets têm pequenas diferenças entre as casas (a S24/S25
documenta) -- o consolidador converte explicitamente coluna a coluna via
SQL ``SELECT`` no ``read_parquet``, evitando depender de schema nominal.

Robustez: arquivo corrompido é registrado em log e ignorado, não interrompe
a consolidação dos demais.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import duckdb
from loguru import logger

from hemiciclo.etl.migrations import aplicar_migrations

_Inseridor = Callable[[duckdb.DuckDBPyConnection, Path], int]


def _inserir_proposicoes_camara(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere proposicoes.parquet (Câmara, 12 colunas) em ``proposicoes``."""
    antes_row = conn.execute("SELECT COUNT(*) FROM proposicoes").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO proposicoes (
            id, casa, sigla, numero, ano, ementa, tema_oficial,
            autor_principal, data_apresentacao, status, url_inteiro_teor,
            hash_conteudo
        )
        SELECT id, casa, sigla, numero, ano, ementa, tema_oficial,
               autor_principal, data_apresentacao, status, url_inteiro_teor,
               hash_conteudo
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM proposicoes").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_proposicoes_senado(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere materias.parquet (Senado, mesmo schema 12-col) em ``proposicoes``."""
    # Schema é idêntico ao da Câmara por design (S25 alinhou em 12 colunas com
    # ``casa = 'senado'``); mesmo SELECT serve.
    return _inserir_proposicoes_camara(conn, parquet)


def _inserir_votacoes_camara(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere votacoes.parquet (Câmara/Senado: 6 colunas) em ``votacoes``.

    Suporta tanto parquets v2 (com ``proposicao_id``, S27.1) quanto v1
    (legados, sem essa coluna): detecta dinamicamente as colunas presentes
    e usa ``NULL`` quando ``proposicao_id`` está ausente. Funciona para
    ambas as casas porque o schema do parquet ficou alinhado em S27.1
    (Senado renomeou ``materia_id`` -> ``proposicao_id``).
    """
    antes_row = conn.execute("SELECT COUNT(*) FROM votacoes").fetchone()
    antes = int(antes_row[0]) if antes_row else 0

    # DESCRIBE retorna primeira coluna como `column_name` (DuckDB ≥ 0.9).
    cols_parquet = {
        linha[0]
        for linha in conn.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [str(parquet)],
        ).fetchall()
    }
    if "proposicao_id" in cols_parquet:
        proj = "proposicao_id"
    elif "materia_id" in cols_parquet:
        # Compat retroativa com parquets de Senado pré-S27.1.
        proj = "materia_id AS proposicao_id"
    else:
        # Compat com parquets ainda mais antigos sem nenhuma das duas.
        proj = "CAST(NULL AS BIGINT) AS proposicao_id"
    conn.execute(
        f"""
        INSERT OR IGNORE INTO votacoes (
            id, casa, data, descricao, resultado, proposicao_id
        )
        SELECT CAST(id AS VARCHAR), casa, data, descricao, resultado, {proj}
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM votacoes").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_votacoes_senado(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere votacoes_senado.parquet em ``votacoes`` (mesmo SELECT da Câmara)."""
    return _inserir_votacoes_camara(conn, parquet)


def _inserir_votos_camara(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere votos.parquet (Câmara: votacao_id VARCHAR, deputado_id Int) em ``votos``."""
    antes_row = conn.execute("SELECT COUNT(*) FROM votos").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO votos (
            votacao_id, parlamentar_id, casa, voto
        )
        SELECT CAST(votacao_id AS VARCHAR), deputado_id, 'camara', voto
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM votos").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_votos_senado(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere votos_senado.parquet (votacao_id Int, senador_id Int) em ``votos``."""
    antes_row = conn.execute("SELECT COUNT(*) FROM votos").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO votos (
            votacao_id, parlamentar_id, casa, voto
        )
        SELECT CAST(votacao_id AS VARCHAR), senador_id, 'senado', voto
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM votos").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_discursos_camara(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere discursos.parquet (deputado_id) em ``discursos``."""
    antes_row = conn.execute("SELECT COUNT(*) FROM discursos").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO discursos (
            hash_conteudo, parlamentar_id, casa, data, conteudo, sumario
        )
        SELECT hash_conteudo, deputado_id, 'camara', data, transcricao, sumario
        FROM read_parquet(?)
        WHERE hash_conteudo IS NOT NULL AND hash_conteudo <> ''
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM discursos").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_discursos_senado(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere discursos_senado.parquet (senador_id) em ``discursos``."""
    antes_row = conn.execute("SELECT COUNT(*) FROM discursos").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO discursos (
            hash_conteudo, parlamentar_id, casa, data, conteudo, sumario
        )
        SELECT hash_conteudo, senador_id, 'senado', data, transcricao, sumario
        FROM read_parquet(?)
        WHERE hash_conteudo IS NOT NULL AND hash_conteudo <> ''
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM discursos").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_parlamentares_camara(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere deputados.parquet em ``parlamentares`` (casa='camara')."""
    antes_row = conn.execute("SELECT COUNT(*) FROM parlamentares").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO parlamentares (id, casa, nome, partido, uf)
        SELECT id, 'camara', nome, partido, uf
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM parlamentares").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_proposicoes_detalhe(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Atualiza 4 colunas em ``proposicoes`` a partir do parquet de detalhe (S24b).

    Usa ``COALESCE`` para preservar valores existentes quando o detalhe vem
    ``NULL`` (segurança anti-regressão). O parquet contém apenas linhas da
    casa Câmara (campo ``casa = 'camara'`` no schema), e o JOIN é por
    ``id`` + ``casa = 'camara'`` -- nunca colide com Senado.

    Returns:
        Delta de linhas com ``tema_oficial`` não nulo após o ``UPDATE``
        (proxy para "linhas efetivamente enriquecidas nesta chamada").
    """
    antes_row = conn.execute(
        "SELECT COUNT(*) FROM proposicoes "
        "WHERE casa = 'camara' AND tema_oficial IS NOT NULL AND tema_oficial <> ''"
    ).fetchone()
    antes = int(antes_row[0]) if antes_row else 0

    conn.execute(
        """
        UPDATE proposicoes
        SET tema_oficial    = COALESCE(d.tema_oficial,    proposicoes.tema_oficial),
            autor_principal = COALESCE(d.autor_principal, proposicoes.autor_principal),
            status          = COALESCE(d.status,          proposicoes.status),
            url_inteiro_teor = COALESCE(d.url_inteiro_teor, proposicoes.url_inteiro_teor)
        FROM (SELECT * FROM read_parquet(?)) d
        WHERE proposicoes.casa = 'camara' AND proposicoes.id = d.id;
        """,
        [str(parquet)],
    )

    depois_row = conn.execute(
        "SELECT COUNT(*) FROM proposicoes "
        "WHERE casa = 'camara' AND tema_oficial IS NOT NULL AND tema_oficial <> ''"
    ).fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


def _inserir_parlamentares_senado(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Insere senadores.parquet em ``parlamentares`` (casa='senado')."""
    antes_row = conn.execute("SELECT COUNT(*) FROM parlamentares").fetchone()
    antes = int(antes_row[0]) if antes_row else 0
    conn.execute(
        """
        INSERT OR IGNORE INTO parlamentares (id, casa, nome, partido, uf)
        SELECT id, 'senado', nome, partido, uf
        FROM read_parquet(?)
        """,
        [str(parquet)],
    )
    depois_row = conn.execute("SELECT COUNT(*) FROM parlamentares").fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes


# Mapa nome do arquivo -> (tabela alvo, função inseridora). A ordem de
# iteração importa: ``proposicoes_detalhe.parquet`` (S24b) precisa rodar
# DEPOIS de ``proposicoes.parquet`` para que o ``UPDATE`` encontre as
# linhas inseridas.
_INSERIDORES: dict[str, tuple[str, _Inseridor]] = {
    "proposicoes.parquet": ("proposicoes", _inserir_proposicoes_camara),
    "materias.parquet": ("proposicoes", _inserir_proposicoes_senado),
    "proposicoes_detalhe.parquet": ("proposicoes", _inserir_proposicoes_detalhe),
    "votacoes.parquet": ("votacoes", _inserir_votacoes_camara),
    "votacoes_senado.parquet": ("votacoes", _inserir_votacoes_senado),
    "votos.parquet": ("votos", _inserir_votos_camara),
    "votos_senado.parquet": ("votos", _inserir_votos_senado),
    "discursos.parquet": ("discursos", _inserir_discursos_camara),
    "discursos_senado.parquet": ("discursos", _inserir_discursos_senado),
    "deputados.parquet": ("parlamentares", _inserir_parlamentares_camara),
    "senadores.parquet": ("parlamentares", _inserir_parlamentares_senado),
}


def consolidar_parquets_em_duckdb(dir_parquets: Path, db_path: Path) -> dict[str, int]:
    """Carrega todos os parquets reconhecidos de ``dir_parquets`` em ``db_path``.

    Aplica migrations pendentes antes de inserir. Idempotente via
    ``INSERT OR IGNORE`` -- reconsolidar parquets já carregados não
    duplica linhas.

    Args:
        dir_parquets: Diretório contendo arquivos como ``proposicoes.parquet``,
            ``materias.parquet``, etc. Arquivos não reconhecidos são ignorados
            silenciosamente.
        db_path: Caminho do arquivo DuckDB. Cria se ausente.

    Returns:
        Dicionário ``{tabela: linhas_inseridas}`` com soma das *novas* linhas
        por tabela. Tabelas sem inserções nesta chamada não aparecem (chave
        omitida = 0).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    try:
        aplicar_migrations(conn)

        contagens: dict[str, int] = {}
        if not dir_parquets.exists():
            logger.warning("[etl][consolidar] diretório inexistente: {d}", d=dir_parquets)
            return contagens

        for nome, (tabela, fn) in _INSERIDORES.items():
            arquivo = dir_parquets / nome
            if not arquivo.exists():
                continue
            try:
                inseridas = fn(conn, arquivo)
            except (duckdb.Error, OSError) as exc:
                logger.error(
                    "[etl][consolidar] falha ao consolidar {a}: {e}",
                    a=arquivo,
                    e=exc,
                )
                continue
            if inseridas > 0:
                contagens[tabela] = contagens.get(tabela, 0) + inseridas
            logger.info(
                "[etl][consolidar] {a} -> {t}: +{n} linhas",
                a=nome,
                t=tabela,
                n=inseridas,
            )
        return contagens
    finally:
        conn.close()
