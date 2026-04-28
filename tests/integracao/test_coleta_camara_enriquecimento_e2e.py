"""Teste integração e2e mockado do enriquecimento de proposições (S24b).

Pipeline completo: listagem 5 proposições + 5 detalhes + 5 autores -->
``proposicoes.parquet`` (5 linhas) + ``proposicoes_detalhe.parquet`` (5
linhas com 4 campos preenchidos) + checkpoint atualizado.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import polars as pl
import respx

from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.camara import URL_BASE, executar_coleta
from hemiciclo.coleta.rate_limit import TokenBucket


def _bucket_rapido() -> TokenBucket:
    return TokenBucket(taxa=10000.0, capacidade=10000)


@respx.mock
def test_pipeline_full_listagem_mais_detalhe_persiste_parquet(
    tmp_path: Path,
) -> None:
    """5 proposições -> listagem.parquet (5L) + detalhe.parquet (5L) + checkpoint=5."""
    home = tmp_path / "hemiciclo"
    saida = tmp_path / "saida"

    # Listagem com 5 itens (campos resumidos -- temaOficial/autorPrincipal
    # propositadamente ausentes; é justamente isto que o enriquecimento existe
    # para preencher).
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": pid,
                        "siglaTipo": "PL",
                        "numero": pid * 100,
                        "ano": 2024,
                        "ementa": f"Ementa {pid}",
                    }
                    for pid in range(1, 6)
                ]
            },
        )
    )

    # Detalhes individuais.
    for pid in range(1, 6):
        respx.get(f"{URL_BASE}/proposicoes/{pid}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "dados": {
                        "id": pid,
                        "ementa": f"Ementa {pid}",
                        "temaOficial": f"Tema {pid}",
                        "statusProposicao": {"descricaoSituacao": f"Em tramitação {pid}"},
                        "urlInteiroTeor": f"https://exemplo/{pid}.pdf",
                        "uriAutores": f"{URL_BASE}/proposicoes/{pid}/autores",
                    }
                },
            )
        )
        respx.get(f"{URL_BASE}/proposicoes/{pid}/autores").mock(
            return_value=httpx.Response(
                200,
                json={"dados": [{"nome": f"Deputado{pid}"}]},
            )
        )

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=5,
        dir_saida=saida,
        enriquecer_proposicoes=True,
    )
    cp = executar_coleta(params, home=home, bucket=_bucket_rapido())

    # Listagem persistida.
    listagem = saida / "proposicoes.parquet"
    assert listagem.exists()
    df_list = pl.read_parquet(listagem)
    assert df_list.height == 5

    # Detalhe persistido com 4 campos preenchidos.
    detalhe = saida / "proposicoes_detalhe.parquet"
    assert detalhe.exists()
    df_det = pl.read_parquet(detalhe)
    assert df_det.height == 5
    # Todos os 4 campos viram não-nulos (mocks têm cobertura 100%).
    for coluna in ("tema_oficial", "autor_principal", "status", "url_inteiro_teor"):
        nao_nulos = df_det[coluna].is_not_null().sum()
        assert nao_nulos == 5, f"coluna {coluna} esperava 5 não-nulos, obteve {nao_nulos}"

    # Checkpoint refletindo enriquecimento.
    assert cp.proposicoes_baixadas == {1, 2, 3, 4, 5}
    assert cp.proposicoes_enriquecidas == {1, 2, 3, 4, 5}
    assert cp.total_baixado() >= 10  # 5 baixadas + 5 enriquecidas
