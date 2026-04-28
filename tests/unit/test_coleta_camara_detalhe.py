"""Testes unit do enriquecimento de proposições da Câmara (S24b).

Cobrem:

- ``enriquecer_proposicao`` em caminho feliz, 404, retry 503, payload pobre.
- ``_resolver_autor_principal`` em caminho feliz e lista vazia.
- Cache JSON round-trip + cache hit pula chamada à API.
- Pipeline marca ``proposicoes_enriquecidas`` no checkpoint.
- Retomada idempotente pula proposições já enriquecidas.
- CLI flag ``--enriquecer-proposicoes`` default True.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl
import pytest
import respx
from typer.testing import CliRunner

from hemiciclo.cli import app
from hemiciclo.coleta import ParametrosColeta
from hemiciclo.coleta.camara import (
    URL_BASE,
    _resolver_autor_principal,
    enriquecer_proposicao,
    executar_coleta,
)
from hemiciclo.coleta.rate_limit import TokenBucket
from hemiciclo.etl.cache import (
    caminho_cache_detalhe_proposicao,
    carregar_cache_detalhe_proposicao,
    salvar_cache_detalhe_proposicao,
)


def _bucket_rapido() -> TokenBucket:
    """Bucket altíssimo -- evita esperar nos testes."""
    return TokenBucket(taxa=10000.0, capacidade=10000)


def _payload_detalhe_completo(prop_id: int = 12345) -> dict[str, Any]:
    """Payload simulando ``GET /proposicoes/{id}`` com todos os campos."""
    return {
        "dados": {
            "id": prop_id,
            "siglaTipo": "PL",
            "numero": 100,
            "ano": 2024,
            "ementa": "ementa exemplo",
            "dataApresentacao": "2024-02-01T15:00",
            "statusProposicao": {
                "dataHora": "2024-04-15T10:00",
                "descricaoSituacao": "Aprovada na Câmara",
                "descricaoTramitacao": "Aprovação",
            },
            "urlInteiroTeor": "https://www.camara.leg.br/proposicoesWeb/abc.pdf",
            "uriAutores": f"{URL_BASE}/proposicoes/{prop_id}/autores",
            "temaOficial": "Política Econômica",
        }
    }


@respx.mock
def test_enriquecer_proposicao_caminho_feliz() -> None:
    """Caminho feliz: 4 campos preenchidos + autor resolvido."""
    prop_id = 12345
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(
        return_value=httpx.Response(200, json=_payload_detalhe_completo(prop_id))
    )
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}/autores").mock(
        return_value=httpx.Response(
            200,
            json={"dados": [{"nome": "Deputada Joana", "tipo": "Deputado"}]},
        ),
    )

    det = enriquecer_proposicao(prop_id, bucket=_bucket_rapido())

    assert det["id"] == prop_id
    assert det["casa"] == "camara"
    assert det["tema_oficial"] == "Política Econômica"
    assert det["autor_principal"] == "Deputada Joana"
    assert det["status"] == "Aprovada na Câmara"
    assert det["url_inteiro_teor"].startswith("https://www.camara.leg.br")
    # ``enriquecido_em`` é ISO 8601 parseável.
    assert datetime.fromisoformat(det["enriquecido_em"]).tzinfo is not None


@respx.mock
def test_enriquecer_proposicao_404_retorna_nones() -> None:
    """404 não interrompe pipeline -- 4 campos viram None."""
    prop_id = 99999
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(
        return_value=httpx.Response(404, json={"message": "não encontrado"})
    )

    det = enriquecer_proposicao(prop_id, bucket=_bucket_rapido())

    assert det["id"] == prop_id
    assert det["tema_oficial"] is None
    assert det["autor_principal"] is None
    assert det["status"] is None
    assert det["url_inteiro_teor"] is None


@respx.mock
def test_enriquecer_proposicao_503_retry_e_sucesso() -> None:
    """503 dispara retry; 200 subsequente fecha o pedido."""
    prop_id = 555
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=_payload_detalhe_completo(prop_id)),
        ]
    )
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}/autores").mock(
        return_value=httpx.Response(200, json={"dados": [{"nome": "Senador Silva"}]})
    )

    det = enriquecer_proposicao(prop_id, bucket=_bucket_rapido())

    assert det["tema_oficial"] == "Política Econômica"
    assert det["autor_principal"] == "Senador Silva"


@respx.mock
def test_enriquecer_proposicao_campos_ausentes_no_payload() -> None:
    """Payload sem ``temaOficial``/``urlInteiroTeor`` -> defaults None (não '')."""
    prop_id = 777
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": {
                    "id": prop_id,
                    "siglaTipo": "PL",
                    "ementa": "ementa parcial",
                }
            },
        )
    )

    det = enriquecer_proposicao(prop_id, bucket=_bucket_rapido())

    assert det["tema_oficial"] is None
    assert det["autor_principal"] is None
    assert det["status"] is None
    assert det["url_inteiro_teor"] is None
    # Nenhum campo deve ser string vazia (lição S27.1).
    for campo in ("tema_oficial", "autor_principal", "status", "url_inteiro_teor"):
        assert det[campo] is None or det[campo] != ""


@respx.mock
def test_resolver_autor_principal_caminho_feliz() -> None:
    """Resolver autor: primeiro nome da lista ``dados``."""
    uri = f"{URL_BASE}/proposicoes/100/autores"
    respx.get(uri).mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {"nome": "Deputado A", "tipo": "Deputado"},
                    {"nome": "Deputado B"},
                ]
            },
        )
    )
    cli = httpx.Client()
    try:
        nome = _resolver_autor_principal(uri, bucket=_bucket_rapido(), cli=cli)
    finally:
        cli.close()
    assert nome == "Deputado A"


@respx.mock
def test_resolver_autor_principal_lista_vazia() -> None:
    """Lista de autores vazia retorna None sem raise."""
    uri = f"{URL_BASE}/proposicoes/200/autores"
    respx.get(uri).mock(return_value=httpx.Response(200, json={"dados": []}))
    cli = httpx.Client()
    try:
        nome = _resolver_autor_principal(uri, bucket=_bucket_rapido(), cli=cli)
    finally:
        cli.close()
    assert nome is None


def test_cache_detalhe_round_trip(tmp_path: Path) -> None:
    """Salvar e carregar detalhe via cache JSON preserva o payload."""
    home = tmp_path / "hemiciclo"
    payload = {
        "id": 42,
        "ementa": "ementa de teste",
        "statusProposicao": {"descricaoSituacao": "Em tramitação"},
        "temaOficial": "Saúde",
    }
    salvar_cache_detalhe_proposicao(payload, home, "camara", 42)
    path = caminho_cache_detalhe_proposicao(home, "camara", 42)
    assert path.exists()
    assert path.name == "camara-42.json"

    carregado = carregar_cache_detalhe_proposicao(home, "camara", 42)
    assert carregado == payload

    # Ausente retorna None.
    assert carregar_cache_detalhe_proposicao(home, "camara", 999) is None


@respx.mock
def test_enriquecer_consulta_cache_antes_de_api(tmp_path: Path) -> None:
    """Cache hit pula chamada à API -- mock de erro não é acionado."""
    home = tmp_path / "hemiciclo"
    prop_id = 4242

    payload_cacheado: dict[str, Any] = {
        "id": prop_id,
        "temaOficial": "Educação",
        "statusProposicao": {"descricaoSituacao": "Arquivada"},
        "urlInteiroTeor": "https://exemplo/teor.pdf",
    }
    salvar_cache_detalhe_proposicao(payload_cacheado, home, "camara", prop_id)

    # Mock 500 garante que se houver chamada ela falharia, mas não deve haver.
    rota = respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(return_value=httpx.Response(500))

    det = enriquecer_proposicao(prop_id, home=home, bucket=_bucket_rapido())

    assert det["tema_oficial"] == "Educação"
    assert det["status"] == "Arquivada"
    assert det["url_inteiro_teor"] == "https://exemplo/teor.pdf"
    # API NÃO foi chamada.
    assert rota.call_count == 0


@respx.mock
def test_pipeline_marca_proposicoes_enriquecidas_no_checkpoint(tmp_path: Path) -> None:
    """Pipeline e2e curto: 3 proposições -> 3 enriquecidas no checkpoint."""
    home = tmp_path / "hemiciclo"
    saida = tmp_path / "saida"

    # Listagem com 3 proposições.
    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": 1,
                        "siglaTipo": "PL",
                        "numero": 1,
                        "ano": 2024,
                        "ementa": "e1",
                    },
                    {
                        "id": 2,
                        "siglaTipo": "PL",
                        "numero": 2,
                        "ano": 2024,
                        "ementa": "e2",
                    },
                    {
                        "id": 3,
                        "siglaTipo": "PL",
                        "numero": 3,
                        "ano": 2024,
                        "ementa": "e3",
                    },
                ]
            },
        )
    )
    for pid in (1, 2, 3):
        respx.get(f"{URL_BASE}/proposicoes/{pid}").mock(
            return_value=httpx.Response(200, json=_payload_detalhe_completo(pid))
        )
        respx.get(f"{URL_BASE}/proposicoes/{pid}/autores").mock(
            return_value=httpx.Response(200, json={"dados": [{"nome": f"Autor{pid}"}]})
        )

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=3,
        dir_saida=saida,
        enriquecer_proposicoes=True,
    )
    cp = executar_coleta(params, home=home, bucket=_bucket_rapido())

    assert cp.proposicoes_baixadas == {1, 2, 3}
    assert cp.proposicoes_enriquecidas == {1, 2, 3}

    detalhe_path = saida / "proposicoes_detalhe.parquet"
    assert detalhe_path.exists()
    df = pl.read_parquet(detalhe_path)
    assert df.height == 3
    assert set(df.columns) == {
        "id",
        "casa",
        "tema_oficial",
        "autor_principal",
        "status",
        "url_inteiro_teor",
        "enriquecido_em",
    }


@respx.mock
def test_retomada_idempotente_pula_ja_enriquecidas(tmp_path: Path) -> None:
    """Pré-popular ``proposicoes_enriquecidas`` -> apenas as faltantes são tentadas."""
    from hemiciclo.coleta.checkpoint import (
        CheckpointCamara,
        caminho_checkpoint,
        hash_params,
        salvar_checkpoint,
    )

    home = tmp_path / "hemiciclo"
    saida = tmp_path / "saida"

    # Pré-popular checkpoint: já baixou 1, 2, 3 e já enriqueceu 1, 2.
    cp_inicial = CheckpointCamara(
        iniciado_em=datetime.now(UTC),
        atualizado_em=datetime.now(UTC),
        legislaturas=[57],
        tipos=["proposicoes"],
        proposicoes_baixadas={1, 2, 3},
        proposicoes_enriquecidas={1, 2},
    )
    h = hash_params([57], ["proposicoes"])
    cp_path = caminho_checkpoint(home, h)
    salvar_checkpoint(cp_inicial, cp_path)

    # Listagem mockada vazia (não vai re-baixar -- já está no checkpoint).
    respx.get(f"{URL_BASE}/proposicoes").mock(return_value=httpx.Response(200, json={"dados": []}))
    # Mock detalhe APENAS para o id 3 (os outros não devem ser chamados).
    rota_3 = respx.get(f"{URL_BASE}/proposicoes/3").mock(
        return_value=httpx.Response(200, json=_payload_detalhe_completo(3))
    )
    respx.get(f"{URL_BASE}/proposicoes/3/autores").mock(
        return_value=httpx.Response(200, json={"dados": [{"nome": "Autor3"}]})
    )
    # Mock 500 nas outras proposições; se for chamado, teste falha.
    rota_1 = respx.get(f"{URL_BASE}/proposicoes/1").mock(return_value=httpx.Response(500))
    rota_2 = respx.get(f"{URL_BASE}/proposicoes/2").mock(return_value=httpx.Response(500))

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        dir_saida=saida,
        enriquecer_proposicoes=True,
    )
    cp = executar_coleta(params, home=home, bucket=_bucket_rapido())

    assert cp.proposicoes_enriquecidas == {1, 2, 3}
    assert rota_3.call_count == 1
    assert rota_1.call_count == 0
    assert rota_2.call_count == 0


def test_cli_flag_enriquecer_default_true() -> None:
    """Sem flag -> ``enriquecer_proposicoes`` é True por default."""
    runner = CliRunner()
    # Apenas valida que o param model fica True; rodar a CLI inteira exige rede.
    p = ParametrosColeta(legislaturas=[57], tipos=["proposicoes"], dir_saida=Path("/tmp/x"))
    assert p.enriquecer_proposicoes is True

    # E o ``--help`` deve listar a flag (typer pode quebrar a linha; verificamos
    # presença do prefixo distintivo).
    result = runner.invoke(app, ["coletar", "camara", "--help"])
    assert result.exit_code == 0
    # Typer renderiza com word-wrap; basta confirmar presença do nome da flag.
    saida_normalizada = "".join(result.stdout.split())
    assert "--enriquecer-proposicoes" in saida_normalizada or (
        "enriquecer-propos" in saida_normalizada
    )


def test_cli_flag_no_enriquecer_propaga_false() -> None:
    """``ParametrosColeta(enriquecer_proposicoes=False)`` desliga o ramo."""
    p = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        dir_saida=Path("/tmp/x"),
        enriquecer_proposicoes=False,
    )
    assert p.enriquecer_proposicoes is False


@respx.mock
def test_no_enriquecer_nao_gera_parquet_detalhe(tmp_path: Path) -> None:
    """``enriquecer_proposicoes=False`` -> não escreve ``proposicoes_detalhe.parquet``."""
    home = tmp_path / "hemiciclo"
    saida = tmp_path / "saida"

    respx.get(f"{URL_BASE}/proposicoes").mock(
        return_value=httpx.Response(
            200,
            json={
                "dados": [
                    {
                        "id": 10,
                        "siglaTipo": "PL",
                        "numero": 10,
                        "ano": 2024,
                        "ementa": "e10",
                    }
                ]
            },
        )
    )

    # Mock 500 em /proposicoes/10 -- se for chamado, falha.
    rota_det = respx.get(f"{URL_BASE}/proposicoes/10").mock(return_value=httpx.Response(500))

    params = ParametrosColeta(
        legislaturas=[57],
        tipos=["proposicoes"],
        max_itens=1,
        dir_saida=saida,
        enriquecer_proposicoes=False,
    )
    cp = executar_coleta(params, home=home, bucket=_bucket_rapido())

    assert cp.proposicoes_baixadas == {10}
    assert cp.proposicoes_enriquecidas == set()
    assert not (saida / "proposicoes_detalhe.parquet").exists()
    assert rota_det.call_count == 0


@pytest.mark.parametrize(
    "uri_value",
    [None, "", 0],
    ids=["none", "vazio", "zero"],
)
@respx.mock
def test_enriquecer_sem_uri_autores_autor_none(
    uri_value: object,
) -> None:
    """``uriAutores`` ausente/falsy -> ``autor_principal`` fica None sem chamada extra."""
    prop_id = 8888
    payload: dict[str, Any] = {
        "dados": {
            "id": prop_id,
            "siglaTipo": "PL",
            "ementa": "x",
            "temaOficial": "T",
            "uriAutores": uri_value,
        }
    }
    respx.get(f"{URL_BASE}/proposicoes/{prop_id}").mock(
        return_value=httpx.Response(200, json=payload)
    )

    det = enriquecer_proposicao(prop_id, bucket=_bucket_rapido())
    assert det["autor_principal"] is None
    assert det["tema_oficial"] == "T"
