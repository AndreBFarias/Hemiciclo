"""Testes unit de ``extrair_palavras_chave_de_ementas`` (S38.8).

Garantem que:
- Lista vazia ou com menos que ``min_df`` documentos retorna lista vazia.
- Stopwords PT-BR e termos jurídicos comuns são filtrados.
- Nomes próprios de parlamentares passados como corpus não viram tokens
  grandes -- bug ético da S38.8.
- Saída é determinística (I3): duas chamadas idênticas devolvem mesma lista.
"""

from __future__ import annotations

from hemiciclo.dashboard.widgets.word_cloud import extrair_palavras_chave_de_ementas

# Corpus mínimo de 6 ementas plausíveis sobre aborto. Repete termos como
# "interrupção", "gestação", "aborto" pra ultrapassar ``min_df=2``.
_EMENTAS_ABORTO = [
    "Dispõe sobre a interrupção voluntária da gestação em casos de estupro.",
    "Altera o Código Penal para tipificar a interrupção da gestação como crime.",
    "Garante atendimento humanizado em casos de aborto legal no SUS.",
    "Estabelece pena para profissional de saúde que pratique aborto fora dos casos legais.",
    "Cria protocolo de atendimento à mulher em situação de violência sexual e gestação.",
    "Institui campanha nacional sobre direitos reprodutivos e saúde da mulher.",
]


def test_lista_vazia_retorna_vazio() -> None:
    """Sem ementas, sem palavras-chave."""
    assert extrair_palavras_chave_de_ementas([]) == []


def test_menos_que_min_df_retorna_vazio() -> None:
    """Apenas 1 ementa não satisfaz ``min_df=2`` default."""
    assert extrair_palavras_chave_de_ementas(["Dispõe sobre interrupção da gestação."]) == []


def test_strings_em_branco_sao_filtradas() -> None:
    """Strings só de espaço viram lista vazia antes de TF-IDF."""
    assert extrair_palavras_chave_de_ementas(["   ", "", "  "]) == []


def test_extrai_termos_relevantes_aborto() -> None:
    """Corpus aborto produz termos de domínio (não nomes próprios)."""
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=20, min_df=2)

    assert termos, "esperado retornar termos não-vazios"
    # Termos esperados (caixa baixa, lematização básica).
    so_termos = [t for t, _ in termos]
    # "gestação" aparece em pelo menos 3 ementas -- deve estar na lista.
    assert any("gestação" in t for t in so_termos), (
        f"'gestação' deveria estar entre os termos top -- saiu: {so_termos!r}"
    )


def test_filtra_stopwords_pt_br() -> None:
    """Saída não contém preposições/artigos PT-BR."""
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=50, min_df=2)
    so_termos = {t for t, _ in termos}

    proibidos = {"de", "da", "do", "para", "que", "não", "nao", "em", "uma", "sobre"}
    intersec = so_termos & proibidos
    assert not intersec, f"stopwords vazaram para a saída: {intersec!r}"


def test_filtra_jargao_legislativo() -> None:
    """Termos como 'dispõe', 'altera', 'estabelece' não devem dominar."""
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=50, min_df=2)
    so_termos = {t for t, _ in termos}

    jargao = {"dispõe", "dispoe", "altera", "estabelece", "institui", "fica"}
    intersec = so_termos & jargao
    assert not intersec, f"jargão legislativo vazou para a saída: {intersec!r}"


def test_nomes_proprios_nao_aparecem_quando_ausentes_do_corpus() -> None:
    """Bug ético da S38.8: nomes de parlamentares não devem virar tokens.

    Garantia indireta: se o corpus é só ementas (sem nomes), nenhum nome
    aparece. Esse teste protege contra regressão se alguém um dia voltar
    a passar ``[p['nome'] for p in top]`` por engano.
    """
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=50, min_df=2)
    so_termos = {t for t, _ in termos}

    nomes = {"sâmia", "talíria", "erika", "magno", "feliciano", "marcel"}
    intersec = so_termos & nomes
    assert not intersec, f"nomes próprios vazaram para a saída: {intersec!r}"


def test_determinismo_duas_chamadas_iguais() -> None:
    """I3: duas chamadas com mesma entrada -> mesma saída ordenada."""
    a = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=15, min_df=2)
    b = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=15, min_df=2)
    assert a == b, "saída de TF-IDF não é determinística"


def test_top_n_limita_quantidade() -> None:
    """Parâmetro ``top_n`` recorta a lista final."""
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=3, min_df=2)
    assert len(termos) <= 3


def test_pesos_sao_decrescentes() -> None:
    """Saída ordenada por peso descendente -- garantia de leitura visual."""
    termos = extrair_palavras_chave_de_ementas(_EMENTAS_ABORTO, top_n=20, min_df=2)
    pesos = [p for _, p in termos]
    assert pesos == sorted(pesos, reverse=True), (
        f"pesos deveriam ser decrescentes, vieram: {pesos!r}"
    )


def test_corpus_pequeno_homogeneo_nao_quebra() -> None:
    """Corpus com tudo igual / sem variação não levanta exceção."""
    homogeneo = ["aborto", "aborto", "aborto"]
    # Pode retornar vazio ou um termo só -- o que importa é não quebrar.
    resultado = extrair_palavras_chave_de_ementas(homogeneo, top_n=5, min_df=2)
    assert isinstance(resultado, list)
