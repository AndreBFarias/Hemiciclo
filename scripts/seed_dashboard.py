"""Cria 3 sessões fake para validar a página de detalhe sem rodar pipeline.

Uso:
    uv run python scripts/seed_dashboard.py

As sessões geradas usam prefixo ``_seed_*`` para nunca colidirem com
sessões reais do usuário. Cada sessão tem ``params.json``, ``status.json``
e (quando aplicável) ``relatorio_state.json``, ``manifesto.json`` e
``classificacao_c1_c2.json``.

Cenários:

- ``_seed_concluida`` -- estado CONCLUIDA, com top a-favor/contra,
  manifesto e classificação completos.
- ``_seed_em_andamento`` -- estado COLETANDO 30%, sem relatório nem
  manifesto.
- ``_seed_erro`` -- estado ERRO com mensagem clara, sem relatório.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from loguru import logger

from hemiciclo.config import Configuracao
from hemiciclo.sessao.modelo import Camada, Casa, EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import salvar_params, salvar_status

# Ementas plausíveis sobre aborto -- sintéticas, mas com vocabulário real
# do tema (interrupção, gestação, atendimento, direitos reprodutivos).
# Hard-coded para determinismo do seed (S38.8).
_EMENTAS_SEED_ABORTO: tuple[dict[str, object], ...] = (
    {
        "id": 8001,
        "casa": "camara",
        "sigla": "PL",
        "numero": 1234,
        "ano": 2023,
        "ementa": (
            "Dispõe sobre a interrupção voluntária da gestação em casos de "
            "estupro, garantindo atendimento humanizado no SUS."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8002,
        "casa": "camara",
        "sigla": "PL",
        "numero": 2345,
        "ano": 2023,
        "ementa": (
            "Altera o Código Penal para tipificar a interrupção da gestação "
            "como crime contra a vida do feto."
        ),
        "tema_oficial": "Direito Penal",
    },
    {
        "id": 8003,
        "casa": "camara",
        "sigla": "PL",
        "numero": 3456,
        "ano": 2022,
        "ementa": (
            "Garante o acesso à interrupção legal da gestação em casos de risco à vida da gestante."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8004,
        "casa": "senado",
        "sigla": "PLS",
        "numero": 4567,
        "ano": 2024,
        "ementa": (
            "Estabelece pena para profissional de saúde que pratique aborto "
            "fora dos casos legais previstos no Código Penal."
        ),
        "tema_oficial": "Direito Penal",
    },
    {
        "id": 8005,
        "casa": "camara",
        "sigla": "PL",
        "numero": 5678,
        "ano": 2024,
        "ementa": (
            "Cria protocolo de atendimento à mulher em situação de violência "
            "sexual, incluindo orientação sobre direitos reprodutivos."
        ),
        "tema_oficial": "Direitos Humanos",
    },
    {
        "id": 8006,
        "casa": "camara",
        "sigla": "PL",
        "numero": 6789,
        "ano": 2023,
        "ementa": (
            "Institui campanha nacional sobre direitos reprodutivos e saúde "
            "sexual da mulher na rede pública."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8007,
        "casa": "senado",
        "sigla": "PLS",
        "numero": 7890,
        "ano": 2022,
        "ementa": (
            "Proíbe o aborto em qualquer hipótese, exceto risco iminente de "
            "morte da gestante comprovado por junta médica."
        ),
        "tema_oficial": "Direito Penal",
    },
    {
        "id": 8008,
        "casa": "camara",
        "sigla": "PL",
        "numero": 8901,
        "ano": 2023,
        "ementa": (
            "Garante atendimento psicológico e jurídico à mulher vítima de "
            "violência sexual com gestação resultante."
        ),
        "tema_oficial": "Direitos Humanos",
    },
    {
        "id": 8009,
        "casa": "camara",
        "sigla": "PEC",
        "numero": 9012,
        "ano": 2024,
        "ementa": (
            "Reconhece o direito à vida desde a concepção, vedando a "
            "interrupção voluntária da gestação."
        ),
        "tema_oficial": "Direitos Humanos",
    },
    {
        "id": 8010,
        "casa": "senado",
        "sigla": "PLS",
        "numero": 1023,
        "ano": 2024,
        "ementa": (
            "Regula a oferta de contracepção de emergência na atenção "
            "primária e em serviços de saúde reprodutiva."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8011,
        "casa": "camara",
        "sigla": "PL",
        "numero": 1124,
        "ano": 2022,
        "ementa": (
            "Garante licença remunerada à mulher em recuperação de aborto "
            "espontâneo no serviço público."
        ),
        "tema_oficial": "Trabalho",
    },
    {
        "id": 8012,
        "casa": "camara",
        "sigla": "PL",
        "numero": 1225,
        "ano": 2023,
        "ementa": (
            "Determina notificação compulsória de casos de violência sexual "
            "com gestação a órgãos de proteção."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8013,
        "casa": "senado",
        "sigla": "PLS",
        "numero": 1326,
        "ano": 2024,
        "ementa": (
            "Cria política nacional de planejamento familiar com foco em "
            "direitos reprodutivos e saúde da mulher."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8014,
        "casa": "camara",
        "sigla": "PL",
        "numero": 1427,
        "ano": 2023,
        "ementa": (
            "Estabelece diretrizes para o atendimento integral à gestante em "
            "situação de aborto legal pelo SUS."
        ),
        "tema_oficial": "Saúde",
    },
    {
        "id": 8015,
        "casa": "camara",
        "sigla": "PL",
        "numero": 1528,
        "ano": 2022,
        "ementa": (
            "Garante a presença de acompanhante e atendimento humanizado "
            "durante interrupção legal da gestação."
        ),
        "tema_oficial": "Saúde",
    },
)
"""15 ementas sintéticas sobre aborto. Determinístico por construção."""

# Lista canônica de parlamentares fake. Nomes inspirados em mockups
# do plano R2 -- nenhuma correspondência com pessoas reais é intencional.
_FAVORAVEIS = [
    {"id": 1001, "nome": "Sâmia Bomfim", "partido": "PSOL", "uf": "SP"},
    {"id": 1002, "nome": "Talíria Petrone", "partido": "PSOL", "uf": "RJ"},
    {"id": 1003, "nome": "Erika Hilton", "partido": "PSOL", "uf": "SP"},
    {"id": 1004, "nome": "Maria do Rosário", "partido": "PT", "uf": "RS"},
    {"id": 1005, "nome": "Benedita da Silva", "partido": "PT", "uf": "RJ"},
    {"id": 1006, "nome": "Ivan Valente", "partido": "PSOL", "uf": "SP"},
    {"id": 1007, "nome": "Glauber Braga", "partido": "PSOL", "uf": "RJ"},
    {"id": 1008, "nome": "Jandira Feghali", "partido": "PCdoB", "uf": "RJ"},
]

_CONTRARIOS = [
    {"id": 2001, "nome": "Eros Biondini", "partido": "PL", "uf": "MG"},
    {"id": 2002, "nome": "Sóstenes Cavalcante", "partido": "PL", "uf": "RJ"},
    {"id": 2003, "nome": "Cabo Gilberto Silva", "partido": "PL", "uf": "PB"},
    {"id": 2004, "nome": "Magno Malta", "partido": "PL", "uf": "ES"},
    {"id": 2005, "nome": "Gilberto Nascimento", "partido": "PSC", "uf": "SP"},
    {"id": 2006, "nome": "Marcel Van Hattem", "partido": "NOVO", "uf": "RS"},
    {"id": 2007, "nome": "Diego Garcia", "partido": "REPUBLICANOS", "uf": "PR"},
    {"id": 2008, "nome": "Pastor Marco Feliciano", "partido": "PL", "uf": "SP"},
]


def _gerar_top(parlamentares: list[dict[str, object]], a_favor: bool) -> list[dict[str, object]]:
    """Gera lista ranqueada de parlamentares com scores plausíveis."""
    rng = random.Random(42)  # determinismo (I3) -- seed fixa
    saida: list[dict[str, object]] = []
    for i, parl in enumerate(parlamentares):
        if a_favor:
            score = max(0.70, 0.99 - 0.02 * i + rng.uniform(-0.01, 0.01))
        else:
            score = min(0.30, 0.05 + 0.02 * i + rng.uniform(-0.01, 0.01))
        intensidade = max(0.05, min(0.95, rng.uniform(0.3, 0.85)))
        linha = {
            **parl,
            "proporcao_sim": round(score, 4),
            "posicao": round(score, 4),
            "intensidade": round(intensidade, 4),
        }
        saida.append(linha)
    return saida


def _params_aborto() -> ParametrosBusca:
    """ParametrosBusca canônicos pro tópico de aborto, recorte 57ª legislatura."""
    return ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        ufs=None,
        partidos=None,
        data_inicio=None,
        data_fim=None,
        camadas=[Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS],
    )


def _criar_sessao_concluida(home: Path) -> Path:
    """Cria ``_seed_concluida`` com todos os artefatos preenchidos."""
    sessao_id = "_seed_concluida"
    pasta = home / "sessoes" / sessao_id
    pasta.mkdir(parents=True, exist_ok=True)

    params = _params_aborto()
    salvar_params(params, pasta / "params.json")

    agora = datetime.now(UTC)
    status = StatusSessao(
        id=sessao_id,
        estado=EstadoSessao.CONCLUIDA,
        progresso_pct=100.0,
        etapa_atual="concluida",
        mensagem="Pipeline real concluído (seed)",
        iniciada_em=agora,
        atualizada_em=agora,
        pid=None,
        erro=None,
    )
    salvar_status(status, pasta / "status.json")

    top_a_favor = _gerar_top(_FAVORAVEIS, a_favor=True)
    top_contra = _gerar_top(_CONTRARIOS, a_favor=False)
    relatorio = {
        "topico": params.topico,
        "casas": [c.value for c in params.casas],
        "legislaturas": list(params.legislaturas),
        "camadas_solicitadas": [c.value for c in params.camadas],
        "n_props": 87,
        "n_parlamentares": 513,
        "top_a_favor": top_a_favor,
        "top_contra": top_contra,
        "c3": {"skipped": True, "motivo": "bge-m3 não baixado nesta seed"},
        "gerado_em": agora.isoformat(),
        "parametros": params.model_dump(mode="json"),
    }
    (pasta / "relatorio_state.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cache_parquet_path = pasta / "cache_seed.parquet"
    # S38.8: grava parquet com ementas sintéticas. Antes apenas o path
    # era apontado, mas o arquivo nunca era criado -- a página de detalhe
    # caía no fallback "Sem ementas" e a word cloud antiga vazava nomes.
    pl.DataFrame(list(_EMENTAS_SEED_ABORTO)).write_parquet(cache_parquet_path)

    classif = {
        "n_props": 87,
        "n_parlamentares": 513,
        "top_a_favor": top_a_favor,
        "top_contra": top_contra,
        "cache_parquet": str(cache_parquet_path),
    }
    (pasta / "classificacao_c1_c2.json").write_text(
        json.dumps(classif, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifesto = {
        "criado_em": agora.isoformat(),
        "versao_pipeline": "1",
        "artefatos": {
            "params.json": "0000000000000000",
            "status.json": "1111111111111111",
            "relatorio_state.json": "2222222222222222",
            "classificacao_c1_c2.json": "3333333333333333",
        },
        "limitacoes_conhecidas": ["S24b", "S24c", "S25.3", "S27.1"],
    }
    (pasta / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return pasta


def _criar_sessao_em_andamento(home: Path) -> Path:
    """Cria ``_seed_em_andamento`` parada na coleta a 30%."""
    sessao_id = "_seed_em_andamento"
    pasta = home / "sessoes" / sessao_id
    pasta.mkdir(parents=True, exist_ok=True)

    params = ParametrosBusca(
        topico="porte_armas",
        casas=[Casa.CAMARA, Casa.SENADO],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS],
    )
    salvar_params(params, pasta / "params.json")

    agora = datetime.now(UTC)
    status = StatusSessao(
        id=sessao_id,
        estado=EstadoSessao.COLETANDO,
        progresso_pct=30.0,
        etapa_atual="coleta_camara",
        mensagem="Coletando proposições da Câmara (página 12 de 47)",
        iniciada_em=agora,
        atualizada_em=agora,
        pid=12345,
        erro=None,
    )
    salvar_status(status, pasta / "status.json")
    return pasta


def _criar_sessao_erro(home: Path) -> Path:
    """Cria ``_seed_erro`` com mensagem clara de falha."""
    sessao_id = "_seed_erro"
    pasta = home / "sessoes" / sessao_id
    pasta.mkdir(parents=True, exist_ok=True)

    params = ParametrosBusca(
        topico="marco_temporal",
        casas=[Casa.CAMARA],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS],
    )
    salvar_params(params, pasta / "params.json")

    agora = datetime.now(UTC)
    status = StatusSessao(
        id=sessao_id,
        estado=EstadoSessao.ERRO,
        progresso_pct=15.0,
        etapa_atual="erro",
        mensagem="HTTPError: 503 Service Unavailable em /proposicoes",
        iniciada_em=agora,
        atualizada_em=agora,
        pid=None,
        erro="HTTPError: 503 Service Unavailable em /proposicoes",
    )
    salvar_status(status, pasta / "status.json")
    return pasta


def main() -> int:
    """Cria 3 sessões fake e imprime o caminho de cada uma."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    home = cfg.home

    pastas = [
        _criar_sessao_concluida(home),
        _criar_sessao_em_andamento(home),
        _criar_sessao_erro(home),
    ]
    logger.info("seed_dashboard: {n} sessões sintéticas criadas em {p}", n=len(pastas), p=home)
    for p in pastas:
        sys.stdout.write(f"{p}\n")
    sys.stdout.write(f"seed_dashboard: {len(pastas)} sessões sintéticas criadas em {home}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
