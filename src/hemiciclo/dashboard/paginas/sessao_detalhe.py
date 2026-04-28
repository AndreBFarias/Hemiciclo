"""Página de detalhe da sessão (S31).

Renderiza relatório multidimensional a partir dos artefatos JSON
produzidos pelo ``pipeline_real`` da S30:

- ``params.json`` -- :class:`ParametrosBusca` da sessão
- ``status.json`` -- :class:`StatusSessao` (polling em sessões em andamento)
- ``relatorio_state.json`` -- ``top_a_favor``, ``top_contra``, ``n_props``,
  ``n_parlamentares``, ``c3``
- ``manifesto.json`` -- ``criado_em``, ``versao_pipeline``, ``artefatos`` e
  ``limitacoes_conhecidas``
- ``classificacao_c1_c2.json`` -- detalhe bruto da classificação

Tolerante a artefato ausente: pipeline parado no meio mostra estado
disponível + aviso. Estado ``concluida`` mostra widgets ricos. Estado em
andamento mostra ``progresso_sessao`` com polling 2s. Estado de erro ou
interrompida mostra mensagem clara + botão de retomar.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger

from hemiciclo.dashboard import componentes, tema
from hemiciclo.dashboard.widgets import (
    heatmap_hipocrisia,
    progresso_sessao,
    radar_assinatura,
    ranking_convertibilidade,
    rede,
    timeline_conversao,
    top_pro_contra,
    word_cloud,
)
from hemiciclo.sessao.modelo import EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    carregar_params,
    carregar_status,
)

if TYPE_CHECKING:
    from hemiciclo.config import Configuracao


# Polling: a cada 2 s a página relê status.json. Sai do loop assim que
# o estado entra em terminal.
INTERVALO_POLLING_S = 2.0
ESTADOS_TERMINAIS_UI = {
    EstadoSessao.CONCLUIDA,
    EstadoSessao.ERRO,
    EstadoSessao.INTERROMPIDA,
    EstadoSessao.PAUSADA,
}


def _carregar_json(path: Path) -> dict[str, Any] | None:
    """Lê JSON de ``path`` retornando ``None`` se ausente/corrompido."""
    if not path.is_file():
        return None
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("artefato corrompido em {p}: {e}", p=path, e=exc)
        return None


def _renderizar_header_sessao(
    sessao_id: str,
    sessao_dir: Path,
    params: ParametrosBusca,
    status: StatusSessao | None,
    relatorio: dict[str, Any] | None,
) -> None:
    """Renderiza o header com tópico, casas, período, estado e botões."""
    col_voltar, col_titulo, col_export = st.columns([1, 6, 1])
    with col_voltar:
        if st.button("← Voltar", key="sessao_detalhe_voltar"):
            st.session_state["pagina_ativa"] = "lista_sessoes"
            st.rerun()
    with col_titulo:
        casas_str = ", ".join(c.value for c in params.casas)
        ufs_str = ", ".join(params.ufs) if params.ufs else "todas"
        leg_str = ", ".join(str(n) for n in params.legislaturas)
        estado_str = status.estado.value if status is not None else "desconhecido"
        st.markdown(
            f"## {params.topico}  "
            f"<span style='font-size:0.9rem; color:{tema.CINZA_PEDRA}; "
            f"opacity:0.7;'>({estado_str})</span>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Casas: {casas_str} · UFs: {ufs_str} · Legislaturas: {leg_str} · Sessão: `{sessao_id}`"
        )
    with col_export:
        from hemiciclo.sessao.exportador import exportar_zip_bytes

        try:
            zip_bytes = exportar_zip_bytes(sessao_dir)
        except FileNotFoundError as exc:
            logger.warning("export bytes falhou em {p}: {e}", p=sessao_dir, e=exc)
            zip_bytes = b""
        st.download_button(
            label="Exportar zip",
            data=zip_bytes,
            file_name=f"{sessao_id}.zip",
            mime="application/zip",
            key="sessao_detalhe_export_zip",
            disabled=not zip_bytes,
            help="Baixa zip portável (sem dados.duckdb e sem modelos_locais)",
        )

    if relatorio is not None:
        n_props = int(relatorio.get("n_props", 0) or 0)
        n_parl = int(relatorio.get("n_parlamentares", 0) or 0)
        st.markdown(
            f"<p class='hemiciclo-storytelling'><strong>{n_props}</strong> "
            f"proposições analisadas · <strong>{n_parl}</strong> "
            f"parlamentares ranqueados</p>",
            unsafe_allow_html=True,
        )


def _renderizar_concluida(
    relatorio: dict[str, Any],
    manifesto: dict[str, Any] | None,
    topico: str,
    sessao_dir: Path | None = None,
) -> None:
    """Renderiza widgets ricos para sessão concluída."""
    top_a_favor = list(relatorio.get("top_a_favor", []) or [])
    top_contra = list(relatorio.get("top_contra", []) or [])

    st.markdown("### Quem está mais a favor, quem está mais contra")
    top_pro_contra.renderizar_top(top_a_favor, top_contra, top_n=100)

    st.markdown("### Assinatura multidimensional")
    st.caption(
        "Cada eixo é uma dimensão do perfil. Eixos marcados como "
        "'(em breve)' ainda estão em desenvolvimento."
    )
    radar_assinatura.renderizar_radar(top_a_favor + top_contra, top_n=20)

    st.markdown("### Heatmap parlamentar × tópico")
    heatmap_hipocrisia.renderizar_heatmap(
        top_a_favor + top_contra,
        topico=topico,
        top_n=50,
    )

    st.markdown("### Vocabulário das proposições analisadas")
    st.caption(
        "Termos extraídos por TF-IDF das ementas das proposições do tópico. "
        "Não representa fala de parlamentar individual."
    )
    _renderizar_word_cloud_topico(sessao_dir)

    if sessao_dir is not None:
        _renderizar_secao_redes(sessao_dir)
        _renderizar_secao_historico(sessao_dir)
        _renderizar_secao_convertibilidade(sessao_dir)

    if manifesto is not None:
        limitacoes = list(manifesto.get("limitacoes_conhecidas", []) or [])
        if limitacoes:
            st.markdown("### Limitações conhecidas desta versão")
            st.markdown(
                "Esta versão tem limites conhecidos: histórico de votação "
                "ainda não filtrado por tópico; redes de coautoria usam "
                "aproximação por co-votação; convertibilidade é experimental."
            )


def _renderizar_word_cloud_topico(sessao_dir: Path | None) -> None:
    """Renderiza word cloud do tópico a partir do ``cache_parquet`` (S38.8).

    Lê o caminho do parquet em ``classificacao_c1_c2.json`` e extrai
    palavras-chave das ementas via TF-IDF. Antes da S38.8 esta seção
    passava ``nome`` do parlamentar como corpus, o que vazava nomes
    próprios para a nuvem -- bug ético reportado no smoke real v2.1.0.

    Tolerante a artefatos ausentes: parquet inexistente, vazio, ou sem
    coluna ``ementa`` cai no fallback ``st.info`` -- não quebra a página.
    """
    if sessao_dir is None:
        return

    classif = _carregar_json(sessao_dir / "classificacao_c1_c2.json")
    cache_path_str = (classif or {}).get("cache_parquet")
    if not cache_path_str:
        st.info("Sem ementas suficientes para vocabulário do tópico.")
        return

    cache_path = Path(str(cache_path_str))
    if not cache_path.is_file():
        st.info("Sem ementas suficientes para vocabulário do tópico.")
        return

    try:
        # Lazy import: só pesa o boot se realmente houver cache.
        import polars as pl_local  # noqa: PLC0415

        df = pl_local.read_parquet(cache_path)
    except (OSError, ValueError) as exc:
        logger.warning("falha ao ler cache_parquet em {p}: {e}", p=cache_path, e=exc)
        st.info("Sem ementas suficientes para vocabulário do tópico.")
        return

    if "ementa" not in df.columns or len(df) == 0:
        st.info("Sem ementas suficientes para vocabulário do tópico.")
        return

    ementas = [str(e) for e in df["ementa"].fill_null("").to_list() if e]
    termos = word_cloud.extrair_palavras_chave_de_ementas(ementas, top_n=50, min_df=2)
    if not termos:
        st.info("Sem ementas suficientes para vocabulário do tópico.")
        return

    # Reconstrói "corpus" repetindo cada termo na proporção do peso.
    # ``renderizar_word_cloud`` recebe ``list[str]`` -- API estável.
    corpus_pesado = [termo for termo, peso in termos for _ in range(max(1, int(round(peso * 10))))]
    word_cloud.renderizar_word_cloud(
        corpus_pesado,
        titulo="Vocabulário derivado de TF-IDF das ementas do tópico",
        cor_dominante=tema.AZUL_HEMICICLO,
    )


def _renderizar_secao_redes(sessao_dir: Path) -> None:
    """Renderiza a seção 'Redes de coautoria e voto' com 3 tabs (S32).

    Tabs:
    - Coautoria: ``grafo_coautoria.html`` embedado
    - Voto: ``grafo_voto.html`` embedado
    - Métricas: tabela com top 10 mais centrais por tipo

    Tolerante a artefatos ausentes (sessão antiga, pipeline parcial, ou
    SKIPPED graceful por amostra insuficiente). Cada tab decide sozinha
    se mostra dado ou aviso.
    """
    st.markdown("### Redes de coautoria e voto")
    st.caption(
        "Quem articula com quem. Coautoria = votar nas mesmas votações. "
        "Voto = afinidade de posição (SIM/NÃO/ABSTENÇÃO)."
    )
    metricas_path = sessao_dir / "metricas_rede.json"
    metricas = _carregar_json(metricas_path)

    tab_co, tab_voto, tab_metricas = st.tabs(["Coautoria", "Voto", "Métricas"])
    with tab_co:
        rede.renderizar_rede(sessao_dir / "grafo_coautoria.html")
        if metricas is not None:
            _exibir_status_grafo(dict(metricas.get("coautoria", {}) or {}))
    with tab_voto:
        rede.renderizar_rede(sessao_dir / "grafo_voto.html")
        if metricas is not None:
            _exibir_status_grafo(dict(metricas.get("voto", {}) or {}))
    with tab_metricas:
        if metricas is None:
            st.info("Métricas de rede ainda não geradas para esta sessão.")
            return
        for rotulo, chave in (("Coautoria", "coautoria"), ("Voto", "voto")):
            bloco = dict(metricas.get(chave, {}) or {})
            st.markdown(f"#### {rotulo}")
            if bloco.get("skipped"):
                st.info("Análise ainda não disponível para esta sessão.")
                continue
            st.markdown(
                f"- Nós: **{bloco.get('n_nos', 0)}** "
                f"· Arestas: **{bloco.get('n_arestas', 0)}** "
                f"· Maior componente: **{bloco.get('maior_componente', 0)}** "
                f"· Comunidades: **{bloco.get('n_comunidades', 0)}**"
            )
            top = list(bloco.get("top_centrais", []) or [])
            if top:
                st.dataframe(top, use_container_width=True)


def _exibir_status_grafo(bloco: dict[str, Any]) -> None:
    """Mostra resumo curto do status (indisponível ou contagem de nós)."""
    if bloco.get("skipped"):
        st.caption("Análise ainda não disponível para esta sessão.")
    else:
        st.caption(
            f"Nós: {bloco.get('n_nos', 0)} · Arestas: {bloco.get('n_arestas', 0)} "
            f"· Comunidades: {bloco.get('n_comunidades', 0)}"
        )


def _renderizar_secao_historico(sessao_dir: Path) -> None:
    """Renderiza seção 'Histórico de conversão' (S33).

    Lê ``<sessao_dir>/historico_conversao.json`` (gerado pelo
    ``_etapa_historico`` da S33) e oferece selectbox dos top 20
    parlamentares mais voláteis, renderizando timeline Plotly do
    parlamentar selecionado.

    Tolerante a:

    - Arquivo ausente (sessão antiga, pipeline parcial) -> ``st.info``.
    - JSON corrompido -> ``st.warning``.
    - SKIPPED graceful (sem dados.duckdb / sem votos) -> ``st.info``
      com motivo.
    """
    st.markdown("### Histórico de conversão")
    st.caption(
        "Como cada parlamentar evoluiu sua posição ao longo dos anos. "
        "Mudanças >= 30 pontos percentuais aparecem destacadas. "
        "Limite atual: histórico geral do parlamentar (todas as votações), "
        "ainda não filtrado pelo tópico desta sessão."
    )
    historico_path = sessao_dir / "historico_conversao.json"
    historico = _carregar_json(historico_path)

    if historico is None:
        st.info("Histórico de conversão ainda não foi calculado para esta sessão.")
        return

    metadata_obj = historico.get("metadata") or {}
    metadata = metadata_obj if isinstance(metadata_obj, dict) else {}
    if metadata.get("skipped"):
        st.info("Histórico ainda não disponível para esta sessão.")
        return

    parlamentares_obj = historico.get("parlamentares") or {}
    parlamentares = parlamentares_obj if isinstance(parlamentares_obj, dict) else {}
    if not parlamentares:
        st.info("Nenhum parlamentar com 2+ buckets temporais nesta sessão.")
        return

    # Top 20 mais voláteis -- ordenação desc por indice_volatilidade.
    pares: list[tuple[str, dict[str, Any]]] = [
        (str(pid), bloco) for pid, bloco in parlamentares.items() if isinstance(bloco, dict)
    ]
    pares.sort(
        key=lambda kv: float(kv[1].get("indice_volatilidade", 0.0) or 0.0),
        reverse=True,
    )
    top_voláteis = pares[:20]

    rotulos = {
        pid: (
            f"{bloco.get('nome', pid)} "
            f"(volatilidade={float(bloco.get('indice_volatilidade', 0.0) or 0.0):.2f})"
        )
        for pid, bloco in top_voláteis
    }
    ids_ordenados = [pid for pid, _ in top_voláteis]
    selecionado = st.selectbox(
        "Top 20 parlamentares mais voláteis",
        options=ids_ordenados,
        format_func=lambda pid: rotulos.get(pid, str(pid)),
        key="historico_select_parlamentar",
        placeholder="Selecione...",
    )
    if selecionado is None:
        return

    bloco_obj = parlamentares.get(selecionado) or {}
    bloco = bloco_obj if isinstance(bloco_obj, dict) else {}
    mudancas_obj = bloco.get("mudancas_detectadas") or []
    mudancas = mudancas_obj if isinstance(mudancas_obj, list) else []
    timeline_conversao.renderizar_timeline_conversao(historico, parlamentar_id=selecionado)
    if mudancas:
        st.markdown(f"**{len(mudancas)} mudança(s) detectada(s) (>= 30pp):**")
        for evento in mudancas:
            if not isinstance(evento, dict):
                continue
            anterior = evento.get("bucket_anterior", "?")
            posterior = evento.get("bucket_posterior", "?")
            delta = float(evento.get("delta_pp", 0.0) or 0.0)
            sinal = "+" if delta >= 0 else ""
            posicao_a = evento.get("posicao_anterior", "?")
            posicao_p = evento.get("posicao_posterior", "?")
            st.markdown(
                f"- **{anterior} -> {posterior}**: "
                f"{sinal}{delta:.0f}pp "
                f"({posicao_a} -> {posicao_p})"
            )


def _renderizar_secao_convertibilidade(sessao_dir: Path) -> None:
    """Renderiza seção 'Convertibilidade prevista (experimental)' (S34).

    Lê ``<sessao_dir>/convertibilidade_scores.json`` (gerado pela
    ``_etapa_convertibilidade`` da S34) e delega ao widget
    :func:`hemiciclo.dashboard.widgets.ranking_convertibilidade.renderizar_ranking`.

    Banner inicial é honesto sobre limitações metodológicas (manifesto
    do projeto: rigor científico publicizado, sem maquiagem).

    Tolerante a:

    - Arquivo ausente (sessão antiga, pipeline parcial / flag desligada).
    - JSON corrompido.
    - SKIPPED graceful (amostra insuficiente / sem features).
    """
    st.markdown("### Convertibilidade prevista (experimental)")
    st.caption(
        "Probabilidade de mudar de posição em votações futuras. "
        "Modelo experimental e correlacional, não causal."
    )
    scores_path = sessao_dir / "convertibilidade_scores.json"
    payload = _carregar_json(scores_path)
    ranking_convertibilidade.renderizar_ranking(payload, top_n=50)


def _renderizar_em_andamento(
    sessao_dir: Path,
    status: StatusSessao,
) -> None:
    """Renderiza progresso com polling 2 s até o estado virar terminal."""
    placeholder = st.empty()
    status_corrente: StatusSessao = status

    # Loop de polling: cada iteração relê status.json. Em estado terminal,
    # rerun pra cair no caminho concluida/erro acima.
    while status_corrente.estado not in ESTADOS_TERMINAIS_UI:
        with placeholder.container():
            progresso_sessao.renderizar_progresso(
                status_corrente,
                etapa_atual=status_corrente.etapa_atual,
                mensagem=status_corrente.mensagem,
                eta_segundos=None,
            )
        time.sleep(INTERVALO_POLLING_S)
        novo = carregar_status(sessao_dir / "status.json")
        if novo is None:
            with placeholder.container():
                st.error(
                    "Status da sessão não encontrado. Pode ter sido deletado "
                    "manualmente ou a sessão acabou de ser criada."
                )
            return
        status_corrente = novo

    # Saiu do loop -- força rerun pra recarregar a página inteira.
    st.rerun()


def _renderizar_erro_ou_interrompida(
    sessao_id: str,
    status: StatusSessao,
) -> None:
    """Renderiza mensagem clara + botões de ação para estados não-terminais ok."""
    if status.estado == EstadoSessao.ERRO:
        st.error(
            f"Erro na sessão `{sessao_id}`: "
            f"{status.erro or status.mensagem or 'mensagem não disponível'}"
        )
    elif status.estado == EstadoSessao.INTERROMPIDA:
        st.warning(
            f"Sessão `{sessao_id}` foi interrompida (kill externo ou processo "
            "morto sem update). Você pode retomar de onde parou."
        )
    elif status.estado == EstadoSessao.PAUSADA:
        st.info(f"Sessão `{sessao_id}` está pausada. Use 'retomar' para continuar.")
    col_a, col_b, _ = st.columns([1, 1, 4])
    with col_a:
        if st.button("Retomar pesquisa", key="sessao_detalhe_retomar"):
            st.info("Retomada estará disponível em breve.")
    with col_b:
        if st.button("Voltar à lista", key="sessao_detalhe_voltar_erro"):
            st.session_state["pagina_ativa"] = "lista_sessoes"
            st.rerun()


def render(cfg: Configuracao) -> None:
    """Renderiza a página de detalhe da sessão.

    Lê ``st.session_state["sessao_id"]``. Se ausente, mostra link de volta
    para a lista. Toda a I/O é tolerante a falhas: artefato ausente vira
    aviso, JSON corrompido idem.
    """
    sessao_id = st.session_state.get("sessao_id")
    if not sessao_id:
        st.warning("Nenhuma sessão selecionada. Volte para a lista de pesquisas.")
        if st.button("Voltar à lista", key="sessao_detalhe_sem_id"):
            st.session_state["pagina_ativa"] = "lista_sessoes"
            st.rerun()
        return

    sessao_dir = caminho_sessao(cfg.home, str(sessao_id))
    if not sessao_dir.is_dir():
        st.error(f"Sessão `{sessao_id}` não encontrada em `{sessao_dir}`.")
        if st.button("Voltar à lista", key="sessao_detalhe_inexistente"):
            st.session_state["pagina_ativa"] = "lista_sessoes"
            st.rerun()
        return

    componentes.storytelling("sessao_detalhe")

    params = carregar_params(sessao_dir / "params.json")
    if params is None:
        st.error(
            f"`params.json` ausente ou corrompido em `{sessao_dir}`. Sessão não pode ser exibida."
        )
        return

    status = carregar_status(sessao_dir / "status.json")
    relatorio = _carregar_json(sessao_dir / "relatorio_state.json")
    manifesto = _carregar_json(sessao_dir / "manifesto.json")

    _renderizar_header_sessao(str(sessao_id), sessao_dir, params, status, relatorio)

    if status is None:
        st.warning(
            "`status.json` ainda não foi gravado. A sessão pode estar "
            "iniciando -- recarregue em alguns segundos."
        )
        return

    if status.estado == EstadoSessao.CONCLUIDA:
        if relatorio is None:
            st.warning(
                "Sessão marcada como concluída mas `relatorio_state.json` "
                "está ausente. Verifique o log da sessão."
            )
            return
        _renderizar_concluida(relatorio, manifesto, params.topico, sessao_dir)
        return

    if status.estado in {EstadoSessao.ERRO, EstadoSessao.INTERROMPIDA, EstadoSessao.PAUSADA}:
        _renderizar_erro_ou_interrompida(str(sessao_id), status)
        return

    # Caso contrário a sessão está em andamento (CRIADA, COLETANDO, ETL,
    # EMBEDDINGS, MODELANDO). Faz polling.
    _renderizar_em_andamento(sessao_dir, status)
