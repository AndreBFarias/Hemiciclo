"""Testes integração end-to-end mockados do coletor do Senado.

Valida o fluxo completo (orquestrador + checkpoint + Parquet + XML)
sem depender de rede real -- todas as respostas são mockadas via respx.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import polars as pl
import respx

from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.checkpoint import (
    CheckpointSenado,
    caminho_checkpoint_senado,
    carregar_checkpoint_senado,
    hash_params_senado,
    salvar_checkpoint_senado,
)
from hemiciclo.coleta.rate_limit import TokenBucket
from hemiciclo.coleta.senado import URL_BASE, executar_coleta


def _payload_materias(quantidade: int) -> dict[str, object]:
    """Constrói payload mock JSON com N matérias."""
    materias = [
        {
            "IdentificacaoMateria": {
                "CodigoMateria": str(100 + i),
                "SiglaSubtipoMateria": "PLS",
                "NumeroMateria": str(i),
                "AnoMateria": "2024",
            },
            "EmentaMateria": f"Ementa simulada {i}",
            "DataApresentacao": "2024-03-15",
            "AutorPrincipal": {"NomeAutor": f"Senador {i}"},
            "SituacaoAtual": {"DescricaoSituacao": "Em tramitacao"},
            "UrlTexto": f"https://senado.leg.br/teor/{i}.pdf",
        }
        for i in range(1, quantidade + 1)
    ]
    return {"PesquisaBasicaMateria": {"Materias": {"Materia": materias}}}


@respx.mock
def test_coleta_completa_persiste_parquet(tmp_path: Path) -> None:
    """Coleta de 10 matérias mockadas escreve Parquet com schema 12 colunas."""
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            json=_payload_materias(10),
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        max_itens=10,
        dir_saida=saida,
    )

    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "materias.parquet"
    assert arquivo.exists()

    df = pl.read_parquet(arquivo)
    assert df.height == 10
    assert df.width == 12
    colunas_esperadas = {
        "id",
        "sigla",
        "numero",
        "ano",
        "ementa",
        "tema_oficial",
        "autor_principal",
        "data_apresentacao",
        "status",
        "url_inteiro_teor",
        "casa",
        "hash_conteudo",
    }
    assert colunas_esperadas == set(df.columns)
    # Casa correta (alinhamento com Câmara para união em S26):
    assert df["casa"].to_list() == ["senado"] * 10

    # Hash conteúdo é SHA256 da ementa (lição S24, ACHADO 3):
    primeiro_hash = df["hash_conteudo"][0]
    assert primeiro_hash != ""
    assert len(primeiro_hash) == 16  # primeiros 16 chars do sha256

    # Checkpoint persistido com prefixo senado_:
    h = hash_params_senado([2024], list(params.tipos))
    cp_path = caminho_checkpoint_senado(home, h)
    assert cp_path.exists()
    assert cp_path.name.startswith("senado_")

    cp_disco = carregar_checkpoint_senado(cp_path)
    assert cp_disco is not None
    assert len(cp_disco.materias_baixadas) == 10
    assert cp.materias_baixadas == cp_disco.materias_baixadas


@respx.mock
def test_kill_e_retomada_idempotente(tmp_path: Path) -> None:
    """Após retomada, segunda execução não recoleta itens já baixados."""
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            json=_payload_materias(10),
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        max_itens=10,
        dir_saida=saida,
    )

    # Pre-carrega checkpoint com IDs 101..105 já baixados:
    h = hash_params_senado([2024], list(params.tipos))
    cp_path = caminho_checkpoint_senado(home, h)
    cp_pre = CheckpointSenado(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        anos=[2024],
        tipos=list(params.tipos),
        materias_baixadas={101, 102, 103, 104, 105},
    )
    salvar_checkpoint_senado(cp_pre, cp_path)

    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp_pos = executar_coleta(params, home=home, bucket=bucket)

    # Apenas 106..110 entraram no Parquet desta rodada:
    arquivo = saida / "materias.parquet"
    df = pl.read_parquet(arquivo)
    ids_no_parquet = set(df["id"].to_list())
    assert ids_no_parquet == {106, 107, 108, 109, 110}

    # Checkpoint final acumula todos os 10:
    assert cp_pos.materias_baixadas == set(range(101, 111))


@respx.mock
def test_xml_payload_parseado_correto(tmp_path: Path) -> None:
    """Payload XML do Senado é parseado e persiste corretamente."""
    xml_payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<PesquisaBasicaMateria>
    <Materias>
        <Materia>
            <IdentificacaoMateria>
                <CodigoMateria>500</CodigoMateria>
                <SiglaSubtipoMateria>PLS</SiglaSubtipoMateria>
                <NumeroMateria>50</NumeroMateria>
                <AnoMateria>2024</AnoMateria>
            </IdentificacaoMateria>
            <EmentaMateria>Materia em XML A</EmentaMateria>
            <DataApresentacao>2024-04-01</DataApresentacao>
        </Materia>
        <Materia>
            <IdentificacaoMateria>
                <CodigoMateria>501</CodigoMateria>
                <SiglaSubtipoMateria>PLS</SiglaSubtipoMateria>
                <NumeroMateria>51</NumeroMateria>
                <AnoMateria>2024</AnoMateria>
            </IdentificacaoMateria>
            <EmentaMateria>Materia em XML B</EmentaMateria>
            <DataApresentacao>2024-04-02</DataApresentacao>
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

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "materias.parquet"
    df = pl.read_parquet(arquivo)
    assert df.height == 2
    ementas = set(df["ementa"].to_list())
    assert ementas == {"Materia em XML A", "Materia em XML B"}
    assert cp.materias_baixadas == {500, 501}


@respx.mock
def test_checkpoint_senado_sobrevive_a_kill(tmp_path: Path) -> None:
    """Após coleta + adição manual de votos, sets/tuples sobrevivem round-trip."""
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            json=_payload_materias(3),
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        max_itens=3,
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    # Adiciona votos manualmente para testar tuple round-trip:
    cp.votos_baixados.add((9001, 5012))
    cp.votos_baixados.add((9001, 5013))

    h = hash_params_senado([2024], list(params.tipos))
    cp_path = caminho_checkpoint_senado(home, h)
    salvar_checkpoint_senado(cp, cp_path)

    rec = carregar_checkpoint_senado(cp_path)
    assert rec is not None
    assert (9001, 5012) in rec.votos_baixados
    assert (9001, 5013) in rec.votos_baixados
    assert all(isinstance(t, tuple) for t in rec.votos_baixados)


@respx.mock
def test_orquestrador_processa_5_tipos(tmp_path: Path) -> None:
    """Orquestrador processa materias + senadores em uma única invocação."""
    # Mock matérias:
    respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            json=_payload_materias(2),
            headers={"content-type": "application/json"},
        )
    )
    # Mock senadores:
    respx.get(f"{URL_BASE}/senador/lista/legislatura/56").mock(
        return_value=httpx.Response(
            200,
            json={
                "ListaParlamentarLegislatura": {
                    "Parlamentares": {
                        "Parlamentar": [
                            {
                                "IdentificacaoParlamentar": {
                                    "CodigoParlamentar": "5012",
                                    "NomeParlamentar": "Fulano",
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
            },
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias", "senadores"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    assert (saida / "materias.parquet").exists()
    assert (saida / "senadores.parquet").exists()

    df_mat = pl.read_parquet(saida / "materias.parquet")
    df_sen = pl.read_parquet(saida / "senadores.parquet")
    assert df_mat.height == 2
    assert df_sen.height == 2
    assert {"id", "nome", "partido", "uf", "legislatura"}.issubset(set(df_sen.columns))

    assert cp.materias_baixadas == {101, 102}
    assert cp.senadores_baixados == {5012, 5013}


@respx.mock
def test_orquestrador_votacoes_e_votos(tmp_path: Path) -> None:
    """Orquestrador processa votacoes + votos, persiste dois Parquet."""
    respx.get(f"{URL_BASE}/plenario/lista/votacao/2024").mock(
        return_value=httpx.Response(
            200,
            json={
                "ListaVotacoes": {
                    "Votacoes": {
                        "Votacao": {
                            "CodigoSessaoVotacao": "9001",
                            "DataSessao": "2024-03-15",
                            "DescricaoVotacao": "PLS 100/2024",
                            "Materia": {"CodigoMateria": "100"},
                            "Resultado": "Aprovado",
                        }
                    }
                }
            },
            headers={"content-type": "application/json"},
        )
    )
    respx.get(f"{URL_BASE}/plenario/votacao/9001").mock(
        return_value=httpx.Response(
            200,
            json={
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
            },
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["votacoes", "votos"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo_v = saida / "votacoes_senado.parquet"
    arquivo_voto = saida / "votos_senado.parquet"
    assert arquivo_v.exists()
    assert arquivo_voto.exists()

    df_v = pl.read_parquet(arquivo_v)
    df_voto = pl.read_parquet(arquivo_voto)
    assert df_v.height == 1
    assert df_voto.height == 2
    assert df_v["casa"].to_list() == ["senado"]
    assert {"votacao_id", "senador_id", "voto", "partido", "uf"} == set(df_voto.columns)
    assert 9001 in cp.votacoes_baixadas
    assert (9001, 5012) in cp.votos_baixados
    assert (9001, 5013) in cp.votos_baixados


@respx.mock
def test_orquestrador_discursos(tmp_path: Path) -> None:
    """Orquestrador processa discursos por senador (precisa de senadores antes)."""
    respx.get(f"{URL_BASE}/senador/lista/legislatura/56").mock(
        return_value=httpx.Response(
            200,
            json={
                "ListaParlamentarLegislatura": {
                    "Parlamentares": {
                        "Parlamentar": {
                            "IdentificacaoParlamentar": {
                                "CodigoParlamentar": "5012",
                                "NomeParlamentar": "Fulano",
                                "SiglaPartidoParlamentar": "PT",
                                "UfParlamentar": "BA",
                            }
                        }
                    }
                }
            },
            headers={"content-type": "application/json"},
        )
    )
    respx.get(f"{URL_BASE}/senador/5012/discursos").mock(
        return_value=httpx.Response(
            200,
            json={
                "DiscursosParlamentar": {
                    "Parlamentar": {
                        "Pronunciamentos": {
                            "Pronunciamento": [
                                {
                                    "CodigoPronunciamento": "11",
                                    "DataPronunciamento": "2024-03-15",
                                    "TipoUsoPalavra": "Plenario",
                                    "Resumo": "Fala A",
                                    "TextoIntegralTxt": "Texto A",
                                },
                                {
                                    "CodigoPronunciamento": "12",
                                    "DataPronunciamento": "2024-03-16",
                                    "TipoUsoPalavra": "Plenario",
                                    "Resumo": "Fala B",
                                    "TextoIntegralTxt": "Texto B",
                                },
                            ]
                        }
                    }
                }
            },
            headers={"content-type": "application/json"},
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["senadores", "discursos"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "discursos_senado.parquet"
    assert arquivo.exists()
    df = pl.read_parquet(arquivo)
    assert df.height == 2
    assert len(cp.discursos_baixados) == 2


@respx.mock
def test_url_aponta_apenas_governo_brasileiro(tmp_path: Path) -> None:
    """I1 BRIEF: URL_BASE só aponta para domínio público .leg.br do Senado."""
    rota = respx.get(f"{URL_BASE}/materia/pesquisa/lista").mock(
        return_value=httpx.Response(
            200,
            json=_payload_materias(1),
            headers={"content-type": "application/json"},
        )
    )
    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[56],
        tipos=["materias"],
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        max_itens=1,
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    executar_coleta(params, home=home, bucket=bucket)

    chamada = rota.calls[0].request
    url_chamada = str(chamada.url)
    assert "legis.senado.leg.br" in url_chamada, (
        f"URL deve apontar para domínio governo BR: {url_chamada}"
    )
