"""Testes unit do coletor da Câmara via respx mocks (sem rede real)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from hemiciclo.coleta.camara import (
    URL_BASE,
    _anos_da_legislatura,
    coletar_cadastro_deputados,
    coletar_proposicoes,
    coletar_votacoes,
    coletar_votos_de_votacao,
)
from hemiciclo.coleta.checkpoint import CheckpointCamara
from hemiciclo.coleta.rate_limit import TokenBucket


def _bucket_rapido() -> TokenBucket:
    """Bucket com taxa altíssima -- evita esperar nos testes."""
    return TokenBucket(taxa=10000.0, capacidade=10000)


@respx.mock
def test_coletar_proposicoes_caminho_feliz() -> None:
    """Coleta uma página de proposições e retorna itens em ordem."""
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"id": 1, "siglaTipo": "PL", "numero": 100, "ano": 2023},
                    {"id": 2, "siglaTipo": "PL", "numero": 200, "ano": 2023},
                ]
            },
        )
    )
    # ``ano=2023`` explícito mantém escopo single-year do teste original.
    # O caminho multi-ano (ano=None) é coberto pelos testes novos da S24c.
    itens = list(coletar_proposicoes(57, ano=2023, bucket=_bucket_rapido()))
    assert len(itens) == 2
    assert itens[0]["id"] == 1
    assert itens[1]["id"] == 2


@respx.mock
def test_coletar_proposicoes_paginacao_link_header() -> None:
    """Paginação via header ``Link: <...>; rel="next"`` é seguida."""
    pagina2 = "https://exemplo.gov.br/api/v2/proposicoes?pagina=2"
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={"dados": [{"id": 1, "siglaTipo": "PL", "numero": 1, "ano": 2024}]},
            headers={"Link": f'<{pagina2}>; rel="next"'},
        )
    )
    respx.get(pagina2).mock(
        return_value=httpx.Response(
            200,
            json={"dados": [{"id": 2, "siglaTipo": "PL", "numero": 2, "ano": 2024}]},
        )
    )
    # ``ano=2024`` explícito: este teste exercita paginação intra-ano.
    itens = list(coletar_proposicoes(57, ano=2024, bucket=_bucket_rapido()))
    assert len(itens) == 2
    assert [i["id"] for i in itens] == [1, 2]


@respx.mock
def test_coletar_votacoes_intervalo_de_data() -> None:
    """Coletar votações respeita intervalo passado."""
    rota = respx.get(f"{URL_BASE}/votacoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"id": "abc-1", "data": "2023-02-15", "descricao": "PL 1"},
                    {"id": "abc-2", "data": "2023-02-20", "descricao": "PL 2"},
                ]
            },
        )
    )
    itens = list(
        coletar_votacoes(
            57,
            data_inicio=date(2023, 2, 1),
            data_fim=date(2023, 2, 28),
            bucket=_bucket_rapido(),
        )
    )
    assert len(itens) == 2
    # Confirma que os params de data foram enviados:
    chamada = rota.calls[0].request
    assert "dataInicio=2023-02-01" in str(chamada.url)
    assert "dataFim=2023-02-28" in str(chamada.url)


@respx.mock
def test_coletar_votos_de_votacao() -> None:
    """Coletar votos individuais de uma votação retorna lista de dicts."""
    respx.get(f"{URL_BASE}/votacoes/abc-1/votos").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"deputado_": {"id": 100, "siglaPartido": "X"}, "tipoVoto": "Sim"},
                    {"deputado_": {"id": 101, "siglaPartido": "Y"}, "tipoVoto": "Nao"},
                ]
            },
        )
    )
    votos = coletar_votos_de_votacao("abc-1", bucket=_bucket_rapido())
    assert len(votos) == 2
    assert votos[0]["tipoVoto"] == "Sim"


@respx.mock
def test_coletar_cadastro_deputados() -> None:
    """Cadastro de deputados retorna lista achatada."""
    respx.get(f"{URL_BASE}/deputados").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"id": 100, "nome": "Fulano", "siglaPartido": "P", "siglaUf": "SP"},
                    {"id": 101, "nome": "Beltrano", "siglaPartido": "Q", "siglaUf": "RJ"},
                ]
            },
        )
    )
    deputados = coletar_cadastro_deputados(57, bucket=_bucket_rapido())
    assert len(deputados) == 2
    assert deputados[0]["nome"] == "Fulano"


@respx.mock
def test_503_retry_e_sucesso() -> None:
    """503 dispara retry interno; eventualmente sucede."""
    respx.get(f"{URL_BASE}/proposicoes").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"dados": [{"id": 9, "siglaTipo": "PL"}]}),
        ]
    )
    # ``ano=2023`` explícito: foco do teste é retry 503->200 num único ano.
    itens = list(coletar_proposicoes(57, ano=2023, bucket=_bucket_rapido()))
    assert len(itens) == 1
    assert itens[0]["id"] == 9


@respx.mock
def test_404_propaga_erro() -> None:
    """404 propaga ``HTTPStatusError`` sem retry."""
    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(404, text="nao encontrado")
    )
    with pytest.raises(httpx.HTTPStatusError):
        list(coletar_proposicoes(99, bucket=_bucket_rapido()))
    # Apenas 1 chamada (sem retry):
    assert rota.call_count == 1


def test_normalizar_votacao_extrai_proposicao_id() -> None:
    """``_normalizar_votacao`` (S27.1) lê ``proposicao_.id`` da API real da Câmara."""
    from hemiciclo.coleta.camara import _normalizar_votacao

    norm = _normalizar_votacao(
        {
            "id": "abc-1",
            "data": "2024-03-10",
            "descricao": "PL 1904/2024",
            "proposicao_": {"id": 91234, "siglaTipo": "PL"},
            "descricaoResultado": "Aprovado",
        }
    )
    assert norm["proposicao_id"] == 91234
    assert norm["casa"] == "camara"


def test_normalizar_votacao_sem_proposicao_principal_retorna_none() -> None:
    """Votação sem proposição principal (req. interno) -> ``proposicao_id = None``."""
    from hemiciclo.coleta.camara import _normalizar_votacao

    norm = _normalizar_votacao(
        {
            "id": "abc-2",
            "data": "2024-03-11",
            "descricao": "Requerimento",
            "descricaoResultado": "Aprovado",
        }
    )
    # `None` é o sentinel correto para NULL no parquet/DB; 0 quebraria o JOIN do C1.
    assert norm["proposicao_id"] is None


def test_normalizar_votacao_aceita_fallback_proposicao_principal() -> None:
    """Algumas variantes da API retornam ``proposicaoPrincipal_`` -- aceita também."""
    from hemiciclo.coleta.camara import _normalizar_votacao

    norm = _normalizar_votacao(
        {
            "id": "abc-3",
            "proposicaoPrincipal_": {"id": "55555"},  # API às vezes retorna string
            "descricaoResultado": "Aprovado",
        }
    )
    assert norm["proposicao_id"] == 55555


@respx.mock
def test_max_itens_respeitado() -> None:
    """``max_itens=2`` interrompe a iteração mesmo com mais itens disponíveis."""
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"id": 1, "siglaTipo": "PL"},
                    {"id": 2, "siglaTipo": "PL"},
                    {"id": 3, "siglaTipo": "PL"},
                    {"id": 4, "siglaTipo": "PL"},
                ]
            },
        )
    )
    itens = list(coletar_proposicoes(57, ano=2023, max_itens=2, bucket=_bucket_rapido()))
    assert len(itens) == 2
    assert [i["id"] for i in itens] == [1, 2]


# ---------------------------------------------------------------------------
# S24c -- coletor itera os 4 anos da legislatura quando ano=None.
# ---------------------------------------------------------------------------


def test_anos_da_legislatura_l57_retorna_2023_2026() -> None:
    """L57 cobre 2023, 2024, 2025, 2026 (legislatura vigente em 2026)."""
    assert _anos_da_legislatura(57) == [2023, 2024, 2025, 2026]


def test_anos_da_legislatura_l56_retorna_2019_2022() -> None:
    """L56 cobre o ciclo Bolsonaro completo (2019-2022)."""
    assert _anos_da_legislatura(56) == [2019, 2020, 2021, 2022]


def test_anos_da_legislatura_l50_retorna_1995_1998() -> None:
    """L50 é a âncora histórica (1995-1998), conforme docstring de
    ``ano_inicial_legislatura``."""
    assert _anos_da_legislatura(50) == [1995, 1996, 1997, 1998]


@respx.mock
def test_coletar_proposicoes_ano_none_itera_4_anos() -> None:
    """Com ``ano=None``, faz GETs para cada um dos 4 anos da legislatura.

    Mocka o endpoint com 1 item por ano (4 itens totais) e verifica:
    1. Foram feitas exatamente 4 chamadas HTTP (uma por ano).
    2. Cada chamada carregou o ``ano`` correto na query string.
    3. Os 4 itens chegam ao consumidor em ordem dos anos.
    """
    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        side_effect=[
            httpx.Response(200, json={"dados": [{"id": 1, "siglaTipo": "PL", "ano": 2023}]}),
            httpx.Response(200, json={"dados": [{"id": 2, "siglaTipo": "PL", "ano": 2024}]}),
            httpx.Response(200, json={"dados": [{"id": 3, "siglaTipo": "PL", "ano": 2025}]}),
            httpx.Response(200, json={"dados": [{"id": 4, "siglaTipo": "PL", "ano": 2026}]}),
        ]
    )
    itens = list(coletar_proposicoes(57, bucket=_bucket_rapido()))
    assert len(itens) == 4
    assert [i["id"] for i in itens] == [1, 2, 3, 4]
    assert rota.call_count == 4
    anos_consultados = [dict(httpx.URL(str(c.request.url)).params).get("ano") for c in rota.calls]
    assert anos_consultados == ["2023", "2024", "2025", "2026"]


@respx.mock
def test_coletar_proposicoes_ano_explicito_nao_itera() -> None:
    """``ano=2024`` faz exatamente 1 GET (sem iterar os outros anos)."""
    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200, json={"dados": [{"id": 99, "siglaTipo": "PL", "ano": 2024}]}
        )
    )
    itens = list(coletar_proposicoes(57, ano=2024, bucket=_bucket_rapido()))
    assert len(itens) == 1
    assert rota.call_count == 1
    chamada = rota.calls[0].request
    assert "ano=2024" in str(chamada.url)


@respx.mock
def test_coletar_proposicoes_max_itens_global_atravessa_anos() -> None:
    """``max_itens=5`` é honrado **somando** os 4 anos, não por ano.

    Mock fornece 3 itens por ano (12 totais). Esperado: para no item 5
    (segundo item do segundo ano). Apenas 2 chamadas HTTP -- ano 2023
    inteiro (3 itens) + ano 2024 parcial (2 itens visto antes do limite).
    """

    def _payload(ids: list[int]) -> httpx.Response:
        return httpx.Response(200, json={"dados": [{"id": i, "siglaTipo": "PL"} for i in ids]})

    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        side_effect=[
            _payload([1, 2, 3]),
            _payload([4, 5, 6]),
            _payload([7, 8, 9]),
            _payload([10, 11, 12]),
        ]
    )
    itens = list(coletar_proposicoes(57, max_itens=5, bucket=_bucket_rapido()))
    assert len(itens) == 5
    assert [i["id"] for i in itens] == [1, 2, 3, 4, 5]
    # Apenas 2 chamadas: ano 2023 (3 itens) + ano 2024 (parcial, 2 itens).
    assert rota.call_count == 2


@respx.mock
def test_coletar_proposicoes_pula_ano_marcado_no_checkpoint() -> None:
    """Ano em ``checkpoint.anos_concluidos`` é pulado; demais são iterados."""
    from datetime import UTC, datetime

    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        side_effect=[
            httpx.Response(200, json={"dados": [{"id": 10, "siglaTipo": "PL"}]}),
            httpx.Response(200, json={"dados": [{"id": 20, "siglaTipo": "PL"}]}),
            httpx.Response(200, json={"dados": [{"id": 30, "siglaTipo": "PL"}]}),
        ]
    )
    cp = CheckpointCamara(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        legislaturas=[57],
        tipos=["proposicoes"],
        anos_concluidos={(57, 2023)},  # ja baixado, deve pular
    )
    itens = list(coletar_proposicoes(57, bucket=_bucket_rapido(), checkpoint=cp))
    # 3 chamadas (2024, 2025, 2026); ano 2023 pulado.
    assert rota.call_count == 3
    assert [i["id"] for i in itens] == [10, 20, 30]
    anos_consultados = [dict(httpx.URL(str(c.request.url)).params).get("ano") for c in rota.calls]
    assert anos_consultados == ["2024", "2025", "2026"]
    # Ao final, todos os 4 anos devem estar marcados (3 novos + 1 pre-existente).
    assert cp.anos_concluidos == {
        (57, 2023),
        (57, 2024),
        (57, 2025),
        (57, 2026),
    }
