"""Página de configuração de uma nova pesquisa.

Em S38.4 o botão ``Iniciar pesquisa`` passa a disparar o ``pipeline_real``
via :class:`hemiciclo.sessao.SessaoRunner` (S29 + S30) em subprocess
detached. O dashboard redireciona o usuário imediatamente para
``sessao_detalhe``, onde o polling de ``status.json`` acompanha o
progresso.
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

import streamlit as st
from loguru import logger
from pydantic import ValidationError

from hemiciclo.dashboard import componentes, tema
from hemiciclo.sessao import SessaoRunner
from hemiciclo.sessao.modelo import (
    UFS_BRASIL,
    Camada,
    Casa,
    ParametrosBusca,
)

if TYPE_CHECKING:
    from hemiciclo.config import Configuracao


_LEGISLATURAS_DISPONIVEIS = (55, 56, 57)

# Espelha ``cli.py:580`` -- rota canônica do pipeline real.
_PIPELINE_REAL_PATH = "hemiciclo.sessao.pipeline:pipeline_real"

# Tradução PT-BR para mensagens de erro de validação do Pydantic v2.
# Cobre os tipos de erro mais frequentes em ``ParametrosBusca``; quando
# o tipo não estiver mapeado, mantemos a mensagem original (que já é em
# inglês mas evita exibição vazia).
_TRADUCAO_ERRO_PYDANTIC: dict[str, str] = {
    "missing": "campo obrigatório não informado",
    "string_too_short": "texto muito curto",
    "string_too_long": "texto muito longo",
    "string_pattern_mismatch": "formato inválido",
    "value_error": "valor inválido",
    "type_error": "tipo inválido",
    "list_type": "deve ser uma lista",
    "list_too_short": "selecione ao menos um item",
    "enum": "valor fora das opções permitidas",
    "literal_error": "valor fora das opções permitidas",
    "datetime_parsing": "data inválida",
    "date_parsing": "data inválida",
    "less_than_equal": "valor acima do permitido",
    "greater_than_equal": "valor abaixo do permitido",
    "int_parsing": "deve ser um número inteiro",
    "float_parsing": "deve ser um número decimal",
}

_TRADUCAO_CAMPO: dict[str, str] = {
    "topico": "Tópico",
    "casas": "Casas legislativas",
    "legislaturas": "Legislaturas",
    "ufs": "Estados (UF)",
    "partidos": "Partidos",
    "data_inicio": "Período (início)",
    "data_fim": "Período (fim)",
    "camadas": "Camadas de análise",
}


def _traduzir_erro_pydantic(erro: dict[str, object]) -> tuple[str, str]:
    """Mapeia um erro do Pydantic v2 para campo + mensagem em PT-BR."""
    loc = erro.get("loc", ())
    campo_raw = ".".join(str(p) for p in loc) if isinstance(loc, tuple | list) else str(loc)
    campo = _TRADUCAO_CAMPO.get(campo_raw, campo_raw or "campo")
    tipo = str(erro.get("type", ""))
    mensagem = _TRADUCAO_ERRO_PYDANTIC.get(tipo)
    if mensagem is None:
        mensagem_original = erro.get("msg")
        mensagem = str(mensagem_original) if mensagem_original else "valor inválido"
    return campo, mensagem


def _slugify(texto: str) -> str:
    """Converte texto em slug ASCII seguro para nome de pasta."""
    base = texto.strip().lower()
    base = re.sub(r"[áàâã]", "a", base)
    base = re.sub(r"[éêè]", "e", base)
    base = re.sub(r"[íì]", "i", base)
    base = re.sub(r"[óôõò]", "o", base)
    base = re.sub(r"[úùü]", "u", base)
    base = re.sub(r"ç", "c", base)
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = base.strip("-")
    return base or "sem-topico"


def render(cfg: Configuracao) -> None:
    """Renderiza o formulário de nova pesquisa."""
    st.markdown("## Nova pesquisa")
    componentes.storytelling("nova_pesquisa")

    with st.form(key="form_nova_pesquisa", clear_on_submit=False):
        topico = st.text_input(
            "Tópico",
            placeholder="ex.: aborto, reforma tributária, desmatamento",
            help="Texto livre OU id de YAML curado em topicos/.",
        )

        col_a, col_b = st.columns(2)
        with col_a:
            casas_rotulos = st.multiselect(
                "Casas legislativas",
                options=["Câmara", "Senado"],
                default=["Câmara"],
                help="Ao menos uma casa precisa ser selecionada.",
                placeholder="Selecione...",
            )
        with col_b:
            legislaturas = st.multiselect(
                "Legislaturas",
                options=list(_LEGISLATURAS_DISPONIVEIS),
                default=[57],
                help="55 = 2015-2018; 56 = 2019-2022; 57 = 2023-2026.",
                placeholder="Selecione...",
            )

        col_c, col_d = st.columns(2)
        with col_c:
            ufs = st.multiselect(
                "Estados (UF)",
                options=list(UFS_BRASIL),
                default=[],
                help="Vazio = todas as 27 UFs.",
                placeholder="Selecione...",
            )
        with col_d:
            partidos = st.multiselect(
                "Partidos",
                options=list(tema.PARTIDOS_CANONICOS),
                default=[],
                help="Vazio = todos os partidos.",
                placeholder="Selecione...",
            )

        periodo = st.date_input(
            "Período",
            value=(date(2015, 1, 1), date(2026, 4, 28)),
            help="Janela de datas a considerar para discursos e proposições.",
        )

        camadas_rotulos = st.multiselect(
            "Camadas de análise",
            options=[
                "Regex/keywords (sempre confiável)",
                "Voto nominal (espinha dorsal)",
                "Embeddings semânticos (resgata implícitos)",
                "LLM opcional (anota nuance, custa horas)",
            ],
            default=[
                "Regex/keywords (sempre confiável)",
                "Voto nominal (espinha dorsal)",
                "Embeddings semânticos (resgata implícitos)",
            ],
            placeholder="Selecione...",
        )

        submetido = st.form_submit_button(
            "Iniciar pesquisa",
            type="primary",
            use_container_width=False,
        )

    if not submetido:
        return

    # Mapeamento dos rótulos de UI para enums Pydantic.
    casas_enum: list[Casa] = []
    if "Câmara" in casas_rotulos:
        casas_enum.append(Casa.CAMARA)
    if "Senado" in casas_rotulos:
        casas_enum.append(Casa.SENADO)

    camadas_enum: list[Camada] = []
    if "Regex/keywords (sempre confiável)" in camadas_rotulos:
        camadas_enum.append(Camada.REGEX)
    if "Voto nominal (espinha dorsal)" in camadas_rotulos:
        camadas_enum.append(Camada.VOTOS)
    if "Embeddings semânticos (resgata implícitos)" in camadas_rotulos:
        camadas_enum.append(Camada.EMBEDDINGS)
    if "LLM opcional (anota nuance, custa horas)" in camadas_rotulos:
        camadas_enum.append(Camada.LLM)

    if isinstance(periodo, tuple) and len(periodo) == 2:
        data_inicio, data_fim = periodo
    else:
        data_inicio, data_fim = None, None

    try:
        params = ParametrosBusca(
            topico=topico,
            casas=casas_enum,
            legislaturas=legislaturas,
            ufs=ufs or None,
            partidos=partidos or None,
            data_inicio=data_inicio,
            data_fim=data_fim,
            camadas=camadas_enum or [Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS],
        )
    except ValidationError as exc:
        st.error("Não foi possível iniciar a pesquisa. Confira os campos abaixo:")
        for erro in exc.errors():
            campo, mensagem = _traduzir_erro_pydantic(dict(erro))
            st.error(f"- **{campo}**: {mensagem}")
        return

    # Garante que ~/hemiciclo/sessoes/ existe (fresh-install do usuário).
    cfg.garantir_diretorios()

    # Constrói runner: cria pasta da sessão + grava params.json + status inicial.
    try:
        runner = SessaoRunner(cfg.home, params)
    except OSError as exc:
        logger.exception("Falha ao criar pasta da sessão")
        st.error(
            f"Não foi possível criar a sessão: {exc}. Verifique permissões em ~/hemiciclo/sessoes/."
        )
        return

    # Spawna subprocess detached do pipeline real.
    try:
        pid = runner.iniciar(_PIPELINE_REAL_PATH)
    except (OSError, FileNotFoundError) as exc:
        logger.exception("Falha ao spawnar subprocess do pipeline")
        st.error(f"Não foi possível iniciar o pipeline: {exc}.")
        return

    logger.info(
        "Sessão {id} iniciada via dashboard, pid={pid}",
        id=runner.id_sessao,
        pid=pid,
    )

    # Redireciona para a tela de polling (sessao_detalhe).
    st.session_state["sessao_id"] = runner.id_sessao
    st.session_state["pagina_ativa"] = "sessao_detalhe"
    st.rerun()
