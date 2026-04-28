"""Design tokens do dashboard Hemiciclo (plano R2 §10.2).

Paleta inspirada em institucional sóbrio (não-partidária). Inter como
tipografia primária, JetBrains Mono para código. Storytelling por aba
no espírito do projeto referência ``stilingue-energisa-etl``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

AZUL_HEMICICLO = "#1E3A5F"  # primary
AZUL_CLARO = "#4A7BAB"  # primary-light
AMARELO_OURO = "#D4A537"  # accent (Brasil sem ser kitsch)
VERDE_FOLHA = "#3D7A3D"  # success / a-favor
VERMELHO_ARGILA = "#A8403A"  # danger / contra
CINZA_PEDRA = "#4A4A4A"  # neutral-strong
CINZA_AREIA = "#E8E4D8"  # neutral-light bg
BRANCO_OSSO = "#FAF8F3"  # bg principal

# ---------------------------------------------------------------------------
# Tipografia e espaçamento
# ---------------------------------------------------------------------------

TIPOGRAFIA: dict[str, str] = {
    "titulo": "'Inter', system-ui, sans-serif",
    "corpo": "'Inter', system-ui, sans-serif",
    "mono": "'JetBrains Mono', monospace",
}

ESPACAMENTO: dict[str, int] = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "xxl": 48,
}

# ---------------------------------------------------------------------------
# Storytelling por aba (frase-pergunta + tom direto)
# ---------------------------------------------------------------------------

STORYTELLING: dict[str, str] = {
    "intro": (
        "Inteligência política aberta. Soberana. Local. "
        "Quem vota a favor do quê. Quem mudou de lado. Quem fala uma coisa "
        "e vota outra. Sem opinião nossa -- só dados."
    ),
    "lista_sessoes": (
        "Suas pesquisas ficam salvas localmente. "
        "Cada uma é uma análise autocontida que você pode revisitar, "
        "exportar, ou compartilhar com outros pesquisadores."
    ),
    "nova_pesquisa": (
        "Configure tópico, casa legislativa, estado, partido e período. "
        "A coleta roda em background na sua máquina -- pode levar minutos "
        "ou horas dependendo do recorte."
    ),
    "sobre": (
        "Hemiciclo é uma ferramenta cidadã para entender o Congresso "
        "Brasileiro com o mesmo rigor metodológico que se vende a "
        "lobistas. Open-source, GPL v3, sem servidor central."
    ),
    "importar": (
        "Importe a sessão de outro pesquisador como se fosse sua. "
        "Verificamos a integridade dos artefatos antes de abrir -- "
        "zero confiança cega."
    ),
    "sessao_detalhe": (
        "Relatório multidimensional da pesquisa. Quem está mais a favor, "
        "quem está mais contra, como é a assinatura do voto e do discurso. "
        "Tudo derivado dos dados oficiais que rodaram localmente na sua máquina."
    ),
}

# ---------------------------------------------------------------------------
# Cores dos 7 eixos da assinatura indutiva (D4)
# ---------------------------------------------------------------------------
# Posição, intensidade, hipocrisia, volatilidade, centralidade, convertibilidade,
# enquadramento. Mantêm a paleta institucional (azul + ouro + tons neutros).

CORES_EIXOS: dict[str, str] = {
    "posicao": AZUL_HEMICICLO,
    "intensidade": AMARELO_OURO,
    "hipocrisia": VERMELHO_ARGILA,
    "volatilidade": AZUL_CLARO,
    "centralidade": VERDE_FOLHA,
    "convertibilidade": "#8B5A3C",  # marrom terra (neutro complementar)
    "enquadramento": CINZA_PEDRA,
}

EIXOS_ASSINATURA: tuple[str, ...] = tuple(CORES_EIXOS.keys())

# ---------------------------------------------------------------------------
# Mapa de cor por aba (usado pelo header e pela navegação)
# ---------------------------------------------------------------------------

COR_POR_ABA: dict[str, str] = {
    "intro": AZUL_HEMICICLO,
    "lista_sessoes": AZUL_CLARO,
    "nova_pesquisa": AMARELO_OURO,
    "sobre": CINZA_PEDRA,
}

# ---------------------------------------------------------------------------
# Rótulos amigáveis das abas
# ---------------------------------------------------------------------------

ROTULO_ABA: dict[str, str] = {
    "intro": "Início",
    "lista_sessoes": "Pesquisas",
    "nova_pesquisa": "Nova pesquisa",
    "sobre": "Sobre",
}

# ---------------------------------------------------------------------------
# Partidos canônicos (siglas das últimas 3 legislaturas, ampliável)
# ---------------------------------------------------------------------------

PARTIDOS_CANONICOS: tuple[str, ...] = (
    "PT",
    "PL",
    "MDB",
    "PSB",
    "PSD",
    "PSDB",
    "PP",
    "UNIÃO",
    "REPUBLICANOS",
    "PDT",
    "NOVO",
    "PSOL",
    "REDE",
    "AVANTE",
    "PODE",
    "PCdoB",
    "CIDADANIA",
    "SOLIDARIEDADE",
    "PV",
    "PRD",
    "AGIR",
)
