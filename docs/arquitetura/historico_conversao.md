# Histórico de conversão por parlamentar (S33)

> Eixo `volatilidade` da assinatura multidimensional (D4 / ADR-004). Alimenta a S34 (ML de convertibilidade).

## O que é

Para cada parlamentar com votos registrados em pelo menos 2 períodos
distintos, o pipeline calcula a trajetória da `proporcao_sim` ao longo
do tempo, detecta **mudanças de posição** (deltas grandes entre buckets
adjacentes) e produz um **índice de volatilidade** em `[0, 1]`.

Exemplo: "Parlamentar X votou 80% SIM em PLs em 2018 e 20% SIM em 2024
-- mudança de -60pp = ALTA volatilidade."

## Arquivos do contrato

| Caminho | Papel |
|---|---|
| `src/hemiciclo/modelos/historico.py` | 3 classes principais + helper batch |
| `src/hemiciclo/sessao/pipeline.py::_etapa_historico` | Etapa 4.7 do pipeline (93-95%) |
| `src/hemiciclo/dashboard/widgets/timeline_conversao.py` | Plotly line chart |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py::_renderizar_secao_historico` | Selectbox + timeline |
| `src/hemiciclo/cli.py::historico_calcular` | Subcomando `hemiciclo historico calcular` |
| `<sessao_dir>/historico_conversao.json` | Persistência por sessão |

## Granularidades

Duas granularidades suportadas:

- **`ano`** (default): bucket = ano da `vt.data`. Mais fino, exige
  pelo menos 5 votos por ano para o bucket aparecer.
- **`legislatura`**: mapa fixo
  - 2015-2018 -> 55
  - 2019-2022 -> 56
  - 2023+ -> 57

  Mais robusto a anos de baixa atividade. Útil para parlamentares com
  poucos votos por ano mas presentes em múltiplos mandatos.

## Detecção de mudanças

Compara buckets adjacentes do histórico ordenado cronologicamente.
Threshold padrão: **30 pontos percentuais** em `proporcao_sim`. Cada
evento detectado registra:

- `bucket_anterior` / `bucket_posterior`
- `proporcao_sim_anterior` / `proporcao_sim_posterior`
- `delta_pp` (sinal preservado: positivo = mais SIM, negativo = menos SIM)
- `posicao_anterior` / `posicao_posterior` (a_favor / contra / neutro)

## Posição dominante

Limiares idênticos aos da camada C1 do classificador:

- `proporcao_sim >= 0.70` -> **a_favor** (verde-folha)
- `proporcao_sim <= 0.30` -> **contra** (vermelho-argila)
- entre os dois -> **neutro** (cinza-pedra)

## Índice de volatilidade

`std_populacional(proporcao_sim) / 0.5`, saturado em `1.0`.

- 0.0 = parlamentar consistente em todos os buckets.
- 1.0 = parlamentar errático (alterna 0% e 100% entre buckets).

A constante `0.5` é a std máxima teórica de uma série binária 0/1.

## Skip graceful

Três níveis:

1. **Tabela `votos` ausente** no `dados.duckdb` -> JSON com
   `skipped=True` e `motivo="tabela votos ausente"`. Pipeline segue.
2. **Sem votos no DB** -> JSON com `skipped=True` e `motivo="sem votos no DB"`.
3. **Parlamentar com < 2 buckets** -> excluído silenciosamente do
   resultado (não aparece no JSON, não trava o pipeline).

Pipeline e CLI sempre saem com exit code 0 nesses casos. Dashboard
mostra `st.info` neutro indicando ausência de dados.

## Schema do `historico_conversao.json`

```json
{
  "parlamentares": {
    "<id>": {
      "casa": "camara",
      "nome": "...",
      "historico": [
        {
          "bucket": 2018,
          "n_votos": 47,
          "proporcao_sim": 0.8,
          "proporcao_nao": 0.18,
          "posicao": "a_favor"
        }
      ],
      "mudancas_detectadas": [
        {
          "bucket_anterior": 2018,
          "bucket_posterior": 2024,
          "proporcao_sim_anterior": 0.8,
          "proporcao_sim_posterior": 0.2,
          "delta_pp": -60.0,
          "posicao_anterior": "a_favor",
          "posicao_posterior": "contra"
        }
      ],
      "indice_volatilidade": 0.42
    }
  },
  "metadata": {
    "granularidade": "ano",
    "threshold_pp": 30.0,
    "n_parlamentares": 100,
    "n_com_mudancas": 12,
    "skipped": false
  }
}
```

## CLI

```bash
hemiciclo historico calcular <sessao_id> \
    [--granularidade ano|legislatura] \
    [--threshold-pp 30] \
    [--top-n 100]
```

- Exit 0 quando OK ou SKIPPED graceful.
- Exit 2 para sessão inexistente ou granularidade inválida.

## Limitação atual

Enquanto a sprint S27.1 não entregar `votacoes.proposicao_id`, o
histórico é **geral** (todas as votações do parlamentar), não filtrado
pelo tópico da sessão. Quando S27.1 fechar, esta sprint ganha modo
`--topico <slug>` que aplica o filtro pelo conjunto de proposições
relevantes da S27.

## Decisões fundamentais

- **JOIN votos x votacoes via `(votacao_id, casa)`** -- o schema atual
  S26 não tem `proposicao_id` em `votacoes`. Reuso do precedente da
  S32 (`hemiciclo.modelos.grafo`).
- **`UPPER(v.voto) = 'SIM'`** -- valores brutos vêm como `'Sim'`,
  `'Nao'`, `'Abstencao'`, `'Obstrucao'`, `'Art.17'`. Comparação
  case-insensitive evita tropeçar em divergências entre Câmara e Senado.
- **`TRY_CAST(vt.data AS DATE)`** -- campo `vt.data` é VARCHAR (schema
  v1). `TRY_CAST` retorna NULL em formato malformado, evitando
  exceção em registros anômalos. WHERE filtra NULL.
- **HAVING `n_votos >= 5`** -- bucket pobre distorce proporção.
  Constante `MIN_VOTOS_POR_BUCKET`.
- **Polars DataFrame** com schema explícito mesmo em retorno vazio --
  consumidor a jusante (CLI, pipeline, dashboard) pode iterar
  colunas sem ramificar para "vazio".

## Próximas sprints

- **S34** consome `indice_volatilidade` como feature da assinatura.
- **S38** integra ao manifesto de release v2.0.0.
