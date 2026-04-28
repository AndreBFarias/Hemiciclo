"""Testes integração end-to-end mockados do coletor da Câmara.

Valida o fluxo completo (orquestrador + checkpoint + Parquet) sem
depender de rede real -- todas as respostas são mockadas via respx.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import httpx
import polars as pl
import pytest
import respx

from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.camara import URL_BASE, executar_coleta
from hemiciclo.coleta.checkpoint import (
    CheckpointCamara,
    caminho_checkpoint,
    carregar_checkpoint,
    hash_params,
    salvar_checkpoint,
)
from hemiciclo.coleta.rate_limit import TokenBucket


def _payload_proposicoes(quantidade: int) -> dict[str, object]:
    """Constrói payload mock com N proposições."""
    return {
        "dados": [
            {
                "id": i,
                "siglaTipo": "PL",
                "numero": 1000 + i,
                "ano": 2024,
                "ementa": f"Ementa simulada {i}",
                "temaOficial": "Saude",
                "autorPrincipal": f"Deputado {i}",
                "dataApresentacao": "2024-03-15",
                "statusProposicao": {"descricaoSituacao": "Em tramitacao"},
                "urlInteiroTeor": f"https://camara.leg.br/teor/{i}.pdf",
                "uri": f"https://camara.leg.br/api/proposicoes/{i}",
            }
            for i in range(1, quantidade + 1)
        ]
    }


@respx.mock
def test_coleta_completa_persiste_parquet(tmp_path: Path) -> None:
    """Coleta de 10 proposições mockadas escreve Parquet com schema correto."""
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(200, json=_payload_proposicoes(10))
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=10,
        dir_saida=saida,
        # S24b: testes históricos cobrem apenas a listagem; enriquecimento
        # tem testes próprios em ``test_coleta_camara_detalhe.py`` e
        # ``test_coleta_camara_enriquecimento_e2e.py``.
        enriquecer_proposicoes=False,
    )

    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "proposicoes.parquet"
    assert arquivo.exists()

    df = pl.read_parquet(arquivo)
    assert df.height == 10
    # 12 colunas mínimas conforme spec
    assert df.width >= 12
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
    assert colunas_esperadas.issubset(set(df.columns))

    # Checkpoint persistido:
    h = hash_params(params.legislaturas, list(params.tipos))
    cp_path = caminho_checkpoint(home, h)
    assert cp_path.exists()
    cp_disco = carregar_checkpoint(cp_path)
    assert cp_disco is not None
    assert len(cp_disco.proposicoes_baixadas) == 10
    assert cp.proposicoes_baixadas == cp_disco.proposicoes_baixadas


@respx.mock
def test_kill_e_retomada_idempotente(tmp_path: Path) -> None:
    """Após retomada, segunda execução não recoleta itens já baixados.

    Simulação: pré-carrega o checkpoint com 5 IDs já baixados; roda a
    coleta de novo e confirma que esses itens não aparecem no Parquet
    final (foram pulados).
    """
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(200, json=_payload_proposicoes(10))
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=10,
        dir_saida=saida,
        # S24b: idempotência da listagem é o foco aqui; enriquecimento
        # tem testes próprios.
        enriquecer_proposicoes=False,
    )

    # Simula execução anterior interrompida: checkpoint com IDs 1..5.
    h = hash_params(params.legislaturas, list(params.tipos))
    cp_path = caminho_checkpoint(home, h)
    from datetime import datetime

    cp_pre = CheckpointCamara(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        legislaturas=params.legislaturas,
        tipos=list(params.tipos),
        proposicoes_baixadas={1, 2, 3, 4, 5},
    )
    salvar_checkpoint(cp_pre, cp_path)

    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp_pos = executar_coleta(params, home=home, bucket=bucket)

    # Itens 1..5 já estavam, então só 6..10 entraram no Parquet desta rodada.
    arquivo = saida / "proposicoes.parquet"
    df = pl.read_parquet(arquivo)
    ids_no_parquet = set(df["id"].to_list())
    assert ids_no_parquet == {6, 7, 8, 9, 10}

    # Checkpoint final acumula todos os 10:
    assert cp_pos.proposicoes_baixadas == set(range(1, 11))


@respx.mock
def test_checkpoint_persistido_com_set_de_tuples(tmp_path: Path) -> None:
    """Após coleta, sets e tuples sobrevivem round-trip via JSON do disco."""
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(200, json=_payload_proposicoes(3))
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=3,
        dir_saida=saida,
        # S24b: foco é round-trip do checkpoint; enriquecimento isolado.
        enriquecer_proposicoes=False,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    # Adiciona votos manualmente para testar tuple round-trip:
    cp.votos_baixados.add(("votacao-x", 100))
    cp.votos_baixados.add(("votacao-x", 101))

    h = hash_params(params.legislaturas, list(params.tipos))
    cp_path = caminho_checkpoint(home, h)
    salvar_checkpoint(cp, cp_path)

    rec = carregar_checkpoint(cp_path)
    assert rec is not None
    assert ("votacao-x", 100) in rec.votos_baixados
    assert all(isinstance(t, tuple) for t in rec.votos_baixados)


@respx.mock
def test_coleta_deputados_persiste_parquet(tmp_path: Path) -> None:
    """Coleta de cadastro de deputados persiste Parquet com 7 colunas."""
    respx.get(f"{URL_BASE}/deputados").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": 100,
                        "nome": "Fulano da Silva",
                        "nomeEleitoral": "Fulano",
                        "siglaPartido": "P",
                        "siglaUf": "SP",
                        "email": "fulano@camara.leg.br",
                    },
                    {
                        "id": 101,
                        "nome": "Beltrano de Souza",
                        "nomeEleitoral": "Beltrano",
                        "siglaPartido": "Q",
                        "siglaUf": "RJ",
                        "email": "beltrano@camara.leg.br",
                    },
                ]
            },
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["deputados"],
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "deputados.parquet"
    assert arquivo.exists()
    df = pl.read_parquet(arquivo)
    assert df.height == 2
    assert {"id", "nome", "partido", "uf", "legislatura"}.issubset(set(df.columns))
    assert cp.deputados_baixados == {100, 101}


@respx.mock
def test_coleta_votacoes_e_votos_persiste_parquet(tmp_path: Path) -> None:
    """Coleta de votações + votos respeita intervalo e produz dois Parquet."""
    from datetime import date as _d

    respx.get(f"{URL_BASE}/votacoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": "vot-1",
                        "data": "2024-03-15",
                        "descricao": "PL 100/2024",
                        "descricaoResultado": "Aprovado",
                    },
                ]
            },
        )
    )
    respx.get(f"{URL_BASE}/votacoes/vot-1/votos").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "deputado_": {"id": 100, "siglaPartido": "P", "siglaUf": "SP"},
                        "tipoVoto": "Sim",
                    },
                    {
                        "deputado_": {"id": 101, "siglaPartido": "Q", "siglaUf": "RJ"},
                        "tipoVoto": "Nao",
                    },
                ]
            },
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["votacoes", "votos"],
        data_inicio=_d(2024, 3, 1),
        data_fim=_d(2024, 3, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    assert (saida / "votacoes.parquet").exists()
    assert (saida / "votos.parquet").exists()
    df_votos = pl.read_parquet(saida / "votos.parquet")
    assert df_votos.height == 2
    assert "vot-1" in cp.votacoes_baixadas
    assert ("vot-1", 100) in cp.votos_baixados


@respx.mock
def test_coleta_votacoes_sem_data_pula_com_warning(tmp_path: Path) -> None:
    """``votacoes`` sem ``data_inicio`` é pulado com warning, não erro."""
    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["votacoes"],
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)
    assert cp.total_baixado() == 0


@respx.mock
def test_coleta_discursos_sem_data_pula_com_warning(tmp_path: Path) -> None:
    """``discursos`` sem ``data_inicio`` é pulado com warning, não erro."""
    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["discursos"],
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)
    assert cp.total_baixado() == 0


@respx.mock
def test_coleta_discursos_com_data_persiste_parquet(tmp_path: Path) -> None:
    """Coleta discursos passa pelo cadastro de deputados primeiro."""
    from datetime import date as _d

    respx.get(f"{URL_BASE}/deputados").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"id": 100, "nome": "Fulano", "siglaPartido": "P", "siglaUf": "SP"},
                ]
            },
        )
    )
    respx.get(f"{URL_BASE}/deputados/100/discursos").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": "disc-1",
                        "dataHoraInicio": "2024-03-15T14:30:00",
                        "tipoDiscurso": "Plenario",
                        "sumario": "Fala simulada A",
                        "transcricao": "Texto A",
                    },
                    {
                        "id": "disc-2",
                        "dataHoraInicio": "2024-03-16T10:00:00",
                        "tipoDiscurso": "Plenario",
                        "sumario": "Fala simulada B",
                        "transcricao": "Texto B",
                    },
                ]
            },
        )
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"
    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["discursos"],
        data_inicio=_d(2024, 3, 1),
        data_fim=_d(2024, 3, 31),
        dir_saida=saida,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp = executar_coleta(params, home=home, bucket=bucket)

    arquivo = saida / "discursos.parquet"
    assert arquivo.exists()
    df = pl.read_parquet(arquivo)
    assert df.height == 2
    assert len(cp.discursos_baixados) == 2


@respx.mock
def test_executar_coleta_proposicoes_retoma_por_ano_apos_kill(
    tmp_path: Path,
) -> None:
    """Retomada por ano: segunda execução pula anos já concluídos (S24c).

    Cenário:

    1. Mock devolve 100 itens (sem header Link) em qualquer GET.
    2. Primeira execução com ``max_itens=150`` baixa: ano 2023 inteiro
       (100 itens, fecha sem interrupção -> marcado em
       ``anos_concluidos``) + 50 itens parciais do ano 2024
       (interrompido por limite global -> ano 2024 NÃO é marcado).
    3. Segunda execução com ``max_itens=20000`` consulta o checkpoint
       persistido e pula 2023 (concluído). Coleta 2024+2025+2026.
       Idempotência via ``proposicoes_baixadas`` garante que IDs
       repetidos do mock não são duplicados.
    4. Asserções: número de chamadas HTTP da segunda execução é
       estritamente menor que uma coleta from-scratch (4) e o
       checkpoint final marca 2023, 2024, 2025, 2026 como concluídos.
    """
    payload_100 = {
        "dados": [
            {
                "id": i,
                "siglaTipo": "PL",
                "numero": 1000 + i,
                "ano": 2024,
                "ementa": f"Ementa {i}",
                "temaOficial": "Saude",
            }
            for i in range(1, 101)
        ]
    }
    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(200, json=payload_100)
    )

    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=150,
        dir_saida=saida,
        enriquecer_proposicoes=False,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    cp1 = executar_coleta(params, home=home, bucket=bucket)
    chamadas_primeira = rota.call_count

    # Primeira execução: 2 chamadas (ano 2023 inteiro + 1 GET parcial 2024).
    assert chamadas_primeira == 2
    # Apenas 2023 fechou sem interrupção; 2024 ficou no meio.
    assert cp1.anos_concluidos == {(57, 2023)}

    # Segunda execução com limite alto: pula 2023 e coleta os outros 3 anos.
    params2 = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=20000,
        dir_saida=saida,
        enriquecer_proposicoes=False,
    )
    cp2 = executar_coleta(params2, home=home, bucket=bucket)
    chamadas_segunda = rota.call_count - chamadas_primeira

    # Apenas 3 chamadas novas (2024 + 2025 + 2026); 2023 foi pulado.
    assert chamadas_segunda == 3
    assert chamadas_segunda < 4  # estritamente menor que coleta from-scratch.
    assert cp2.anos_concluidos == {
        (57, 2023),
        (57, 2024),
        (57, 2025),
        (57, 2026),
    }
    # Idempotência: IDs repetidos no mock não duplicam.
    assert len(cp2.proposicoes_baixadas) == 100


@pytest.mark.parametrize("legislatura", [55, 56, 57])
@respx.mock
def test_url_aponta_apenas_governo_brasileiro(legislatura: int, tmp_path: Path) -> None:
    """I1 BRIEF: URL_BASE só aponta para domínio público .gov.br ou .leg.br."""
    rota = respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(200, json=_payload_proposicoes(1))
    )
    saida = tmp_path / "saida"
    home = tmp_path / "home"

    params = ParametrosColeta(
        legislaturas=[legislatura],
        tipos=["proposicoes"],
        max_itens=1,
        dir_saida=saida,
        # S24b: este teste valida URL_BASE da listagem; enriquecimento
        # isolado em test_coleta_camara_enriquecimento_e2e.
        enriquecer_proposicoes=False,
    )
    bucket = TokenBucket(taxa=10000.0, capacidade=10000)
    executar_coleta(params, home=home, bucket=bucket)

    chamada = rota.calls[0].request
    url_chamada = str(chamada.url)
    assert "dadosabertos.camara.leg.br" in url_chamada or "camara.leg.br" in url_chamada, (
        f"URL deve apontar para domínio governo BR: {url_chamada}"
    )
