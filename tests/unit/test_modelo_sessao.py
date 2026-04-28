"""Testes do modelo Pydantic da Sessão de Pesquisa (S23).

Cobre `ParametrosBusca`, `StatusSessao` e enums associados conforme spec
da Sprint S23 e plano R2 §5.4. Foco em invariantes, defaults e validações.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from hemiciclo.sessao.modelo import (
    UFS_BRASIL,
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
    StatusSessao,
)


def _params_minimos() -> dict[str, object]:
    """Retorna kwargs mínimos válidos para ``ParametrosBusca``."""
    return {
        "topico": "aborto",
        "casas": [Casa.CAMARA],
        "legislaturas": [57],
    }


# ---------------------------------------------------------------------------
# ParametrosBusca
# ---------------------------------------------------------------------------


def test_parametros_busca_topico_obrigatorio() -> None:
    """Tópico vazio ou só espaços levanta ``ValidationError``."""
    base = _params_minimos()

    with pytest.raises(ValidationError):
        ParametrosBusca(**{**base, "topico": ""})

    with pytest.raises(ValidationError):
        ParametrosBusca(**{**base, "topico": "   "})


def test_parametros_busca_camadas_default() -> None:
    """Default das camadas é regex + votos + embeddings; LLM desligada."""
    params = ParametrosBusca(**_params_minimos())
    assert params.camadas == [Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS]
    assert Camada.LLM not in params.camadas


def test_parametros_busca_casas_obrigatoria_pelo_menos_uma() -> None:
    """Lista de casas vazia falha (min_length=1)."""
    with pytest.raises(ValidationError):
        ParametrosBusca(**{**_params_minimos(), "casas": []})


def test_parametros_busca_legislatura_invalida() -> None:
    """Legislatura zero ou negativa é rejeitada."""
    with pytest.raises(ValidationError):
        ParametrosBusca(**{**_params_minimos(), "legislaturas": [0]})

    with pytest.raises(ValidationError):
        ParametrosBusca(**{**_params_minimos(), "legislaturas": [-1]})


def test_parametros_busca_uf_invalida() -> None:
    """UF fora da lista canônica é rejeitada."""
    with pytest.raises(ValidationError):
        ParametrosBusca(**{**_params_minimos(), "ufs": ["XX"]})


def test_parametros_busca_uf_normalizada_para_maiusculo() -> None:
    """UFs em minúsculo são normalizadas para maiúsculo."""
    params = ParametrosBusca(**{**_params_minimos(), "ufs": ["sp", "rj"]})
    assert params.ufs == ["SP", "RJ"]


def test_parametros_busca_max_itens_default_none() -> None:
    """Sem o campo ``max_itens``, a instância nasce com ``None`` (full)."""
    params = ParametrosBusca(**_params_minimos())
    assert params.max_itens is None


def test_parametros_busca_max_itens_valido_inteiro_positivo() -> None:
    """``max_itens=42`` é aceito e preservado no modelo (S30.1)."""
    params = ParametrosBusca(**_params_minimos(), max_itens=42)
    assert params.max_itens == 42


def test_parametros_busca_max_itens_zero_rejeitado() -> None:
    """``max_itens=0`` rejeitado por ``ge=1`` (alinhado a ``ParametrosColeta``)."""
    with pytest.raises(ValidationError):
        ParametrosBusca(**_params_minimos(), max_itens=0)


def test_parametros_busca_periodo_invertido() -> None:
    """data_inicio > data_fim é rejeitado."""
    base = _params_minimos()
    with pytest.raises(ValidationError):
        ParametrosBusca(
            **base,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2025, 1, 1),
        )


def test_ufs_brasil_tem_27_estados() -> None:
    """Constante canônica deve ter 27 UFs (26 estados + DF)."""
    assert len(UFS_BRASIL) == 27
    assert "DF" in UFS_BRASIL
    assert "SP" in UFS_BRASIL


def test_estado_sessao_enum_valores() -> None:
    """Enum ``EstadoSessao`` tem exatamente 9 valores literais (D7)."""
    assert {e.value for e in EstadoSessao} == {
        "criada",
        "coletando",
        "etl",
        "embeddings",
        "modelando",
        "concluida",
        "erro",
        "interrompida",
        "pausada",
    }


# ---------------------------------------------------------------------------
# StatusSessao
# ---------------------------------------------------------------------------


def _status_minimo() -> dict[str, object]:
    agora = datetime(2026, 4, 28, 12, 0, 0)
    return {
        "id": "aborto-camara",
        "estado": EstadoSessao.COLETANDO,
        "progresso_pct": 42.0,
        "etapa_atual": "Coletando votações da Câmara",
        "iniciada_em": agora,
        "atualizada_em": agora + timedelta(minutes=5),
    }


def test_status_sessao_progresso_clamp_lower() -> None:
    """progresso_pct < 0 levanta ``ValidationError``."""
    with pytest.raises(ValidationError):
        StatusSessao(**{**_status_minimo(), "progresso_pct": -0.1})


def test_status_sessao_progresso_clamp_upper() -> None:
    """progresso_pct > 100 levanta ``ValidationError``."""
    with pytest.raises(ValidationError):
        StatusSessao(**{**_status_minimo(), "progresso_pct": 100.1})


def test_status_sessao_atualizada_nao_pode_ser_anterior_a_iniciada() -> None:
    """Coerência temporal mínima é validada."""
    base = _status_minimo()
    base["atualizada_em"] = datetime(2026, 4, 28, 11, 59, 0)  # antes de iniciada
    with pytest.raises(ValidationError):
        StatusSessao(**base)


def test_serializacao_round_trip() -> None:
    """``model_dump_json`` -> ``model_validate_json`` preserva os campos."""
    params = ParametrosBusca(
        topico="reforma tributária",
        casas=[Casa.CAMARA, Casa.SENADO],
        legislaturas=[55, 56, 57],
        ufs=["SP", "RJ"],
        partidos=["PT", "PL"],
        data_inicio=date(2015, 1, 1),
        data_fim=date(2026, 4, 28),
        camadas=[Camada.REGEX, Camada.VOTOS],
        incluir_grafo=False,
    )
    serial = params.model_dump_json()
    restaurado = ParametrosBusca.model_validate_json(serial)
    assert restaurado == params

    status = StatusSessao(**_status_minimo())
    serial_status = status.model_dump_json()
    restaurado_status = StatusSessao.model_validate_json(serial_status)
    assert restaurado_status == status
