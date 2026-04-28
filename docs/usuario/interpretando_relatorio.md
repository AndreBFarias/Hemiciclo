# Como interpretar o relatório de uma pesquisa

Este guia ajuda a ler a página de detalhe da sessão (Pesquisas → Abrir
relatório). Toda a análise foi gerada localmente na sua máquina, a partir
dos dados oficiais da Câmara e do Senado, sem nenhum servidor central.

## Top a-favor / Top contra

Duas tabelas ranqueadas mostram os parlamentares com **maior proporção de
votos sim** (a-favor) e **menor proporção** (contra) em proposições do
tópico da pesquisa.

- **Score**: proporção de votos `Sim` no recorte (0% a 100%).
- **Limite default**: top 100 cada.
- Os scores vêm da camada C1 (regex sobre ementas + JOIN com a tabela de
  votos nominais). Quando a tabela `votacoes` ainda não tem
  `proposicao_id` (ver limitação `S27.1` abaixo), o JOIN retorna vazio e a
  coluna fica zerada para esse recorte. A camada C2 (TF-IDF sobre
  discursos) entra como desempate de relevância textual.

## Assinatura multidimensional (radar)

O radar usa até 7 eixos da assinatura indutiva (D4 do plano R2):

| Eixo | Significado | Status |
|---|---|---|
| `posicao` | Proporção de votos sim no tópico | disponível |
| `intensidade` | Frequência relativa de discursos no tópico | disponível |
| `hipocrisia` | Gap entre discurso público e voto efetivo | em S33 |
| `volatilidade` | Variação do voto ao longo do tempo | em S33 |
| `centralidade` | Grau no grafo de coautoria | em S32 |
| `convertibilidade` | Probabilidade de mudar de lado (ML) | em S34 |
| `enquadramento` | Marco discursivo dominante (LLM) | em S34b |

Eixos rotulados `(em SXX)` aparecem como zero no traço polar até a sprint
correspondente entregar a feature. **Não interprete zero como ausência de
posicionamento -- interprete como dimensão ainda não medida.**

Limite default: 20 parlamentares plotados (performance Plotly).

## Heatmap parlamentar × tópico

Cor = `proporcao_sim`. Verde claro = a-favor; vermelho = contra; cinza-areia
= neutro. Na S31 a sessão tem só um tópico (recorte da pesquisa), então o
heatmap é uma faixa vertical. Em sprints futuras (S33, S38) ele cruza
múltiplos tópicos para revelar coerência ideológica.

## Word clouds

Duas nuvens de palavras (a-favor e contra) extraídas dos nomes/textos do
ranking. Stop words PT-BR básicas removidas. Cor única por nuvem
(verde-folha vs vermelho-argila) -- determinística (`random_state=42`)
para que a mesma sessão gere a mesma imagem em qualquer máquina.

## Limitações conhecidas

A seção final do relatório lista as sprints que documentam limites
herdados desta versão. Cada uma tem um spec próprio em `sprints/`:

- **S24b** -- 4 colunas vazias em proposições da Câmara (recall reduzido
  em metadados).
- **S24c** -- coletor da Câmara só pega o ano inicial da legislatura
  quando `ano=None`.
- **S25.3** -- schema dual da API Senado v7 (raiz vs
  `IdentificacaoMateria`); tratado defensivamente, mas pode haver perda
  marginal.
- **S27.1** -- tabela `votacoes` ainda sem `proposicao_id` (Migration
  M002). O JOIN de votos no classificador C1 retorna agregação vazia em
  recortes onde nenhuma proposição relevante foi votada. Score do top
  pode ficar zerado nesse caso.

Quando essas sprints ficarem `DONE` (ver `sprints/ORDEM.md`) o relatório
ganha precisão automaticamente sem você precisar refazer a pesquisa.

## Estados da sessão

| Estado | O que aparece na tela |
|---|---|
| `criada` / `coletando` / `etl` / `embeddings` / `modelando` | Barra de progresso + lista de etapas, com polling 2 s |
| `concluida` | Top, radar, heatmap, word clouds, manifesto |
| `erro` | Mensagem do campo `erro` + botão de retomar |
| `interrompida` | Aviso "kill externo" + botão de retomar |
| `pausada` | Aviso "use retomar" |

A retomada via UI chega em sprint próxima. Por enquanto, retomar pelo
CLI:

```sh
hemiciclo sessao retomar <id-da-sessao>
```

## Determinismo

- `random_state=42` em todo modelo aleatório (PCA, BERTopic, word cloud).
- Hash SHA256 truncado em 16 chars para cada artefato em
  `manifesto.json`. Duas pesquisas com os mesmos parâmetros e o mesmo
  estado de coleta produzem manifestos com hashes idênticos -- prova
  matemática de auditabilidade.
