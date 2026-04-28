"""Widget de ranking de convertibilidade prevista (S34).

Renderiza tabela ordenada por probabilidade de conversão prevista pelo
:class:`hemiciclo.modelos.convertibilidade.ModeloConvertibilidade`.

Layout:

- Cabeçalho com aviso "experimental" e link para o doc de caveats.
- Coluna ``proba`` com barra de progresso amarela-ouro proporcional.
- Tooltip nos coeficientes da regressão (proxy de SHAP) -- expandido
  abaixo da tabela em ``st.expander`` por questão de espaço.

Tolerância:

- ``scores_payload`` ``None`` -> ``st.info``.
- ``skipped=True`` -> ``st.info`` com motivo.
- Lista vazia -> ``st.info`` neutro.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from hemiciclo.dashboard import tema


def renderizar_ranking(
    scores_payload: dict[str, Any] | None,
    top_n: int = 50,
) -> None:
    """Renderiza tabela ranqueada por probabilidade de conversão prevista.

    Args:
        scores_payload: Dict carregado de ``convertibilidade_scores.json``
            com chaves ``skipped``, ``motivo``, ``scores``, ``metricas``,
            ``coeficientes``, ``feature_names``. ``None`` se ausente.
        top_n: Quantidade máxima de linhas exibidas (default 50).
    """
    if not scores_payload:
        st.info("Convertibilidade ainda não foi calculada para esta sessão.")
        return

    if scores_payload.get("skipped"):
        st.info("Convertibilidade ainda não disponível para esta sessão.")
        return

    scores_obj = scores_payload.get("scores") or []
    if not isinstance(scores_obj, list) or not scores_obj:
        st.info("Nenhum parlamentar ranqueado nesta sessão.")
        return

    metricas_obj = scores_payload.get("metricas") or {}
    metricas = metricas_obj if isinstance(metricas_obj, dict) else {}
    n_amostra = int(scores_payload.get("n_amostra", 0) or 0)

    # Cabeçalho com métricas + caveats curtos
    st.markdown(
        f"**Modelo treinado em {n_amostra} parlamentares.** "
        f"Acurácia: {float(metricas.get('accuracy', 0.0)):.2f} · "
        f"F1: {float(metricas.get('f1', 0.0)):.2f} · "
        f"ROC-AUC: {float(metricas.get('roc_auc', 0.0)):.2f}"
    )
    st.caption(
        "Modelo experimental e correlacional, não causal. "
        "Use com cautela e verifique o método na documentação do projeto."
    )

    linhas: list[dict[str, Any]] = []
    for entrada in scores_obj[:top_n]:
        if not isinstance(entrada, dict):
            continue
        nome = str(entrada.get("nome", entrada.get("parlamentar_id", "?")))
        casa = str(entrada.get("casa", "?"))
        proba = float(entrada.get("proba", 0.0) or 0.0)
        volat = float(entrada.get("indice_volatilidade", 0.0) or 0.0)
        linhas.append(
            {
                "Parlamentar": nome,
                "Casa": casa,
                "Probabilidade de conversão": proba,
                "Volatilidade histórica": volat,
            }
        )

    if not linhas:
        st.info("Lista de scores vazia após filtro.")
        return

    st.dataframe(
        linhas,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Probabilidade de conversão": st.column_config.ProgressColumn(
                "Probabilidade de conversão",
                help="Probabilidade prevista pela LogisticRegression (0..1)",
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
            ),
            "Volatilidade histórica": st.column_config.ProgressColumn(
                "Volatilidade histórica",
                help="Índice de volatilidade do parlamentar (0..1)",
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
            ),
        },
    )

    coefs_obj = scores_payload.get("coeficientes") or {}
    coefs = coefs_obj if isinstance(coefs_obj, dict) else {}
    if coefs:
        with st.expander("Coeficientes da regressão (interpretabilidade)"):
            st.caption(
                "Cada coeficiente mede o peso da feature no log-odds. "
                "Positivo = aumenta probabilidade prevista; negativo = diminui."
            )
            tabela_coefs = [{"Feature": str(k), "Coeficiente": float(v)} for k, v in coefs.items()]
            st.dataframe(tabela_coefs, use_container_width=True, hide_index=True)
            st.caption(
                f"Cor de destaque: amarelo-ouro {tema.AMARELO_OURO} "
                "(feature mais influente no ranqueamento)."
            )
