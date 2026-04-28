# Grafos de rede parlamentar (S32)

Este documento descreve a arquitetura, os algoritmos e as limitações
conhecidas dos grafos de rede entregues na sprint S32 (eixo `centralidade`
da assinatura multidimensional D4 do plano R2).

## Visão geral

São construídos dois grafos não-dirigidos a partir de `dados.duckdb` da
Sessão de Pesquisa, ambos com nós = parlamentares (id inteiro) e
atributos `nome`, `partido`, `uf` enriquecidos da tabela `parlamentares`:

| Grafo | Aresta | Peso | Mínimo |
|---|---|---|---|
| `GrafoCoautoria` | "Votaram juntos na mesma votação" | Contagem de votações em comum | 5 votações |
| `GrafoVoto` | Mesma posição (SIM/NÃO/ABSTENÇÃO) | Proporção de coincidência ∈ [0, 1] | 50% |

Para ambos os grafos, **menos de 5 nós** dispara `AmostraInsuficiente`,
que o caller (pipeline ou CLI) trata como SKIPPED graceful. Nada de
exceção fatal ao usuário.

## Arquivos persistidos

Por sessão concluída com `incluir_grafo=True`:

- `~/hemiciclo/sessoes/<id>/grafo_coautoria.html` -- HTML pyvis interativo standalone
- `~/hemiciclo/sessoes/<id>/grafo_voto.html` -- idem
- `~/hemiciclo/sessoes/<id>/metricas_rede.json` -- métricas resumidas

Estrutura de `metricas_rede.json`:

```json
{
  "coautoria": {
    "skipped": false,
    "n_nos": 87,
    "n_arestas": 412,
    "maior_componente": 84,
    "n_comunidades": 5,
    "top_centrais": [
      {"id": 1234, "nome": "...", "partido": "PT", "uf": "SP",
       "centralidade": 0.86, "comunidade": 0}
    ]
  },
  "voto": { ... }
}
```

Quando SKIPPED: `{"skipped": true, "motivo": "..."}`.

## Algoritmos

### Centralidade de grau

Calculada via `networkx.degree_centrality(grafo)`, retornando `degree(v) / (N-1)`
para cada nó. Resultado normalizado em `[0, 1]`. Em grafo vazio retorna
dicionário vazio.

### Comunidades

**Algoritmo principal: Louvain via `python-louvain`.**

Quando `community` está disponível em runtime, chamamos
`community.best_partition(grafo, random_state=42)`. Determinismo garantido
pelo seed fixo (invariante I3 do `VALIDATOR_BRIEF.md`).

**Fallback: greedy modularity da networkx.**

Se `python-louvain` falha o import (por exemplo numa máquina Windows
onde a dependência C não compilou), caímos automaticamente em
`networkx.community.greedy_modularity_communities`, que retorna uma
lista de conjuntos de nós (cada conjunto = uma comunidade). Convertemos
para o formato `{node: idx}` esperado pelo restante do código.

O fallback é silencioso pelo log mas registrado como WARNING via Loguru
para que o usuário curioso entenda por que os agrupamentos parecem mais
grosseiros.

### Tamanho da maior componente

`MetricasGrafo.tamanho_maior_componente(grafo)` retorna o número de nós
da maior componente conexa. Usado para reportar a "saúde" do grafo --
componente principal pequena indica grafo fragmentado (recorte temporal
estreito demais ou pouco voto registrado).

## Renderização pyvis

`renderizar_pyvis(grafo, html_path, titulo)` produz HTML standalone via
`pyvis.network.Network`:

- `cdn_resources="in_line"` -- todo o JavaScript embutido no arquivo,
  zero dep de rede em runtime (alinhado com I1 do BRIEF: tudo local).
- `bgcolor=tema.BRANCO_OSSO`, `font_color=tema.AZUL_HEMICICLO`.
- Cor do nó: cicla na paleta institucional `(AZUL_HEMICICLO, AMARELO_OURO,
  VERDE_FOLHA, VERMELHO_ARGILA, marrom-terra, AZUL_CLARO)` por comunidade
  detectada -- 6 cores cobrem comunidades comuns sem virar arco-íris.
- Tamanho do nó: `10 + 30 * centralidade`, ressaltando hubs.
- Tooltip: `nome (partido/UF)`.
- Layout `barnes_hut` com parâmetros estáveis (`gravity=-2000`,
  `central_gravity=0.1`, `spring_length=120`, `spring_strength=0.05`,
  `damping=0.4`).

Para grafos com mais de 200 nós, o caller deve usar
`MetricasGrafo.filtrar_top(grafo, max_nos=200)` antes -- pyvis fica
ilegível com 500+ nós no canvas.

Grafo vazio gera placeholder HTML coerente com a paleta
("Amostra insuficiente para gerar o grafo...") sem levantar exceção.

## Embedação no dashboard

`renderizar_rede(html_path, altura=600)` lê o HTML como string e injeta
via `st.components.v1.html(conteudo, height=altura, scrolling=False)`.
Tolerante a arquivo ausente (`st.info` amigável) e OSError (`st.warning`).

A página `sessao_detalhe.py` ganha seção "Redes de coautoria e voto"
com 3 tabs:

- **Coautoria**: HTML pyvis embedado + status (n_nos/n_arestas ou SKIPPED motivo)
- **Voto**: idem
- **Métricas**: lista textual + `st.dataframe` com top 10 mais centrais
  por tipo de grafo

## Como interpretar comunidades

A detecção de comunidades agrupa parlamentares que **votam de forma
similar** (no `GrafoVoto`) ou **co-presenciam votações** (no `GrafoCoautoria`).

- Um partido coeso aparece como uma única comunidade.
- Um partido faccionalizado aparece em duas ou três comunidades distintas.
- "Pontes" entre comunidades indicam parlamentares com afinidade
  cruzada -- candidatos a maiores níveis de **convertibilidade**
  (eixo da assinatura D4 que será calculado em S34).
- Comunidades com 1-2 nós são casos de borda; tratados como ruído.

A interpretação **nunca** atribui rótulo ideológico automaticamente. O
algoritmo só agrupa por padrão de voto -- a leitura política é do
usuário cidadão.

## Limitações conhecidas

### Proxy de coautoria (S27.1 pendente)

Enquanto S27.1 não entrega `votacoes.proposicao_id`, "coautoria de
proposição" é aproximada por "co-presença em votação". Isso significa
que:

- Dois parlamentares que votam juntos em **muitas** votações sem
  necessariamente serem co-autores de PLs ainda gerarão aresta com peso
  alto.
- A semântica "coautoria genuína" (definida pela API da Câmara via campo
  `coautores` em proposições) só ficará disponível quando S27.1 fechar.

A limitação está documentada via campo `LIMITACOES_CONHECIDAS = ("S24b",
"S24c", "S25.3", "S27.1")` em `pipeline.py` e impressa no
`manifesto.json` de cada sessão.

### Determinismo de Louvain

Mesmo com `random_state=42`, micro-variações na ordem de iteração de
hashmaps em runtimes diferentes podem produzir partições levemente
distintas. Para reprodutibilidade absoluta, fixe também a seed do PRNG
do Python via `PYTHONHASHSEED=0`.

### Tamanho do HTML pyvis

O HTML standalone com 200 nós e 500 arestas tem ~300 KB. Sessões com
recortes muito amplos (legislatura inteira, todas as casas, todos os
partidos) facilmente passariam de 500 nós; o filtro `top_n=200` por
centralidade corta para garantir HTML usável.

## Fluxo do CLI

```bash
# Pipeline completo: cria sessão, coleta, ETL, classifica, gera grafos
hemiciclo sessao iniciar --topico aborto --legislatura 57

# Regenerar grafos de uma sessão antiga (anterior à S32)
hemiciclo rede analisar <id_sessao> --tipo ambos

# Só coautoria (mais rápido)
hemiciclo rede analisar <id_sessao> --tipo coautoria
```

## Próximos passos

- **S33** -- histórico temporal das redes: como a comunidade de cada
  parlamentar evolui ao longo de meses/anos.
- **S34** -- ML de convertibilidade usando features de rede como input.
- **S38** -- comparação de redes entre tópicos (qual a sobreposição
  entre quem articula em "aborto" e quem articula em "porte de armas").
- **Sprint dedicada** -- grafo dirigido (relator → autor) e análise
  multilevel (parlamentar × partido × casa).
