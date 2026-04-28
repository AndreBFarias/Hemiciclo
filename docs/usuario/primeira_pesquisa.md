# Primeira pesquisa -- jornada do usuário

> **Status atual (S23):** o formulário de Nova Pesquisa está completo e
> validado por Pydantic, mas o pipeline real (coleta, ETL, classificação,
> modelagem) chega na sprint **S30**. Por enquanto, ao clicar em "Iniciar
> pesquisa" você verá a mensagem `Funcionalidade chega em S30` e um
> rascunho dos parâmetros é salvo localmente para retomada futura.

## O que é uma Sessão de Pesquisa

Uma **Sessão de Pesquisa** é uma análise autocontida no seu computador.
Cada sessão fica em `~/hemiciclo/sessoes/<id>/` e contém:

- `params.json` -- a configuração que você escolheu.
- `status.json` -- estado de execução publicado pelo subprocess.
- `dados.duckdb` -- banco local com discursos, votos e proposições.
- `relatorio_state.json` -- caminho do relatório multidimensional.
- `manifesto.json` -- hash de integridade da sessão.
- `log.txt` -- log estruturado da execução.

Você pode revisitar, exportar como `.zip` e compartilhar a sessão com outro
pesquisador (a S35 entrega importação verificada).

## Jornada esperada (com S30 ativa)

### 1. Configure os parâmetros

Na aba **Nova pesquisa**, preencha:

| Campo | Exemplo | Notas |
|---|---|---|
| Tópico | `aborto` | texto livre OU id de YAML curado em `topicos/` |
| Casas legislativas | Câmara, Senado | escolha ao menos uma |
| Legislaturas | 55, 56, 57 | 55 = 2015-2018; 56 = 2019-2022; 57 = 2023-2026 |
| Estados (UF) | (vazio) | vazio = todas as 27 UFs |
| Partidos | (vazio) | vazio = todos os partidos canônicos |
| Período | 2015-01-01 a 2026-04-28 | janela para discursos e proposições |
| Camadas de análise | regex + voto + embeddings | LLM desligada por default |

### 2. Inicie a coleta

Clique em **Iniciar pesquisa**. O Streamlit dispara um subprocess Python que
roda em background na sua máquina. Você pode fechar o navegador -- a coleta
continua. O lockfile (`pid.lock`) garante que processos zumbis sejam
detectados e a sessão volte ao estado `INTERROMPIDA` se o processo morrer.

### 3. Acompanhe o progresso

O Streamlit faz polling em `status.json` e mostra:

- Barra de progresso global (`progresso_pct`).
- Etapa atual (Coleta / ETL / Embeddings / Modelagem).
- Tempo decorrido e tempo restante estimado.
- Botões de **Pausar**, **Cancelar** e (se interrompida) **Retomar**.

### 4. Leia o relatório

Quando o estado vai para `CONCLUIDA`, a aba **Pesquisas** abre o relatório
multidimensional (sprints S31-S34):

- Top 100 a-favor / Top 100 contra.
- Assinatura multidimensional (radar com os 7 eixos).
- Grafo de coautoria + voto (S32).
- Histórico de conversão por parlamentar (S33).
- Convertibilidade (ML, S34).
- Word clouds e séries temporais.

### 5. Exporte ou compartilhe

Botão **Exportar** gera um zip da pasta da sessão com hash de integridade.
Outro pesquisador pode importar com a aba dedicada (S35) e o Hemiciclo
valida schema, hash e versão do modelo base usado.

## E hoje, na S23?

Hoje o formulário valida tudo via **Pydantic v2** (rejeita tópico vazio,
casa vazia, legislatura inválida, UF fora da lista canônica, período
invertido). Ao submeter, persistimos `params.json` em
`~/hemiciclo/sessoes/<slug>_rascunho/` para que, quando a S30 ficar pronta,
você não precise reconfigurar.

A página **Pesquisas** já lê pastas de sessão em
`~/hemiciclo/sessoes/` e mostra cards com o estado de cada uma. Antes de a
S30 chegar, o estado padrão dos rascunhos é `criada` e o progresso fica
em zero.
