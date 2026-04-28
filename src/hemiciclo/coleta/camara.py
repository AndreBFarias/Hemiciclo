"""Coletor da API da Câmara dos Deputados (Dados Abertos v2).

Endpoints alvo (todos públicos do governo brasileiro -- I1):

- ``https://dadosabertos.camara.leg.br/api/v2/proposicoes``
- ``https://dadosabertos.camara.leg.br/api/v2/votacoes``
- ``https://dadosabertos.camara.leg.br/api/v2/votacoes/{id}/votos``
- ``https://dadosabertos.camara.leg.br/api/v2/deputados``
- ``https://dadosabertos.camara.leg.br/api/v2/deputados/{id}/discursos``

Para o teor RTF dos discursos, mantemos compatibilidade com o padrão
estabelecido no código R legado (``src/lib/rtf.R``) que decodifica
Base64 do endpoint legacy ``SitCamaraWS``. Esse fluxo fica em
``coletar_discursos_rtf`` (opcional, default desligado em S24).

Cada função de coleta:

1. Respeita o ``TokenBucket`` para rate limiting.
2. Aplica ``@retry_resiliente`` para resiliência.
3. Atualiza ``checkpoint`` em memória, sem escrever a cada item (o
   orquestrador chama :func:`salvar_checkpoint` a cada 50 requisições).
4. Yield item por item (Iterator), permitindo persistência incremental.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import polars as pl
from loguru import logger

from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.checkpoint import (
    CheckpointCamara,
    caminho_checkpoint,
    carregar_checkpoint,
    hash_params,
    salvar_checkpoint,
)
from hemiciclo.coleta.http import (
    cliente_http,
    raise_para_status,
    retry_resiliente,
)
from hemiciclo.coleta.rate_limit import TokenBucket

if TYPE_CHECKING:  # pragma: no cover
    pass

URL_BASE = "https://dadosabertos.camara.leg.br/api/v2"
"""Base da API Dados Abertos v2 da Câmara (público, governo BR -- I1)."""

URL_BASE_LEGACY = "https://www.camara.leg.br/SitCamaraWS"
"""Endpoint legacy SOAP/XML usado apenas para teor RTF de discursos."""

CHECKPOINT_INTERVALO = 50
"""Salva o checkpoint a cada N requisições bem-sucedidas."""


def ano_inicial_legislatura(legislatura: int) -> int:
    """Ano inicial canônico da legislatura na Câmara dos Deputados.

    Legislaturas seguem ciclo de 4 anos. A 50ª iniciou em 1995. A 57ª
    iniciou em 2023.
    """
    return 1995 + 4 * (legislatura - 50)


def _anos_da_legislatura(legislatura: int) -> list[int]:
    """Lista os 4 anos canônicos de uma legislatura (S24c).

    Legislaturas seguem ciclo de 4 anos a partir do ano inicial dado por
    :func:`ano_inicial_legislatura`. Exemplos:

    - Legislatura 57 -> ``[2023, 2024, 2025, 2026]``.
    - Legislatura 56 -> ``[2019, 2020, 2021, 2022]``.
    - Legislatura 50 -> ``[1995, 1996, 1997, 1998]`` (âncora histórica).

    Usado por :func:`coletar_proposicoes` para iterar todos os anos da
    legislatura quando o parâmetro ``ano`` não é fornecido pelo chamador,
    eliminando o viés de truncar para apenas o ano inicial.
    """
    inicio = ano_inicial_legislatura(legislatura)
    return [inicio + i for i in range(4)]


SCHEMA_PROPOSICAO: dict[str, pl.DataType] = {
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
"""Schema mínimo do Parquet de proposições (12 colunas, conforme spec)."""

SCHEMA_VOTACAO: dict[str, pl.DataType] = {
    "id": pl.Utf8(),
    "data": pl.Utf8(),
    "descricao": pl.Utf8(),
    "proposicao_id": pl.Int64(),
    "resultado": pl.Utf8(),
    "casa": pl.Utf8(),
}

SCHEMA_VOTO: dict[str, pl.DataType] = {
    "votacao_id": pl.Utf8(),
    "deputado_id": pl.Int64(),
    "voto": pl.Utf8(),
    "partido": pl.Utf8(),
    "uf": pl.Utf8(),
}

SCHEMA_DISCURSO: dict[str, pl.DataType] = {
    "id": pl.Utf8(),
    "deputado_id": pl.Int64(),
    "data": pl.Utf8(),
    "tipo": pl.Utf8(),
    "sumario": pl.Utf8(),
    "url_audio": pl.Utf8(),
    "url_video": pl.Utf8(),
    "transcricao": pl.Utf8(),
    "hash_conteudo": pl.Utf8(),
}

SCHEMA_DEPUTADO: dict[str, pl.DataType] = {
    "id": pl.Int64(),
    "nome": pl.Utf8(),
    "nome_eleitoral": pl.Utf8(),
    "partido": pl.Utf8(),
    "uf": pl.Utf8(),
    "legislatura": pl.Int64(),
    "email": pl.Utf8(),
}

SCHEMA_PROPOSICAO_DETALHE: dict[str, pl.DataType] = {
    "id": pl.Int64(),
    "casa": pl.Utf8(),
    "tema_oficial": pl.Utf8(),
    "autor_principal": pl.Utf8(),
    "status": pl.Utf8(),
    "url_inteiro_teor": pl.Utf8(),
    "enriquecido_em": pl.Utf8(),
}
"""Schema do parquet de enriquecimento (S24b): 4 campos preenchidos via
``GET /proposicoes/{id}`` mais ``id``/``casa`` para JOIN e
``enriquecido_em`` (ISO 8601) como auditoria."""


@retry_resiliente
def _baixar_pagina(
    cli: httpx.Client, url: str, params: dict[str, Any] | None = None
) -> tuple[dict[str, Any], httpx.Headers]:
    """Baixa uma página JSON com retry resiliente.

    Returns:
        ``(corpo_json, headers)``. Headers contém ``Link`` para paginação.
    """
    inicio = time.monotonic()
    resp = cli.get(url, params=params)
    raise_para_status(resp)
    duracao = time.monotonic() - inicio
    logger.info(
        "GET {url} -> {status} em {duracao:.2f}s",
        url=str(resp.request.url),
        status=resp.status_code,
        duracao=duracao,
    )
    return resp.json(), resp.headers


def _proxima_pagina(headers: httpx.Headers) -> str | None:
    """Extrai a URL ``rel="next"`` do header ``Link``, se presente.

    Formato esperado pelo padrão RFC 5988::

        Link: <https://...?pagina=2>; rel="next", <...>; rel="last"
    """
    link_raw = headers.get("Link") or headers.get("link")
    if not link_raw:
        return None
    link: str = str(link_raw)
    for parte_raw in link.split(","):
        parte = parte_raw.strip()
        if 'rel="next"' in parte or "rel=next" in parte:
            inicio = parte.find("<")
            fim = parte.find(">")
            if inicio != -1 and fim != -1:
                return parte[inicio + 1 : fim]
    return None


def _coletar_proposicoes_ano(
    legislatura: int,
    ano: int,
    max_itens: int | None,
    bucket: TokenBucket,
    cli: httpx.Client,
) -> Iterator[dict[str, Any]]:
    """Itera proposições de **um único ano** da legislatura.

    Helper privado extraído em S24c para que :func:`coletar_proposicoes`
    possa, no caminho ``ano is None``, iterar os 4 anos da legislatura
    chamando este helper com cliente e bucket compartilhados, evitando
    recursão na API pública.

    Args:
        legislatura: Número da legislatura (ex.: 57). Hoje só usado em
            logs futuros; a API ``/proposicoes`` filtra por ``ano``.
        ano: Ano de apresentação a baixar (obrigatório aqui).
        max_itens: Limite. ``None`` = sem limite.
        bucket: Token bucket gerenciado pelo chamador.
        cli: Cliente httpx gerenciado pelo chamador (não fecha aqui).

    Yields:
        Dict bruto da API por proposição.
    """
    del legislatura  # mantido na assinatura para clareza semântica e logs
    url: str | None = f"{URL_BASE}/proposicoes"
    params_iniciais: dict[str, Any] = {
        "ano": ano,
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "id",
    }
    params: dict[str, Any] | None = params_iniciais

    baixados = 0
    while url is not None:
        bucket.aguardar()
        corpo, headers = _baixar_pagina(cli, url, params=params)
        params = None  # próxima URL já carrega query string
        for item in corpo.get("dados", []):
            yield item
            baixados += 1
            if max_itens is not None and baixados >= max_itens:
                return
        url = _proxima_pagina(headers)


def coletar_proposicoes(
    legislatura: int,
    ano: int | None = None,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
    checkpoint: CheckpointCamara | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera proposições da legislatura, yield item por item.

    Quando ``ano`` é fornecido, baixa apenas esse ano (back-compat S24).
    Quando ``ano is None`` (default), itera os 4 anos da legislatura via
    :func:`_anos_da_legislatura` (S24c) -- elimina o viés de truncar para
    o ano inicial. ``max_itens`` é interpretado **globalmente** entre
    anos (não por ano).

    Quando ``checkpoint`` é fornecido, anos já marcados em
    ``checkpoint.anos_concluidos`` são pulados, e cada ano que termina
    sem interrupção (max_itens não atingido no meio) é registrado no
    set para retomada granular após ``kill -9``.

    Args:
        legislatura: Número da legislatura (ex.: 57).
        ano: Filtro opcional de ano. ``None`` aciona iteração 4 anos.
        max_itens: Limite total **somando os 4 anos**. ``None`` = sem limite.
        bucket: Token bucket compartilhado. Cria um default se ``None``.
        cli: Cliente httpx compartilhado. Cria um efêmero se ``None``.
        checkpoint: Estado opcional para pular anos já concluídos e
            registrar progresso por ano.

    Yields:
        Dict bruto da API por proposição.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        if ano is not None:
            yield from _coletar_proposicoes_ano(legislatura, ano, max_itens, bucket, cli)
            return

        # Caminho multi-ano: itera os 4 anos canônicos da legislatura.
        anos = _anos_da_legislatura(legislatura)
        baixados_total = 0
        for ano_iter in anos:
            if checkpoint is not None and (legislatura, ano_iter) in checkpoint.anos_concluidos:
                logger.info(
                    "[coleta] camara prop legislatura={l} ano={a} -- pulado (checkpoint)",
                    l=legislatura,
                    a=ano_iter,
                )
                continue

            limite_restante = None if max_itens is None else max(0, max_itens - baixados_total)
            if limite_restante == 0:
                break

            baixados_ano = 0
            interrompido = False
            for item in _coletar_proposicoes_ano(
                legislatura, ano_iter, limite_restante, bucket, cli
            ):
                yield item
                baixados_ano += 1
                baixados_total += 1
                if max_itens is not None and baixados_total >= max_itens:
                    # Não marca ano concluído -- pode ter sobrado conteúdo.
                    interrompido = True
                    logger.info(
                        "[coleta] camara prop legislatura={l} ano={a} "
                        "baixadas={n} (interrompido por max_itens)",
                        l=legislatura,
                        a=ano_iter,
                        n=baixados_ano,
                    )
                    return

            if not interrompido:
                logger.info(
                    "[coleta] camara prop legislatura={l} ano={a} baixadas={n}",
                    l=legislatura,
                    a=ano_iter,
                    n=baixados_ano,
                )
                if checkpoint is not None:
                    checkpoint.anos_concluidos.add((legislatura, ano_iter))
    finally:
        if fechar_cli:
            cli.close()


def coletar_votacoes(
    legislatura: int,
    data_inicio: date,
    data_fim: date,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera votações nominais no intervalo de datas, yield item por item.

    Args:
        legislatura: Legislatura alvo.
        data_inicio: Data inicial (inclusive).
        data_fim: Data final (inclusive).
        max_itens: Limite total.
        bucket: Token bucket compartilhado.
        cli: Cliente httpx compartilhado.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url: str | None = f"{URL_BASE}/votacoes"
        params: dict[str, Any] | None = {
            "idLegislatura": legislatura,
            "dataInicio": data_inicio.isoformat(),
            "dataFim": data_fim.isoformat(),
            "itens": 100,
            "ordem": "ASC",
            "ordenarPor": "dataHoraRegistro",
        }
        baixados = 0
        while url is not None:
            bucket.aguardar()
            corpo, headers = _baixar_pagina(cli, url, params=params)
            params = None
            for item in corpo.get("dados", []):
                yield item
                baixados += 1
                if max_itens is not None and baixados >= max_itens:
                    return
            url = _proxima_pagina(headers)
    finally:
        if fechar_cli:
            cli.close()


def coletar_votos_de_votacao(
    votacao_id: str,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Baixa todos os votos individuais de uma votação.

    Returns:
        Lista de dicts ``{deputado_id, voto, partido, uf}``.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url = f"{URL_BASE}/votacoes/{votacao_id}/votos"
        bucket.aguardar()
        corpo, _ = _baixar_pagina(cli, url, params={"itens": 1000})
        return [dict(v) for v in corpo.get("dados", [])]
    finally:
        if fechar_cli:
            cli.close()


def coletar_discursos(
    legislatura: int,
    data_inicio: date,
    data_fim: date,
    max_itens: int | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> Iterator[dict[str, Any]]:
    """Itera discursos do plenário no intervalo de datas.

    Usa o endpoint ``/deputados/{id}/discursos`` indiretamente: primeiro
    lista deputados ativos da legislatura, depois pagina discursos por
    deputado. Para teor RTF (Base64), o orquestrador pode chamar o
    endpoint legacy SitCamaraWS posteriormente.
    """
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        deputados = list(coletar_cadastro_deputados(legislatura, bucket=bucket, cli=cli))
        baixados = 0
        for dep in deputados:
            if max_itens is not None and baixados >= max_itens:
                return
            dep_id = dep.get("id")
            if dep_id is None:
                continue
            url: str | None = f"{URL_BASE}/deputados/{dep_id}/discursos"
            params: dict[str, Any] | None = {
                "dataInicio": data_inicio.isoformat(),
                "dataFim": data_fim.isoformat(),
                "itens": 100,
                "ordem": "ASC",
                "ordenarPor": "dataHoraInicio",
            }
            while url is not None:
                bucket.aguardar()
                corpo, headers = _baixar_pagina(cli, url, params=params)
                params = None
                for item in corpo.get("dados", []):
                    item_completo = dict(item)
                    item_completo["deputado_id"] = dep_id
                    yield item_completo
                    baixados += 1
                    if max_itens is not None and baixados >= max_itens:
                        return
                url = _proxima_pagina(headers)
    finally:
        if fechar_cli:
            cli.close()


def coletar_cadastro_deputados(
    legislatura: int,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Baixa cadastro de deputados ativos numa legislatura."""
    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    try:
        url: str | None = f"{URL_BASE}/deputados"
        params: dict[str, Any] | None = {
            "idLegislatura": legislatura,
            "itens": 100,
            "ordem": "ASC",
            "ordenarPor": "nome",
        }
        deputados: list[dict[str, Any]] = []
        while url is not None:
            bucket.aguardar()
            corpo, headers = _baixar_pagina(cli, url, params=params)
            params = None
            deputados.extend(dict(d) for d in corpo.get("dados", []))
            url = _proxima_pagina(headers)
        return deputados
    finally:
        if fechar_cli:
            cli.close()


def _resolver_autor_principal(
    uri_autores: str,
    bucket: TokenBucket,
    cli: httpx.Client,
) -> str | None:
    """Resolve nome do primeiro autor de uma proposição (S24b).

    Faz ``GET <uri_autores>`` (URL absoluta vinda do detalhe) e extrai o
    campo ``nome`` do primeiro item da lista ``dados``. Em qualquer falha
    (rede, payload malformado, lista vazia) retorna ``None`` -- nunca
    interrompe o pipeline de enriquecimento.

    Returns:
        Nome do primeiro autor, ou ``None`` em qualquer falha.
    """
    try:
        bucket.aguardar()
        corpo, _ = _baixar_pagina(cli, uri_autores)
        autores = corpo.get("dados") or []
        if not autores:
            return None
        primeiro = autores[0]
        if not isinstance(primeiro, dict):
            return None
        nome = primeiro.get("nome")
        return str(nome) if nome else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Falha ao resolver autor de {uri}: {e}", uri=uri_autores, e=exc)
        return None


def enriquecer_proposicao(
    prop_id: int,
    home: Path | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
    autores_resolvidos: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Busca detalhe completo de uma proposição da Câmara (S24b).

    Faz ``GET /proposicoes/{id}``, normaliza o payload e devolve dict com
    4 campos preenchidos (mais ``id``, ``casa`` e ``enriquecido_em`` para
    auditoria/JOIN). Defaults ``None`` quando o campo está ausente -- nunca
    string vazia (lição S27.1).

    Estratégia em 5 passos:

    1. Consulta cache local em ``<home>/cache/proposicoes/camara-{id}.json``.
    2. Cache miss: ``GET`` na API com retry resiliente.
    3. Resolve autor principal via ``uriAutores`` (chamada extra opcional;
       ``None`` em falha).
    4. Persiste payload bruto em cache para reuso entre sessões.
    5. Retorna dict normalizado com 7 chaves.

    Args:
        prop_id: ID inteiro da proposição na Câmara.
        home: Raiz do Hemiciclo (``~/hemiciclo``). Se ``None``, cache é
            ignorado (modo só-API útil em testes).
        bucket: ``TokenBucket`` compartilhado para rate limiting global.
        cli: Cliente ``httpx`` compartilhado (importante para reusar
            conexões keep-alive ao iterar muitas proposições).
        autores_resolvidos: Cache em memória ``{uri_autores: nome|None}``
            para evitar refazer ``GET <uriAutores>`` quando vários PLs
            partilham o mesmo autor.

    Returns:
        Dict com chaves: ``id``, ``casa``, ``tema_oficial``,
        ``autor_principal``, ``status``, ``url_inteiro_teor``,
        ``enriquecido_em``.
    """
    from hemiciclo.etl.cache import (
        carregar_cache_detalhe_proposicao,
        salvar_cache_detalhe_proposicao,
    )

    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    if autores_resolvidos is None:
        autores_resolvidos = {}

    try:
        payload: dict[str, Any] | None = None
        if home is not None:
            payload = carregar_cache_detalhe_proposicao(home, "camara", prop_id)

        if payload is None:
            url = f"{URL_BASE}/proposicoes/{prop_id}"
            try:
                bucket.aguardar()
                corpo, _ = _baixar_pagina(cli, url)
                bruto = corpo.get("dados") or {}
                payload = bruto if isinstance(bruto, dict) else {}
                if home is not None:
                    salvar_cache_detalhe_proposicao(payload, home, "camara", prop_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.warning("Detalhe ausente para proposição {id} (404)", id=prop_id)
                    payload = {}
                else:
                    raise

        # Resolve autor principal (chamada extra opcional).
        autor: str | None = None
        uri_autores_raw = payload.get("uriAutores")
        uri_autores = str(uri_autores_raw) if uri_autores_raw else ""
        if uri_autores:
            if uri_autores in autores_resolvidos:
                autor = autores_resolvidos[uri_autores]
            else:
                autor = _resolver_autor_principal(uri_autores, bucket=bucket, cli=cli)
                autores_resolvidos[uri_autores] = autor

        status_obj = payload.get("statusProposicao") or {}
        status_val: str | None = None
        if isinstance(status_obj, dict):
            descr = status_obj.get("descricaoSituacao")
            status_val = str(descr) if descr else None

        tema = payload.get("temaOficial")
        url_teor = payload.get("urlInteiroTeor")

        return {
            "id": prop_id,
            "casa": "camara",
            "tema_oficial": str(tema) if tema else None,
            "autor_principal": autor,
            "status": status_val,
            "url_inteiro_teor": str(url_teor) if url_teor else None,
            "enriquecido_em": datetime.now(UTC).isoformat(),
        }
    finally:
        if fechar_cli:
            cli.close()


def _normalizar_proposicao(item: dict[str, Any]) -> dict[str, Any]:
    """Achata a estrutura aninhada da API em um dict plano com 12 colunas."""
    return {
        "id": int(item.get("id", 0)),
        "sigla": str(item.get("siglaTipo", "")),
        "numero": int(item.get("numero", 0)),
        "ano": int(item.get("ano", 0)),
        "ementa": str(item.get("ementa", "")),
        "tema_oficial": str(item.get("temaOficial", "") or ""),
        "autor_principal": str(item.get("autorPrincipal", "") or ""),
        "data_apresentacao": str(item.get("dataApresentacao", "") or ""),
        "status": str((item.get("statusProposicao") or {}).get("descricaoSituacao", "")),
        "url_inteiro_teor": str(item.get("urlInteiroTeor", "") or ""),
        "casa": "camara",
        "hash_conteudo": _hash_texto(str(item.get("ementa", ""))),
    }


def _normalizar_votacao(item: dict[str, Any]) -> dict[str, Any]:
    """Achata votação da Câmara em 6 colunas (S24 + S27.1).

    ``proposicao_id`` é extraído do objeto aninhado retornado pela API real
    -- na Câmara dos Deputados o campo é ``proposicao_`` (com sufixo
    underscore, convenção da serialização v2). Aceita também
    ``proposicaoPrincipal_`` como fallback observado em alguns endpoints
    derivados.

    Quando a API não retorna proposição principal (votação de requerimento
    interno, parecer, etc.), o campo é ``None`` -- traduz para NULL no
    parquet e na tabela DuckDB. **Nunca usar 0** como sentinela: 0 é um
    BIGINT válido e quebra o JOIN do classificador C1.
    """
    proposicao = item.get("proposicao_") or item.get("proposicaoPrincipal_")
    proposicao_id: int | None = None
    if isinstance(proposicao, dict):
        bruto = proposicao.get("id")
        if isinstance(bruto, int):
            proposicao_id = bruto
        elif isinstance(bruto, str) and bruto.strip().isdigit():
            proposicao_id = int(bruto)
    return {
        "id": str(item.get("id", "")),
        "data": str(item.get("data", "") or item.get("dataHoraRegistro", "")),
        "descricao": str(item.get("descricao", "")),
        "proposicao_id": proposicao_id,
        "resultado": str(item.get("resumo", "") or item.get("descricaoResultado", "")),
        "casa": "camara",
    }


def _normalizar_voto(votacao_id: str, item: dict[str, Any]) -> dict[str, Any]:
    deputado = item.get("deputado_") or item.get("deputado") or {}
    return {
        "votacao_id": votacao_id,
        "deputado_id": int(deputado.get("id", 0)) if isinstance(deputado, dict) else 0,
        "voto": str(item.get("tipoVoto", "") or item.get("voto", "")),
        "partido": str(deputado.get("siglaPartido", "")) if isinstance(deputado, dict) else "",
        "uf": str(deputado.get("siglaUf", "")) if isinstance(deputado, dict) else "",
    }


def _normalizar_discurso(item: dict[str, Any]) -> dict[str, Any]:
    transcricao = str(item.get("transcricao", "") or "")
    return {
        "id": str(item.get("id", "") or item.get("dataHoraInicio", "")),
        "deputado_id": int(item.get("deputado_id", 0)),
        "data": str(item.get("dataHoraInicio", "") or ""),
        "tipo": str(item.get("tipoDiscurso", "") or ""),
        "sumario": str(item.get("sumario", "") or ""),
        "url_audio": str(item.get("urlAudio", "") or ""),
        "url_video": str(item.get("urlVideo", "") or ""),
        "transcricao": transcricao,
        "hash_conteudo": _hash_texto(transcricao),
    }


def _normalizar_deputado(item: dict[str, Any], legislatura: int) -> dict[str, Any]:
    return {
        "id": int(item.get("id", 0)),
        "nome": str(item.get("nome", "")),
        "nome_eleitoral": str(item.get("nomeEleitoral", "") or item.get("nome", "")),
        "partido": str(item.get("siglaPartido", "")),
        "uf": str(item.get("siglaUf", "")),
        "legislatura": legislatura,
        "email": str(item.get("email", "") or ""),
    }


def _hash_texto(texto: str) -> str:
    """SHA256 dos primeiros 8 chars (suficiente para deduplicação local)."""
    import hashlib

    if not texto:
        return ""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _escrever_parquet(
    registros: list[dict[str, Any]],
    schema: dict[str, pl.DataType],
    arquivo: Path,
) -> int:
    """Escreve lista de dicts como Parquet com schema explícito.

    Returns:
        Número de linhas escritas.
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(schema=schema) if not registros else pl.DataFrame(registros, schema=schema)
    df.write_parquet(arquivo)
    return df.height


def executar_coleta(
    params: ParametrosColeta,
    home: Path,
    bucket: TokenBucket | None = None,
) -> CheckpointCamara:
    """Orquestra a coleta inteira respeitando checkpoint resumível.

    Args:
        params: Parâmetros validados da coleta.
        home: Diretório raiz do Hemiciclo (para localizar checkpoint).
        bucket: Token bucket. Cria default se ``None``.

    Returns:
        Checkpoint final atualizado (também persistido no disco).
    """
    if bucket is None:
        bucket = TokenBucket()

    h = hash_params(params.legislaturas, list(params.tipos))
    cp_path = caminho_checkpoint(home, h)
    checkpoint = carregar_checkpoint(cp_path)
    if checkpoint is None:
        checkpoint = CheckpointCamara(
            iniciado_em=datetime.now(UTC),
            atualizado_em=datetime.now(UTC),
            legislaturas=list(params.legislaturas),
            tipos=list(params.tipos),
        )
        logger.info("Checkpoint novo criado em {p}", p=cp_path)
    else:
        logger.info(
            "Checkpoint existente carregado: {n} itens ja baixados",
            n=checkpoint.total_baixado(),
        )

    params.dir_saida.mkdir(parents=True, exist_ok=True)
    contador_req = 0

    def _talvez_salvar(forcar: bool = False) -> None:
        nonlocal contador_req
        if forcar or contador_req >= CHECKPOINT_INTERVALO:
            checkpoint.atualizado_em = datetime.now(UTC)
            salvar_checkpoint(checkpoint, cp_path)
            logger.debug("Checkpoint salvo em {p}", p=cp_path)
            contador_req = 0

    log = logger.bind(coleta="camara", legislaturas=params.legislaturas)

    cli = cliente_http()
    try:
        for legislatura in params.legislaturas:
            inicio_leg = time.monotonic()

            if "proposicoes" in params.tipos:
                registros: list[dict[str, Any]] = []
                ano = params.data_inicio.year if params.data_inicio else None
                for item in coletar_proposicoes(
                    legislatura,
                    ano=ano,
                    max_itens=params.max_itens,
                    bucket=bucket,
                    cli=cli,
                    checkpoint=checkpoint,
                ):
                    item_id = int(item.get("id", 0))
                    if item_id in checkpoint.proposicoes_baixadas:
                        continue
                    registros.append(_normalizar_proposicao(item))
                    checkpoint.proposicoes_baixadas.add(item_id)
                    contador_req += 1
                    _talvez_salvar()
                qtd = _escrever_parquet(
                    registros,
                    SCHEMA_PROPOSICAO,
                    params.dir_saida / "proposicoes.parquet",
                )
                duracao = time.monotonic() - inicio_leg
                log.info(
                    "[coleta][camara] {n} proposicoes baixadas em {t:.1f}s",
                    n=qtd,
                    t=duracao,
                )

            if "proposicoes" in params.tipos and params.enriquecer_proposicoes:
                inicio_enr = time.monotonic()
                pendentes = checkpoint.proposicoes_baixadas - checkpoint.proposicoes_enriquecidas
                registros_det: list[dict[str, Any]] = []
                autores_resolvidos: dict[str, str | None] = {}
                erros_enr = 0
                for prop_id in sorted(pendentes):
                    try:
                        det = enriquecer_proposicao(
                            prop_id,
                            home=home,
                            bucket=bucket,
                            cli=cli,
                            autores_resolvidos=autores_resolvidos,
                        )
                        registros_det.append(det)
                        checkpoint.proposicoes_enriquecidas.add(prop_id)
                        contador_req += 1
                        _talvez_salvar()
                    except (httpx.HTTPError, ValueError) as exc:
                        erros_enr += 1
                        codigo = getattr(getattr(exc, "response", None), "status_code", None)
                        checkpoint.erros.append(
                            {
                                "url": f"{URL_BASE}/proposicoes/{prop_id}",
                                "codigo": codigo,
                                "mensagem": str(exc),
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        )
                qtd_det = _escrever_parquet(
                    registros_det,
                    SCHEMA_PROPOSICAO_DETALHE,
                    params.dir_saida / "proposicoes_detalhe.parquet",
                )
                duracao_enr = time.monotonic() - inicio_enr
                log.info(
                    "[coleta][camara] {n} proposicoes enriquecidas em {t:.1f}s ({e} erros)",
                    n=qtd_det,
                    t=duracao_enr,
                    e=erros_enr,
                )
                _talvez_salvar(forcar=True)

            if "deputados" in params.tipos:
                inicio = time.monotonic()
                lista = coletar_cadastro_deputados(legislatura, bucket=bucket, cli=cli)
                registros_dep = [_normalizar_deputado(d, legislatura) for d in lista]
                for d in lista:
                    checkpoint.deputados_baixados.add(int(d.get("id", 0)))
                    contador_req += 1
                qtd = _escrever_parquet(
                    registros_dep,
                    SCHEMA_DEPUTADO,
                    params.dir_saida / "deputados.parquet",
                )
                duracao = time.monotonic() - inicio
                log.info(
                    "[coleta][camara] {n} deputados baixados em {t:.1f}s",
                    n=qtd,
                    t=duracao,
                )
                _talvez_salvar()

            if "votacoes" in params.tipos:
                if params.data_inicio is None or params.data_fim is None:
                    log.warning(
                        "votacoes requer data_inicio e data_fim; pulando legislatura {l}",
                        l=legislatura,
                    )
                else:
                    registros_v: list[dict[str, Any]] = []
                    for item in coletar_votacoes(
                        legislatura,
                        params.data_inicio,
                        params.data_fim,
                        max_itens=params.max_itens,
                        bucket=bucket,
                        cli=cli,
                    ):
                        vid = str(item.get("id", ""))
                        if vid in checkpoint.votacoes_baixadas:
                            continue
                        registros_v.append(_normalizar_votacao(item))
                        checkpoint.votacoes_baixadas.add(vid)
                        contador_req += 1
                        _talvez_salvar()
                    _escrever_parquet(
                        registros_v,
                        SCHEMA_VOTACAO,
                        params.dir_saida / "votacoes.parquet",
                    )

            if "votos" in params.tipos:
                registros_voto: list[dict[str, Any]] = []
                for vid in list(checkpoint.votacoes_baixadas):
                    votos = coletar_votos_de_votacao(vid, bucket=bucket, cli=cli)
                    for v in votos:
                        norm = _normalizar_voto(vid, v)
                        chave = (vid, norm["deputado_id"])
                        if chave in checkpoint.votos_baixados:
                            continue
                        registros_voto.append(norm)
                        checkpoint.votos_baixados.add(chave)
                        contador_req += 1
                        _talvez_salvar()
                _escrever_parquet(
                    registros_voto,
                    SCHEMA_VOTO,
                    params.dir_saida / "votos.parquet",
                )

            if "discursos" in params.tipos:
                if params.data_inicio is None or params.data_fim is None:
                    log.warning(
                        "discursos requer data_inicio e data_fim; pulando legislatura {l}",
                        l=legislatura,
                    )
                else:
                    registros_d: list[dict[str, Any]] = []
                    for item in coletar_discursos(
                        legislatura,
                        params.data_inicio,
                        params.data_fim,
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
                        params.dir_saida / "discursos.parquet",
                    )

        _talvez_salvar(forcar=True)
        return checkpoint
    finally:
        cli.close()
