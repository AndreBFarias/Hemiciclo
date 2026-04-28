"""Word cloud com paleta institucional do Hemiciclo (S31).

Gera uma nuvem de palavras a partir de uma lista de textos (ementas, trechos
de discurso etc) usando ``wordcloud.WordCloud`` com cor única dominante e
fundo da paleta sóbria do tema. Stop words PT-BR básicas embutidas.

I3 (determinismo): ``random_state=42`` fixo na construção do
``WordCloud`` -- duas chamadas com a mesma lista de textos produzem o
mesmo PNG.
"""

from __future__ import annotations

import io

import streamlit as st

from hemiciclo.dashboard import tema

# Stop words PT-BR mínimas pra word cloud não virar lista de preposições.
# Conjunto curto e curado; ampliação fica para sprint futura se necessário.
STOP_PT_BR: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "ate",
        "até",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "entre",
        "essa",
        "essas",
        "esse",
        "esses",
        "esta",
        "estas",
        "este",
        "estes",
        "eu",
        "foi",
        "ja",
        "já",
        "lhe",
        "mais",
        "mas",
        "me",
        "na",
        "nao",
        "não",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "pela",
        "pelo",
        "por",
        "qual",
        "que",
        "se",
        "sem",
        "ser",
        "seu",
        "seus",
        "sob",
        "sobre",
        "sua",
        "suas",
        "tem",
        "um",
        "uma",
        "umas",
        "uns",
    }
)


def renderizar_word_cloud(
    textos: list[str],
    titulo: str,
    max_palavras: int = 100,
    cor_dominante: str | None = None,
) -> None:
    """Renderiza word cloud em PNG via ``st.image``.

    Args:
        textos: Lista de strings que serão concatenadas em um único corpus.
        titulo: Título exibido como caption logo abaixo da imagem.
        max_palavras: Limite superior de palavras desenhadas (default 100).
        cor_dominante: Cor hex (ex. ``"#1E3A5F"``). Se ``None`` usa
            ``tema.AZUL_HEMICICLO``.
    """
    if not textos:
        st.info(f"Sem dados para a nuvem de palavras: {titulo}")
        return

    # Import local pra preservar boot do dashboard (precedente S28).
    from wordcloud import WordCloud  # noqa: PLC0415 -- lazy

    cor = cor_dominante or tema.AZUL_HEMICICLO
    corpus = " ".join(t for t in textos if t and t.strip())
    if not corpus.strip():
        st.info(f"Sem dados para a nuvem de palavras: {titulo}")
        return

    wc = WordCloud(
        max_words=max_palavras,
        background_color=tema.BRANCO_OSSO,
        color_func=lambda *_args, **_kwargs: cor,
        stopwords=set(STOP_PT_BR),
        random_state=42,  # I3
        width=800,
        height=400,
        prefer_horizontal=0.95,
    ).generate(corpus)

    buf = io.BytesIO()
    wc.to_image().save(buf, format="PNG")
    st.image(buf.getvalue(), caption=titulo, use_container_width=True)


def extrair_palavras_chave_de_ementas(
    ementas: list[str],
    top_n: int = 50,
    min_df: int = 2,
) -> list[tuple[str, float]]:
    """Extrai termos mais relevantes de uma lista de ementas via TF-IDF.

    Sinal: peso TF-IDF agregado (soma dos scores em todos os documentos).
    Vocabulário em PT-BR é filtrado por :data:`STOP_PT_BR` ampliado com
    stopwords adicionais frequentes em ementas legislativas. Suporta
    bigramas para capturar termos como "interrupção gestação".

    Determinismo (I3): ementas são ordenadas lexicograficamente antes da
    vetorização e a saída é estavelmente ordenada por (peso desc, termo asc).

    Args:
        ementas: Lista de strings com ementas das proposições.
        top_n: Quantidade máxima de termos a retornar (default 50).
        min_df: Frequência documental mínima para incluir um termo
            (default 2 -- termo aparece em pelo menos 2 ementas).

    Returns:
        Lista ``[(termo, peso), ...]`` ordenada por peso decrescente.
        Lista vazia se ``ementas`` for vazia ou se não houver termos
        que sobrevivam aos filtros (corpus muito pequeno / só stopwords).
    """
    textos = [e for e in (ementas or []) if e and e.strip()]
    if len(textos) < min_df:
        return []

    # Ordem estável -- TF-IDF determinístico precede ordenação da entrada.
    textos_ordenados = sorted(textos)

    # Lazy import (precedente classificador_c2.tfidf_relevancia).
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

    # Stopwords adicionais comuns em ementas que poluem a nuvem.
    stop_extra = {
        "art",
        "lei",
        "altera",
        "dispoe",
        "dispõe",
        "estabelece",
        "institui",
        "fica",
        "outras",
        "providencias",
        "providências",
        "n",
        "nº",
        "º",
        "ª",
    }
    stop_words = sorted(STOP_PT_BR | stop_extra)

    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words=stop_words,
            min_df=min_df,
            ngram_range=(1, 2),
            max_features=top_n * 4,  # folga; recortamos no final
        )
        matriz = vectorizer.fit_transform(textos_ordenados)
    except ValueError:
        # Corpus pequeno demais -- todos os termos viram stopword ou
        # nenhum sobrevive ao min_df.
        return []

    pesos = matriz.sum(axis=0).A1.tolist()
    vocab = vectorizer.get_feature_names_out().tolist()
    pares = list(zip(vocab, pesos, strict=True))
    # Ordenação estável: peso desc, termo asc (lexicográfica como tiebreaker).
    pares.sort(key=lambda kv: (-kv[1], kv[0]))
    return [(termo, float(peso)) for termo, peso in pares[:top_n]]
