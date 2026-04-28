"""Coletor da API do Senado Federal (Dados Abertos).

Endpoints alvo (todos públicos do governo brasileiro -- I1):

- ``https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/{leg}``
- ``https://legis.senado.leg.br/dadosabertos/senador/{cod}``
- ``https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista``
- ``https://legis.senado.leg.br/dadosabertos/plenario/lista/votacao/{ano}``
- ``https://legis.senado.leg.br/dadosabertos/plenario/votacao/{cod}``
- ``https://legis.senado.leg.br/dadosabertos/senador/{cod}/discursos``

Diferenças vs Câmara:

- API do Senado retorna XML por default em vários endpoints. Quando
  possível, negociamos ``Accept: application/json`` -- mas o helper
  :func:`_parse_xml_ou_json` faz fallback para parse XML via ``lxml``.
- IDs são inteiros (``int``).
- Volume menor (81 senadores vs 513 deputados).

Cada função de coleta:

1. Respeita o ``TokenBucket`` para rate limiting.
2. Aplica ``@retry_resiliente`` para resiliência.
3. Itera item por item (Iterator) ou retorna lista, conforme cardinalidade.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import polars as pl
from loguru import logger

from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.checkpoint import (
    CheckpointSenado,
    caminho_checkpoint_senado,
    carregar_checkpoint_senado,
    hash_params_senado,
    salvar_checkpoint_senado,
)
from hemiciclo.coleta.http import (
    cliente_http,
    raise_para_status,
    retry_resiliente,
)
from hemiciclo.coleta.rate_limit import TokenBucket

if TYPE_CHECKING:  # pragma: no cover
    pass

URL_BASE = "https://legis.senado.leg.br/dadosabertos"
"""Base da API Dados Abertos do Senado (público, governo BR -- I1)."""

CHECKPOINT_INTERVALO = 50
"""Salva o checkpoint a cada N requisições bem-sucedidas."""


SCHEMA_MATERIA: dict[str, pl.DataType] = {
    "id": pl.Int64(),
    "sigla": pl.Utf8(),
    "numero": pl.Int64(),
    "ano": pl.Int64(),
    "ementa": pl.Utf8(),
    "tema_oficial": pl.Utf8(),
    "autor_principal": pl.Utf8(),
    "data_apresentacao": pl.Utf8(),
    "status": pl.Utf8(),
    "url_inteiro_teor": pl.Utf8(),
    "casa": pl.Utf8(),
    "hash_conteudo": pl.Utf8(),
}
"""Schema mínimo do Parquet de matérias (12 colunas, alinhado com Câmara).

Permite união simples em S26 (DuckDB unificado) bastando
``UNION ALL`` entre proposicoes.parquet (casa='camara') e
materias.parquet (casa='senado').
"""

SCHEMA_VOTACAO: dict[str, pl.DataType] = {
    "id": pl.Int64(),
    "data": pl.Utf8(),
    "descricao": pl.Utf8(),
    "proposicao_id": pl.Int64(),
    "resultado": pl.Utf8(),
    "casa": pl.Utf8(),
}
"""Schema do parquet de votações do Senado.

A coluna passou a se chamar ``proposicao_id`` em S27.1 (antes ``materia_id``)
para alinhar com Câmara e simplificar o consolidador, que insere ambas as
casas na mesma tabela ``votacoes`` do DuckDB. Semanticamente é o
``CodigoMateria`` do XML do Senado -- a matéria à qual a votação se refere.
"""

SCHEMA_VOTO: dict[str, pl.DataType] = {
    "votacao_id": pl.Int64(),
    "senador_id": pl.Int64(),
    "voto": pl.Utf8(),
    "partido": pl.Utf8(),
    "uf": pl.Utf8(),
}

SCHEMA_DISCURSO: dict[str, pl.DataType] = {
    "id": pl.Utf8(),
    "senador_id": pl.Int64(),
    "data": pl.Utf8(),
    "tipo": pl.Utf8(),
    "sumario": pl.Utf8(),
    "url_audio": pl.Utf8(),
    "url_video": pl.Utf8(),
    "transcricao": pl.Utf8(),
    "hash_conteudo": pl.Utf8(),
}

SCHEMA_SENADOR: dict[str, pl.DataType] = {
    "id": pl.Int64(),
    "nome": pl.Utf8(),
    "nome_eleitoral": pl.Utf8(),
    "partido": pl.Utf8(),
    "uf": pl.Utf8(),
    "legislatura": pl.Int64(),
    "email": pl.Utf8(),
}


def _xml_para_dict(elemento: Any) -> dict[str, Any]:
    """Converte um elemento ``lxml.etree`` para dict aninhado.

    Estratégia: cada elemento vira dict com chaves dos filhos. Quando há
    múltiplos filhos com a mesma tag, agrega em lista. Texto puro vira
    valor escalar string. Tags do Senado aparecem em camelCase
    (ex.: ``CodigoMateria``); preservamos.
    """
    resultado: dict[str, Any] = {}
    for filho in elemento:
        tag = filho.tag
        # Strip namespace XML se houver.
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        if len(filho) > 0:
            valor: Any = _xml_para_dict(filho)
        else:
            texto = filho.text
            valor = texto.strip() if isinstance(texto, str) else ""
        if tag in resultado:
            if isinstance(resultado[tag], list):
                resultado[tag].append(valor)
            else:
                resultado[tag] = [resultado[tag], valor]
        else:
            resultado[tag] = valor
    return resultado


def _parse_xml_ou_json(resp: httpx.Response) -> dict[str, Any]:
    """Parseia resposta JSON ou XML (fallback).

    Args:
        resp: Resposta HTTP.

    Returns:
        Dict com a estrutura aninhada do payload. Para XML, a chave de
        primeiro nível é a tag raiz do documento.
    """
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype or ctype.endswith("/json"):
        corpo: Any = resp.json()
        if isinstance(corpo, dict):
            return corpo
        return {"dados": corpo}

    # Fallback: XML. Importação lazy evita custo se nunca usado.
    from lxml import etree

    raiz = etree.fromstring(resp.content)
    tag_raiz = raiz.tag
    if "}" in tag_raiz:
        tag_raiz = tag_raiz.split("}", 1)[1]
    return {tag_raiz: _xml_para_dict(raiz)}


@retry_resiliente
def _baixar(
    cli: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Baixa uma página JSON ou XML com retry resiliente."""
    inicio = time.monotonic()
    headers = {"Accept": "application/json"}
    resp = cli.get(url, params=params, headers=headers)
    raise_para_status(resp)
    duracao = time.monotonic() - inicio
    logger.info(
        "GET {url} -> {status} em {duracao:.2f}s",
        url=str(resp.request.url),
        status=resp.status_code,
        duracao=duracao,
    )
    return _parse_xml_ou_json(resp)


def _itens_de(corpo: dict[str, Any], *caminho: str) -> list[dict[str, Any]]:
    """Navega pelo caminho aninhado e retorna sempre uma lista de itens.

    O Senado por vezes retorna um único item sem wrapper de lista.
    Normalizamos: ``{"X": {"Y": item}}`` ou ``{"X": {"Y": [item, item]}}``
    sempre vira ``[item, ...]``. Dicts são empacotados em lista de 1 elemento.
    """
    no: Any = corpo
    for chave in caminho:
        if not isinstance(no, dict) or chave not in no:
            return []
        no = no[chave]
        if no is None:
            return []
    if isinstance(no, list):
        return [d for d in no if isinstance(d, dict)]
    if isinstance(no, dict):
        return [no]
    return []


def coletar_senadores(
    legislatura: int,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Baixa cadastro de senadores ativos numa legislatura.

    Args:
        legislatura: Legislatura alvo (ex.: 56).
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.

    Returns:
        Lista de dicts brutos (``IdentificacaoParlamentar`` do Senado).
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/senador/lista/legislatura/{legislatura}"
        bucket.aguardar()
        corpo = _baixar(cli, url)
        # Caminho típico (JSON): ListaParlamentarLegislatura.Parlamentares.Parlamentar
        return _itens_de(corpo, "ListaParlamentarLegislatura", "Parlamentares", "Parlamentar")
    finally:
        if fechar_cli:
            cli.close()


def coletar_materias(
    ano: int,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera matérias do Senado pelo ano de apresentação.

    Args:
        ano: Ano da apresentação.
        max_itens: Limite total. ``None`` = sem limite.
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.

    Yields:
        Dict bruto da API por matéria.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/materia/pesquisa/lista"
        params: dict[str, Any] = {"ano": ano}
        bucket.aguardar()
        corpo = _baixar(cli, url, params=params)

        materias = _itens_de(
            corpo,
            "PesquisaBasicaMateria",
            "Materias",
            "Materia",
        )
        for indice, item in enumerate(materias, start=1):
            yield item
            if max_itens is not None and indice >= max_itens:
                return
    finally:
        if fechar_cli:
            cli.close()


def coletar_votacoes(
    ano: int,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera votações nominais do plenário do Senado num ano.

    Args:
        ano: Ano alvo.
        max_itens: Limite total.
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.

    Yields:
        Dict bruto da API por votação.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/plenario/lista/votacao/{ano}"
        bucket.aguardar()
        corpo = _baixar(cli, url)
        votacoes = _itens_de(corpo, "ListaVotacoes", "Votacoes", "Votacao")
        for indice, item in enumerate(votacoes, start=1):
            yield item
            if max_itens is not None and indice >= max_itens:
                return
    finally:
        if fechar_cli:
            cli.close()


def coletar_votos_de_votacao(
    votacao_id: int,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Baixa todos os votos individuais de uma votação do Senado.

    Args:
        votacao_id: Código da votação.
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.

    Returns:
        Lista de dicts brutos com voto + senador identificador.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/plenario/votacao/{votacao_id}"
        bucket.aguardar()
        corpo = _baixar(cli, url)
        return _itens_de(corpo, "VotacaoPlenario", "Votos", "VotoParlamentar")
    finally:
        if fechar_cli:
            cli.close()


def coletar_discursos(
    senador_codigo: int,
    ano: int | None = None,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera discursos de um senador.

    Args:
        senador_codigo: Código do senador.
        ano: Filtro opcional por ano.
        max_itens: Limite total.
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.

    Yields:
        Dict bruto por discurso.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/senador/{senador_codigo}/discursos"
        params: dict[str, Any] = {}
        if ano is not None:
            params["ano"] = ano
        bucket.aguardar()
        corpo = _baixar(cli, url, params=params or None)
        discursos = _itens_de(
            corpo,
            "DiscursosParlamentar",
            "Parlamentar",
            "Pronunciamentos",
            "Pronunciamento",
        )
        for indice, item in enumerate(discursos, start=1):
            item_completo = dict(item)
            item_completo["senador_id"] = senador_codigo
            yield item_completo
            if max_itens is not None and indice >= max_itens:
                return
    finally:
        if fechar_cli:
            cli.close()


# ---------------------------------------------------------------------------
# Normalizadores -- achatam a estrutura aninhada para o schema mínimo.
# ---------------------------------------------------------------------------


def _hash_texto(texto: str) -> str:
    """SHA256 dos primeiros 16 chars (lição S24: hash da ementa, não da URI)."""
    if not texto:
        return ""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _str_ou_vazio(valor: Any) -> str:
    """Converte para string, tratando ``None`` e dicts vazios como ``""``."""
    if valor is None:
        return ""
    if isinstance(valor, dict):
        return ""
    return str(valor)


def _int_ou_zero(valor: Any) -> int:
    """Converte para int, com fallback 0 em payloads malformados."""
    if valor is None or valor == "":
        return 0
    if isinstance(valor, dict):
        return 0
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _normalizar_materia(item: dict[str, Any]) -> dict[str, Any]:
    """Achata estrutura aninhada do Senado em 12 colunas alinhadas com Câmara.

    Suporta dois formatos de payload da API real:

    1. Detalhe (``IdentificacaoMateria`` aninhado): chaves
       ``CodigoMateria``, ``SiglaSubtipoMateria``, ``NumeroMateria``,
       ``AnoMateria``, ``EmentaMateria``, ``AutorPrincipal.NomeAutor``,
       ``SituacaoAtual.DescricaoSituacao``.
    2. Listagem v7 (``/materia/pesquisa/lista``): chaves no nível raiz
       como ``Codigo``, ``Sigla``, ``Numero``, ``Ano``, ``Ementa``,
       ``Autor``, ``Data``, ``UrlDetalheMateria``.

    O normalizador tenta ambos, com prioridade para o formato 1 quando
    presente.
    """
    ident = item.get("IdentificacaoMateria") or {}
    if not isinstance(ident, dict):
        ident = {}
    autor_dict = item.get("AutorPrincipal") or {}
    if not isinstance(autor_dict, dict):
        autor_dict = {}
    situacao = item.get("SituacaoAtual") or {}
    if not isinstance(situacao, dict):
        situacao = {}

    ementa = _str_ou_vazio(item.get("EmentaMateria") or item.get("Ementa"))
    # Autor pode vir como dict (formato 1) OU string (formato 2 -- v7)
    autor_str = _str_ou_vazio(autor_dict.get("NomeAutor")) or _str_ou_vazio(item.get("Autor"))
    return {
        "id": _int_ou_zero(
            ident.get("CodigoMateria") or item.get("CodigoMateria") or item.get("Codigo")
        ),
        "sigla": _str_ou_vazio(
            ident.get("SiglaSubtipoMateria") or ident.get("SiglaTipoMateria") or item.get("Sigla")
        ),
        "numero": _int_ou_zero(ident.get("NumeroMateria") or item.get("Numero")),
        "ano": _int_ou_zero(ident.get("AnoMateria") or item.get("Ano")),
        "ementa": ementa,
        "tema_oficial": _str_ou_vazio(item.get("IndexacaoMateria")),
        "autor_principal": autor_str,
        "data_apresentacao": _str_ou_vazio(item.get("DataApresentacao") or item.get("Data")),
        "status": _str_ou_vazio(situacao.get("DescricaoSituacao")),
        "url_inteiro_teor": _str_ou_vazio(
            item.get("UrlTexto") or item.get("UrlInteiroTeor") or item.get("UrlDetalheMateria")
        ),
        "casa": "senado",
        "hash_conteudo": _hash_texto(ementa),
    }


def _normalizar_votacao(item: dict[str, Any]) -> dict[str, Any]:
    """Achata votação do Senado em 6 colunas alinhadas com Câmara (S25 + S27.1).

    ``proposicao_id`` corresponde ao ``CodigoMateria`` do XML do Senado --
    semanticamente o mesmo conceito de "proposição principal" da API da
    Câmara, alinhado em uma coluna comum. Quando a votação não tem matéria
    associada (raro), o valor é ``None`` (NULL no parquet e no DB).
    """
    materia = item.get("Materia") or {}
    if not isinstance(materia, dict):
        materia = {}
    bruto = materia.get("CodigoMateria")
    proposicao_id: int | None
    if bruto is None or bruto == "" or isinstance(bruto, dict):
        proposicao_id = None
    else:
        try:
            proposicao_id = int(bruto)
        except (TypeError, ValueError):
            proposicao_id = None
    return {
        "id": _int_ou_zero(item.get("CodigoSessaoVotacao") or item.get("CodigoVotacao")),
        "data": _str_ou_vazio(item.get("DataSessao") or item.get("Data")),
        "descricao": _str_ou_vazio(item.get("DescricaoVotacao") or item.get("Descricao")),
        "proposicao_id": proposicao_id,
        "resultado": _str_ou_vazio(item.get("Resultado") or item.get("DescricaoResultado")),
        "casa": "senado",
    }


def _normalizar_voto(votacao_id: int, item: dict[str, Any]) -> dict[str, Any]:
    """Achata voto individual em 5 colunas."""
    parlamentar = item.get("IdentificacaoParlamentar") or {}
    if not isinstance(parlamentar, dict):
        parlamentar = {}
    return {
        "votacao_id": votacao_id,
        "senador_id": _int_ou_zero(parlamentar.get("CodigoParlamentar")),
        "voto": _str_ou_vazio(item.get("DescricaoVoto") or item.get("Voto")),
        "partido": _str_ou_vazio(parlamentar.get("SiglaPartidoParlamentar")),
        "uf": _str_ou_vazio(parlamentar.get("UfParlamentar")),
    }


def _normalizar_discurso(item: dict[str, Any]) -> dict[str, Any]:
    """Achata discurso em 9 colunas alinhadas com Câmara."""
    transcricao = _str_ou_vazio(item.get("TextoIntegralTxt") or item.get("Transcricao"))
    return {
        "id": _str_ou_vazio(item.get("CodigoPronunciamento") or item.get("DataPronunciamento")),
        "senador_id": _int_ou_zero(item.get("senador_id")),
        "data": _str_ou_vazio(item.get("DataPronunciamento") or item.get("Data")),
        "tipo": _str_ou_vazio(item.get("TipoUsoPalavra")),
        "sumario": _str_ou_vazio(item.get("Resumo") or item.get("Sumario")),
        "url_audio": _str_ou_vazio(item.get("UrlAudio")),
        "url_video": _str_ou_vazio(item.get("UrlVideo")),
        "transcricao": transcricao,
        "hash_conteudo": _hash_texto(transcricao),
    }


def _normalizar_senador(item: dict[str, Any], legislatura: int) -> dict[str, Any]:
    """Achata cadastro de senador em 7 colunas alinhadas com Câmara."""
    parlamentar = item.get("IdentificacaoParlamentar") or item
    if not isinstance(parlamentar, dict):
        parlamentar = {}
    return {
        "id": _int_ou_zero(parlamentar.get("CodigoParlamentar")),
        "nome": _str_ou_vazio(parlamentar.get("NomeParlamentar")),
        "nome_eleitoral": _str_ou_vazio(
            parlamentar.get("NomeCompletoParlamentar") or parlamentar.get("NomeParlamentar")
        ),
        "partido": _str_ou_vazio(parlamentar.get("SiglaPartidoParlamentar")),
        "uf": _str_ou_vazio(parlamentar.get("UfParlamentar")),
        "legislatura": legislatura,
        "email": _str_ou_vazio(parlamentar.get("EmailParlamentar")),
    }


def _escrever_parquet(
    registros: list[dict[str, Any]],
    schema: dict[str, pl.DataType],
    arquivo: Path,
) -> int:
    """Escreve lista de dicts como Parquet com schema explícito."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(schema=schema) if not registros else pl.DataFrame(registros, schema=schema)
    df.write_parquet(arquivo)
    return df.height


def executar_coleta(
    params: ParametrosColeta,
    home: Path,
    bucket: TokenBucket | None = None,
) -> CheckpointSenado:
    """Orquestra a coleta inteira do Senado respeitando checkpoint resumível.

    Diferente da Câmara, parametriza por **ano** (mais granular). Quando
    apenas legislaturas foram passadas, derivamos uma faixa razoável de
    anos a partir delas (4 anos por legislatura).

    Args:
        params: Parâmetros validados da coleta.
        home: Diretório raiz do Hemiciclo (para localizar checkpoint).
        bucket: Token bucket. Cria default se ``None``.

    Returns:
        Checkpoint final atualizado (também persistido no disco).
    """
    if bucket is None:
        bucket = TokenBucket()

    # Derivar anos a partir de data_inicio/data_fim quando presentes; senão
    # usar legislaturas com 4 anos cada.
    if params.data_inicio is not None and params.data_fim is not None:
        anos = list(range(params.data_inicio.year, params.data_fim.year + 1))
    else:
        anos = []
        for leg in params.legislaturas:
            ano_inicial_leg = 1995 + 4 * (leg - 50)  # mesma fórmula da Câmara
            anos.extend(range(ano_inicial_leg, ano_inicial_leg + 4))
        anos = sorted(set(anos))

    h = hash_params_senado(anos, list(params.tipos))
    cp_path = caminho_checkpoint_senado(home, h)
    checkpoint = carregar_checkpoint_senado(cp_path)
    if checkpoint is None:
        checkpoint = CheckpointSenado(
            iniciado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
            legislaturas=list(params.legislaturas),
            anos=anos,
            tipos=list(params.tipos),
        )
        logger.info("Checkpoint Senado novo criado em {p}", p=cp_path)
    else:
        logger.info(
            "Checkpoint Senado existente carregado: {n} itens ja baixados",
            n=checkpoint.total_baixado(),
        )

    params.dir_saida.mkdir(parents=True, exist_ok=True)
    contador_req = 0

    def _talvez_salvar(forcar: bool = False) -> None:
        nonlocal contador_req
        if forcar or contador_req >= CHECKPOINT_INTERVALO:
            checkpoint.atualizado_em = datetime.now(UTC)
            salvar_checkpoint_senado(checkpoint, cp_path)
            logger.debug("Checkpoint Senado salvo em {p}", p=cp_path)
            contador_req = 0

    log = logger.bind(coleta="senado", anos=anos)

    cli = cliente_http()
    try:
        if "materias" in params.tipos:
            inicio = time.monotonic()
            registros: list[dict[str, Any]] = []
            for ano in anos:
                for item in coletar_materias(
                    ano,
                    max_itens=params.max_itens,
                    bucket=bucket,
                    cli=cli,
                ):
                    norm = _normalizar_materia(item)
                    if norm["id"] in checkpoint.materias_baixadas:
                        continue
                    registros.append(norm)
                    checkpoint.materias_baixadas.add(norm["id"])
                    contador_req += 1
                    _talvez_salvar()
            qtd = _escrever_parquet(
                registros,
                SCHEMA_MATERIA,
                params.dir_saida / "materias.parquet",
            )
            duracao = time.monotonic() - inicio
            log.info(
                "[coleta][senado] {n} materias baixadas em {t:.1f}s",
                n=qtd,
                t=duracao,
            )

        if "senadores" in params.tipos:
            inicio_sen = time.monotonic()
            registros_sen: list[dict[str, Any]] = []
            for legislatura in params.legislaturas or [56]:
                lista = coletar_senadores(legislatura, bucket=bucket, cli=cli)
                for s in lista:
                    norm = _normalizar_senador(s, legislatura)
                    if norm["id"] in checkpoint.senadores_baixados:
                        continue
                    registros_sen.append(norm)
                    checkpoint.senadores_baixados.add(norm["id"])
                    contador_req += 1
            qtd = _escrever_parquet(
                registros_sen,
                SCHEMA_SENADOR,
                params.dir_saida / "senadores.parquet",
            )
            duracao = time.monotonic() - inicio_sen
            log.info(
                "[coleta][senado] {n} senadores baixados em {t:.1f}s",
                n=qtd,
                t=duracao,
            )
            _talvez_salvar()

        if "votacoes" in params.tipos:
            registros_v: list[dict[str, Any]] = []
            for ano in anos:
                for item in coletar_votacoes(
                    ano,
                    max_itens=params.max_itens,
                    bucket=bucket,
                    cli=cli,
                ):
                    norm = _normalizar_votacao(item)
                    vid = norm["id"]
                    if vid in checkpoint.votacoes_baixadas:
                        continue
                    registros_v.append(norm)
                    checkpoint.votacoes_baixadas.add(vid)
                    contador_req += 1
                    _talvez_salvar()
            _escrever_parquet(
                registros_v,
                SCHEMA_VOTACAO,
                params.dir_saida / "votacoes_senado.parquet",
            )

        if "votos" in params.tipos:
            registros_voto: list[dict[str, Any]] = []
            for vid in list(checkpoint.votacoes_baixadas):
                votos = coletar_votos_de_votacao(vid, bucket=bucket, cli=cli)
                for v in votos:
                    norm = _normalizar_voto(vid, v)
                    chave = (vid, norm["senador_id"])
                    if chave in checkpoint.votos_baixados:
                        continue
                    registros_voto.append(norm)
                    checkpoint.votos_baixados.add(chave)
                    contador_req += 1
                    _talvez_salvar()
            _escrever_parquet(
                registros_voto,
                SCHEMA_VOTO,
                params.dir_saida / "votos_senado.parquet",
            )

        if "discursos" in params.tipos:
            registros_d: list[dict[str, Any]] = []
            for sid in list(checkpoint.senadores_baixados):
                ano_filtro = anos[0] if anos else None
                for item in coletar_discursos(
                    sid,
                    ano=ano_filtro,
                    max_itens=params.max_itens,
                    bucket=bucket,
                    cli=cli,
                ):
                    norm = _normalizar_discurso(item)
                    h_disc = norm["hash_conteudo"]
                    if h_disc and h_disc in checkpoint.discursos_baixados:
                        continue
                    registros_d.append(norm)
                    if h_disc:
                        checkpoint.discursos_baixados.add(h_disc)
                    contador_req += 1
                    _talvez_salvar()
            _escrever_parquet(
                registros_d,
                SCHEMA_DISCURSO,
                params.dir_saida / "discursos_senado.parquet",
            )

        _talvez_salvar(forcar=True)
        return checkpoint
    finally:
        cli.close()
