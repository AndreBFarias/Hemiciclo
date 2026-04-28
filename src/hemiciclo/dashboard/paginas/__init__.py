"""Páginas do dashboard Hemiciclo.

Cada página exporta uma função ``render(cfg: Configuracao) -> None`` chamada
pelo ``app.py`` conforme a aba ativa em ``st.session_state["pagina_ativa"]``.
"""
