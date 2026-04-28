"""Widgets reutilizáveis do dashboard Hemiciclo (S31).

Cada módulo aqui expõe uma função ``renderizar_*`` que recebe os dados já
no formato pronto e desenha o componente via Streamlit. Sem leitura de
disco, sem chamadas de rede, sem lógica de negócio.

Convenção: o widget nunca "sabe" da estrutura da página -- só dos dados
que recebe. A página em ``dashboard/paginas/sessao_detalhe.py`` decide o
quê e quando renderizar.
"""

from __future__ import annotations
