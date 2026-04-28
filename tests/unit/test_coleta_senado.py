"""Testes unit do coletor do Senado via respx mocks (sem rede real)."""

from __future__ import annotations

import httpx
import pytest
import respx

from hemiciclo.coleta.rate_limit import TokenBucket
from hemiciclo.coleta.senado import (
    URL_BASE,
    coletar_discursos,
    coletar_materias,
    coletar_senadores,
    coletar_votacoes,
    coletar_votos_de_votacao,
)


def _bucket_rapido() -> TokenBucket:
    """Bucket com taxa altíssima -- evita esperar nos testes."""
    return TokenBucket(taxa=10000.0, capacidade=10000)


@respx.mock
def test_coletar_senadores_caminho_feliz() -> None:
    """Coleta lista de senadores ativos numa legislatura."""
    payload = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "5012",
                            "NomeParlamentar": "Fulano da Silva",
                            "SiglaPartidoParlamentar": "PT",
                            "UfParlamentar": "BA",
                        }
                    },
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "5013",
                            "NomeParlamentar": "Beltrano",
                            "SiglaPartidoParlamentar": "PSDB",
                            "UfParlamentar": "SP",
                        }
                    },
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/senador/lista/legislatura/56").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    senadores = coletar_senadores(56, bucket=_bucket_rapido())
    assert len(senadores) == 2
    assert senadores[0]["IdentificacaoParlamentar"]["NomeParlamentar"] == "Fulano da Silva"


@respx.mock
def test_coletar_materias_paginacao() -> None:
    """Coleta página de matérias do Senado por ano."""
    payload = {
        "PesquisaBasicaMateria": {
            "Materias": {
                "Materia": [
                    {
                        "IdentificacaoMateria": {
                            "CodigoMateria": "100",
                            "SiglaSubtipoMateria": "PLS",
                            "NumeroMateria": "10",
                            "AnoMateria": "2024",
                        },
                        "EmentaMateria": "Ementa simulada A",
                    },
                    {
                        "IdentificacaoMateria": {
                            "CodigoMateria": "101",
                            "SiglaSubtipoMateria": "PLS",
                            "NumeroMateria": "11",
                            "AnoMateria": "2024",
                        },
                        "EmentaMateria": "Ementa simulada B",
                    },
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    itens = list(coletar_materias(2024, bucket=_bucket_rapido()))
    assert len(itens) == 2
    ementas = [i["EmentaMateria"] for i in itens]
    assert "Ementa simulada A" in ementas


@respx.mock
def test_coletar_votacoes_intervalo_de_ano() -> None:
    """Coleta lista de votações do plenário num ano."""
    payload = {
        "ListaVotacoes": {
            "Votacoes": {
                "Votacao": [
                    {
                        "CodigoSessaoVotacao": "9001",
                        "DataSessao": "2024-03-15",
                        "DescricaoVotacao": "PLS 100/2024",
                    },
                    {
                        "CodigoSessaoVotacao": "9002",
                        "DataSessao": "2024-03-22",
                        "DescricaoVotacao": "PLS 101/2024",
                    },
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/plenario/lista/votacao/2024").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    itens = list(coletar_votacoes(2024, bucket=_bucket_rapido()))
    assert len(itens) == 2
    assert itens[0]["CodigoSessaoVotacao"] == "9001"


@respx.mock
def test_coletar_votos_de_votacao() -> None:
    """Coleta votos individuais de uma votação retorna lista de dicts."""
    payload = {
        "VotacaoPlenario": {
            "Votos": {
                "VotoParlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "5012",
                            "SiglaPartidoParlamentar": "PT",
                            "UfParlamentar": "BA",
                        },
                        "DescricaoVoto": "Sim",
                    },
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "5013",
                            "SiglaPartidoParlamentar": "PSDB",
                            "UfParlamentar": "SP",
                        },
                        "DescricaoVoto": "Não",
                    },
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/plenario/votacao/9001").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    votos = coletar_votos_de_votacao(9001, bucket=_bucket_rapido())
    assert len(votos) == 2
    assert votos[0]["DescricaoVoto"] == "Sim"


@respx.mock
def test_coletar_discursos_por_senador() -> None:
    """Coleta discursos pelo código do senador."""
    payload = {
        "DiscursosParlamentar": {
            "Parlamentar": {
                "Pronunciamentos": {
                    "Pronunciamento": [
                        {
                            "CodigoPronunciamento": "1001",
                            "DataPronunciamento": "2024-03-15",
                            "TipoUsoPalavra": "Plenario",
                            "Resumo": "Fala A",
                            "TextoIntegralTxt": "Texto A",
                        },
                        {
                            "CodigoPronunciamento": "1002",
                            "DataPronunciamento": "2024-03-20",
                            "TipoUsoPalavra": "Plenario",
                            "Resumo": "Fala B",
                            "TextoIntegralTxt": "Texto B",
                        },
                    ]
                }
            }
        }
    }
    respx.get(f"{URL_BASE}/senador/5012/discursos").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    itens = list(coletar_discursos(5012, ano=2024, bucket=_bucket_rapido()))
    assert len(itens) == 2
    # Cada item recebe ``senador_id`` injetado pelo coletor:
    assert all(i["senador_id"] == 5012 for i in itens)


@respx.mock
def test_503_retry_e_sucesso() -> None:
    """503 dispara retry interno; eventualmente sucede."""
    payload_ok = {
        "PesquisaBasicaMateria": {
            "Materias": {
                "Materia": [
                    {
                        "IdentificacaoMateria": {
                            "CodigoMateria": "200",
                            "SiglaSubtipoMateria": "PLS",
                        },
                        "EmentaMateria": "Recuperada após 503",
                    }
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json=payload_ok, headers={"content-type": "application/json"}),
        ]
    )
    itens = list(coletar_materias(2024, bucket=_bucket_rapido()))
    assert len(itens) == 1
    assert itens[0]["EmentaMateria"] == "Recuperada após 503"


@respx.mock
def test_404_propaga_erro() -> None:
    """404 propaga ``HTTPStatusError`` sem retry."""
    rota = respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(404, text="não encontrado")
    )
    with pytest.raises(httpx.HTTPStatusError):
        list(coletar_materias(1900, bucket=_bucket_rapido()))
    # Apenas 1 chamada (sem retry):
    assert rota.call_count == 1


@respx.mock
def test_max_itens_respeitado() -> None:
    """``max_itens=2`` interrompe a iteração mesmo com mais itens disponíveis."""
    payload = {
        "PesquisaBasicaMateria": {
            "Materias": {
                "Materia": [
                    {"IdentificacaoMateria": {"CodigoMateria": str(i)}} for i in range(1, 6)
                ]
            }
        }
    }
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(200, json=payload, headers={"content-type": "application/json"})
    )
    itens = list(coletar_materias(2024, max_itens=2, bucket=_bucket_rapido()))
    assert len(itens) == 2


def test_itens_de_normaliza_dict_solto() -> None:
    """``_itens_de`` empacota dict solto em lista de 1 elemento."""
    from hemiciclo.coleta.senado import _itens_de

    # Dict solto vira lista de 1
    corpo = {"X": {"Y": {"a": 1}}}
    assert _itens_de(corpo, "X", "Y") == [{"a": 1}]

    # Caminho inexistente
    assert _itens_de(corpo, "X", "Z") == []

    # Valor None no caminho
    assert _itens_de({"X": {"Y": None}}, "X", "Y") == []

    # Valor escalar (não dict, não lista)
    assert _itens_de({"X": 42}, "X") == []

    # Lista mista (alguns não-dicts) é filtrada
    corpo_misto = {"X": [{"a": 1}, "lixo", {"b": 2}]}
    assert _itens_de(corpo_misto, "X") == [{"a": 1}, {"b": 2}]


def test_xml_para_dict_agrega_filhos_repetidos() -> None:
    """``_xml_para_dict`` agrega filhos com mesma tag em lista."""
    from lxml import etree

    from hemiciclo.coleta.senado import _xml_para_dict

    xml = b"""<?xml version="1.0"?>
<raiz>
    <item>A</item>
    <item>B</item>
    <item>C</item>
    <unico>X</unico>
</raiz>"""
    raiz = etree.fromstring(xml)
    resultado = _xml_para_dict(raiz)
    assert resultado["item"] == ["A", "B", "C"]
    assert resultado["unico"] == "X"


def test_xml_namespace_e_strip() -> None:
    """``_xml_para_dict`` remove namespaces das tags."""
    from lxml import etree

    from hemiciclo.coleta.senado import _xml_para_dict

    xml = b"""<?xml version="1.0"?>
<raiz xmlns="http://example.com/ns">
    <campo>valor</campo>
</raiz>"""
    raiz = etree.fromstring(xml)
    resultado = _xml_para_dict(raiz)
    assert "campo" in resultado
    assert resultado["campo"] == "valor"


def test_normalizadores_robustos_a_payload_malformado() -> None:
    """Helpers de normalização tratam None/dict/strings inválidas sem quebrar."""
    from hemiciclo.coleta.senado import (
        _int_ou_zero,
        _normalizar_discurso,
        _normalizar_materia,
        _normalizar_senador,
        _normalizar_votacao,
        _normalizar_voto,
        _str_ou_vazio,
    )

    # _str_ou_vazio
    assert _str_ou_vazio(None) == ""
    assert _str_ou_vazio({"a": 1}) == ""
    assert _str_ou_vazio("texto") == "texto"
    assert _str_ou_vazio(42) == "42"

    # _int_ou_zero
    assert _int_ou_zero(None) == 0
    assert _int_ou_zero("") == 0
    assert _int_ou_zero({"a": 1}) == 0
    assert _int_ou_zero("abc") == 0
    assert _int_ou_zero("123") == 123
    assert _int_ou_zero(42) == 42

    # _normalizar_materia com payload mínimo (todos None)
    materia = _normalizar_materia({})
    assert materia["id"] == 0
    assert materia["casa"] == "senado"
    assert materia["hash_conteudo"] == ""

    # _normalizar_materia com IdentificacaoMateria não-dict (defensivo)
    materia2 = _normalizar_materia(
        {
            "IdentificacaoMateria": "string solta",
            "AutorPrincipal": ["lista", "ao inves de dict"],
            "SituacaoAtual": None,
            "EmentaMateria": "minha ementa",
        }
    )
    assert materia2["ementa"] == "minha ementa"
    assert materia2["hash_conteudo"] != ""

    # _normalizar_votacao com Materia não-dict
    # Nota S27.1: campo renomeado de `materia_id` -> `proposicao_id` (alinha
    # com Câmara para consolidador unificado). Quando Materia é não-dict,
    # `proposicao_id` é `None` (não 0) -- 0 quebraria o JOIN do C1 ao
    # confundir-se com BIGINT válido.
    votacao = _normalizar_votacao({"Materia": "string"})
    assert votacao["proposicao_id"] is None
    assert votacao["casa"] == "senado"

    # _normalizar_votacao com Materia.CodigoMateria preenchido (S27.1)
    votacao_ok = _normalizar_votacao(
        {
            "CodigoSessaoVotacao": "777",
            "DescricaoVotacao": "PEC 5/2023",
            "Materia": {"CodigoMateria": "1234567"},
            "DescricaoResultado": "Aprovado",
        }
    )
    assert votacao_ok["proposicao_id"] == 1234567
    assert votacao_ok["id"] == 777

    # _normalizar_voto com IdentificacaoParlamentar não-dict
    voto = _normalizar_voto(99, {"IdentificacaoParlamentar": "string"})
    assert voto["votacao_id"] == 99
    assert voto["senador_id"] == 0

    # _normalizar_discurso com payload mínimo
    discurso = _normalizar_discurso({"senador_id": 5012})
    assert discurso["senador_id"] == 5012
    assert discurso["hash_conteudo"] == ""

    # _normalizar_senador com IdentificacaoParlamentar não-dict
    senador = _normalizar_senador({"IdentificacaoParlamentar": "lixo"}, 56)
    assert senador["legislatura"] == 56
    assert senador["id"] == 0


@respx.mock
def test_parse_xml_fallback() -> None:
    """Resposta com Content-Type XML é parseada via lxml."""
    xml_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<PesquisaBasicaMateria>
    <Materias>
        <Materia>
            <IdentificacaoMateria>
                <CodigoMateria>300</CodigoMateria>
                <SiglaSubtipoMateria>PLS</SiglaSubtipoMateria>
                <NumeroMateria>50</NumeroMateria>
                <AnoMateria>2024</AnoMateria>
            </IdentificacaoMateria>
            <EmentaMateria>Ementa via XML</EmentaMateria>
        </Materia>
    </Materias>
</PesquisaBasicaMateria>
"""
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            content=xml_payload,
            headers={"content-type": "application/xml"},
        )
    )
    itens = list(coletar_materias(2024, bucket=_bucket_rapido()))
    assert len(itens) == 1
    assert itens[0]["EmentaMateria"] == "Ementa via XML"
    assert itens[0]["IdentificacaoMateria"]["CodigoMateria"] == "300"
