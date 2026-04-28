# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

(Próximas releases em `sprints/ORDEM.md`.)

## [2.1.1] - 2026-04-28

### Hotfix UX/UI revelado em smoke real do browser

Após tag v2.1.0, smoke real no browser (que não foi feito antes da release -- lição empírica registrada em `memory/feedback_smoke_real_browser_obrigatorio.md`) revelou problemas que invalidam o produto para uso público. Esta release corrige todos.

**Saneamento histórico (S38.3.1, decisão `b1` do autor):** repositório recriado do zero a partir de main saneada -- histórico antigo descartado por contém vestígios de NDA do ex-empregador.

- **S38.2**: substitui `uninstall.sh` legado da era R por uninstaller Python compatível + adiciona `uninstall.bat`.
- **S38.3** [P0 LEGAL]: remove identificadores autobiográficos do ex-empregador no `manifesto.md`, no plano de design (`docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`), nas specs históricas (`SPRINT_S38_RELEASE_V2.md`, `ORDEM.md`) e no histórico do CHANGELOG -- risco de multa por quebra de NDA. Página `paginas/sobre.py` herda o saneamento (renderiza `manifesto.md`).
- **S38.4** [P0 funcional, DONE]: botão "Iniciar pesquisa" no dashboard agora dispara `SessaoRunner` real (callable `hemiciclo.sessao.pipeline:pipeline_real`), grava `params.json` + `status.json` + `pid.lock` na pasta da sessão, redireciona para `sessao_detalhe` via `st.session_state["sessao_id"]` e mostra polling de progresso. Funções órfãs `_persistir_rascunho` e `_estimar_tempo_e_espaco` removidas (anti-débito). Erros de Pydantic / OSError em criação de sessão / falha de spawn tratados com mensagens PT-BR amigáveis. Smoke real no browser confirma subprocess `_sessao_worker` spawnado e tela de polling renderizando.
- **S38.5** [DONE]: aplica tema institucional completo aos componentes nativos do Streamlit. Cria `.streamlit/config.toml` (paleta `BRANCO_OSSO`/`AMARELO_OURO`/`AZUL_HEMICICLO`/`CINZA_PEDRA`/`CINZA_AREIA`) e estende `dashboard/style.css` com regras `!important` para `[data-baseweb="select"]`, `[data-baseweb="popover"]`, `[data-baseweb="tag"]`, `[data-testid="stDateInput"]`, `[data-testid="stDataFrame"]`, `[data-testid="stForm"] label`, botões `kind="primary"`/`secondary` e `[data-testid="stMarkdownContainer"] code`. Multiselects/selectbox passam a usar `placeholder="Selecione..."` (substitui "Choose options"). Tags do multiselect em `AZUL_CLARO` (jamais vermelho). Botões primary em `AMARELO_OURO` com texto `AZUL_HEMICICLO`. Tabelas Top a-favor/contra com cabeçalho `AZUL_HEMICICLO` e barras de Score em `VERDE_FOLHA`. Mensagens de erro Pydantic do form `nova_pesquisa` traduzidas via `_traduzir_erro_pydantic`. Mantém modo dark, animações e mobile-first como out-of-scope.
- **S38.6** [DONE]: despoluição de jargão técnico no dashboard. Rótulos do radar de assinatura passam de "(S33)/(S32)/(S34)/(S34b)" para "(em breve)"; mensagens "SKIPPED -- motivo" viram "Análise ainda não disponível para esta sessão."; comando CLI exposto "Rode `hemiciclo rede analisar <id_sessao>`" virou "Os grafos de articulação política aparecerão aqui assim que a análise terminar."; path `docs/arquitetura/convertibilidade.md` removido das captions; bloco "Limitações conhecidas" deixa de listar IDs de sprint e mostra texto cidadão único; caption "Retomada via UI chega em sprint próxima... CLI: `hemiciclo sessao retomar`" virou "Retomada estará disponível em breve.". Smoke real (Playwright) confirma zero ocorrências de jargão (`(SXX)`, `S<NN>`, `SKIPPED`, `hemiciclo rede`, `docs/arquitetura`, `proxy enquanto S27`, `chega em S30`) no DOM da `sessao_detalhe`.
- **S38.7** [P0 bug, DONE]: corrige `Score` 1% / 0% travado nas tabelas Top a-favor / Top contra. `ProgressColumn` com `format="%.0f%%"` aplica `printf` ao valor cru -- `0.9928` virava `"1%"`. Fix: `_normalizar_linha` escala `proporcao_sim` por `100` e `min/max_value` do `ProgressColumn` passam para `[0, 100]`. Smoke real do browser confirma scores variados (Sâmia 99%, Talíria 97%, Erika 95%, ..., Eros 5%, Sóstenes 7%).
- **S38.8** [DONE]: word cloud da `sessao_detalhe` deixa de exibir nomes próprios de parlamentares como tokens centrais. Nova função pura `extrair_palavras_chave_de_ementas` em `widgets/word_cloud.py` aplica `TfidfVectorizer` (lazy import) com `STOP_PT_BR` ampliado (jargão legislativo: `dispõe`, `altera`, `estabelece`, `institui`, `fica`) e bigramas `(1, 2)` sobre as ementas do `cache_parquet`. `paginas/sessao_detalhe.py` substitui `st.columns(2)` com `[p["nome"] ...]` por **uma única** word cloud azul institucional alimentada pelo vocabulário do tópico (caption explícita "Termos extraídos por TF-IDF das ementas das proposições"). `scripts/seed_dashboard.py` agora grava `cache_seed.parquet` com 15 ementas sintéticas plausíveis sobre aborto -- antes o path era apontado em `classificacao_c1_c2.json` mas o arquivo nunca era criado, fazendo a página cair em fallback. Determinismo (I3) preservado por ordenação lexicográfica do corpus antes da vetorização. Smoke real (Playwright) confirma word cloud com termos `gestação`, `voluntária`, `reprodutivos`, `interrupção`, `saúde`, `violência` e zero nomes próprios. Labels do form `nova_pesquisa` confirmados em `var(--azul-hemiciclo)` semibold (regressão visual da S38.5). 11 testes novos em `tests/unit/test_word_cloud_palavras_chave.py` cobrindo determinismo, filtros de stopword, recorte por `top_n` e proteção contra regressão de nomes próprios.
- **S23.4** [DONE]: flag `--com-modelo` (alias `--com-bge`) em `install.sh` e `install.bat` baixa `BAAI/bge-m3` (~2GB) via `FlagEmbedding` após o `uv sync`. Falha graciosa sem internet ou com Hugging Face Hub fora do ar (avisos PT-BR, exit não-zero apenas no bloco de download). Adicionada flag `--dry-run` para inspecionar plano sem efetivar. Documentação ampliada em `docs/usuario/instalacao.md` (tabela de trade-off, fallback manual) e nota explícita no `README.md` "Início rápido".

## [2.1.0] - 2026-04-28

### Highlights

Hemiciclo 2.1.0 fecha o "produto utilizável amplamente": **release público destravado** (Windows + fontes auto-hospedadas), **recall do classificador completo** (Migration M002 + iteração de 4 anos por legislatura + enriquecimento de proposições), e **ergonomia de sessão** (filtros UF/partido + `--max-itens`).

7 sprints fundidas em main:
- **S27.1** -- Migration M002 destrava JOIN de votos no classificador C1.
- **S23.1** -- Fontes Inter + JetBrains Mono auto-hospedadas sob SIL OFL 1.1 (zero `@import` Google Fonts; honra I1 do BRIEF).
- **S36** -- Paridade Windows: `install.bat` + `run.bat` testados em CI windows-2022.
- **S30.1** -- `--max-itens` propagado da CLI para coletores Câmara/Senado (sessão amostral em ~1-2min vs 30-60min).
- **S30.2** -- Filtros `--uf` e `--partido` aplicados em `pipeline_real` via SQL pós-ETL.
- **S24b** -- Enriquecimento de proposições via `GET /proposicoes/{id}` popula tema_oficial/autor/status/inteiro_teor.
- **S24c** -- Coletor da Câmara itera os 4 anos da legislatura quando `ano=None` (volume passa de ~3-4k para ~12-16k proposições/legislatura).

### Adicionado

- **S30.2 -- Filtros `--uf` e `--partido` em `sessao iniciar`.** Os campos
  `ParametrosBusca.ufs` e `ParametrosBusca.partidos`, declarados desde
  S29 mas ignorados pelo `pipeline_real`, agora são aplicados no JOIN da
  agregação de voto via tabela temp `_parlamentares_subset_tmp`. Helper
  novo `_montar_clausula_subset_parlamentares` em `sessao/pipeline.py`
  resolve o recorte com placeholders parametrizados (defesa em
  profundidade vs injeção) e `UPPER(partido)` defensivo para o histórico
  do Senado. CLI ganha flags repetíveis `--uf`/`-u` e `--partido`/`-p`
  com try/except amigável que converte `pydantic.ValidationError` em
  `typer.Exit(2)` + texto em vermelho. Filtro acontece **após** o ETL
  (cache transversal SHA256 da S26 deduplica a coleta global; restringir
  ali enviesaria amostra combinada com `--max-itens`). `relatorio_state
  .json` enriquecido com `ufs`, `partidos`, `n_parlamentares_subset`
  para o dashboard (S31) exibir badge de recorte. Smoke esperado:
  `--uf SP --partido PT --topico aborto` reduz ~594 parlamentares para
  ≤15, conclui em <90s.

- **S24b -- Enriquecimento de proposições da Câmara via `GET /proposicoes/{id}`.**
  O endpoint `/proposicoes` (listagem) retorna apenas 6 campos resumidos;
  os 4 campos críticos `tema_oficial`, `autor_principal`, `status` e
  `url_inteiro_teor` chegam apenas via chamada individual ao detalhe.
  Esta sprint introduz `enriquecer_proposicao(prop_id, ...)` em
  `coleta/camara.py`, novo parquet separado `proposicoes_detalhe.parquet`,
  cache transversal por ID em `<home>/cache/proposicoes/<casa>-<id>.json`,
  campo de checkpoint `proposicoes_enriquecidas: set[int]` para retomada
  idempotente, e flag CLI `--enriquecer-proposicoes/--no-enriquecer-proposicoes`
  (default ligado). O consolidador ganha `_inserir_proposicoes_detalhe`
  com `UPDATE ... FROM ... COALESCE` que preenche as 4 colunas no
  DuckDB sem sobrescrever valores existentes. Defaults `None` em vez
  de `""` quando campo está ausente (lição S27.1 -- NULL é a verdade
  semântica de "campo desconhecido"; "" quebra heurísticas em filtros
  `LIKE`). Custo: ~50k chamadas extras por legislatura (~83 min a
  10 req/s), aceitável e mitigado por cache transversal entre sessões.
  Habilita classificador C1 (S27) a operar em recall pleno na produção
  do usuário e dashboard (S31) a exibir autoria/status/link teor reais.

### Corrigido

- **S30.1 -- `--max-itens` propagado em `sessao iniciar`.** O flag
  `hemiciclo sessao iniciar --max-itens N`, antes placeholder herdado da
  S30 (`# noqa: ARG001`), agora atravessa `ParametrosBusca` e chega aos
  coletores Câmara/Senado dentro de `pipeline_real._etapa_coleta` como
  `ParametrosColeta.max_itens`. Default permanece `None` (preserva
  comportamento full -- regressão zero). Sessão amostral conclui em
  ~1-2 min com `--max-itens 50` em vez de 30-60 min full, destravando
  smoke real local, demo do dashboard (S31) e iteração rápida sobre
  sessões reais. Validação Pydantic `ge=1` em `ParametrosBusca` alinhada
  ao `ParametrosColeta` irmão (`max_itens=0` rejeitado; "sem limite" é
  `None`). Out-of-scope explícito: etapas pós-coleta (ETL, C1+C2, C3,
  grafos, histórico, convertibilidade) processam toda a amostra
  coletada -- limites por etapa ficam para sprints futuras
  (S30.4/S30.5).
- **S24c -- Coletor da Câmara itera 4 anos da legislatura quando `ano=None`.**
  Antes da sprint, `coletar_proposicoes(legislatura)` (caminho default
  do CLI quando o usuário não passa `--data-inicio`) baixava apenas o
  ano inicial da legislatura -- ou seja, perdia 75% do volume da
  legislatura. Agora, quando `ano is None`, a função itera os 4 anos
  canônicos via novo helper `_anos_da_legislatura(legislatura)` (ex.:
  `[2023, 2024, 2025, 2026]` para L57). Volume entregue por legislatura
  passa de ~3-4 mil proposições para ~12-16 mil. Refator estrutural:
  extração de `_coletar_proposicoes_ano` (helper privado) para evitar
  recursão na API pública; `coletar_proposicoes` ganha parâmetro
  keyword-only opcional `checkpoint: CheckpointCamara | None = None`,
  que permite pular anos já marcados em `anos_concluidos` -- novo campo
  `set[tuple[int, int]]` em `CheckpointCamara`. `max_itens` é honrado
  globalmente entre os 4 anos (não por ano). Compatibilidade com
  checkpoints legacy (sem `anos_concluidos`) preservada via Pydantic
  `default_factory=set`. Logging por ano facilita diagnóstico de
  retomada após `kill -9`. 10 testes novos (6 unit em `coleta_camara`,
  3 unit em `coleta_checkpoint`, 1 integração de retomada granular) +
  1 bônus que valida pular ano via `checkpoint.anos_concluidos`.

### Adicionado

- **S36 -- Paridade Windows com `install.bat` + `run.bat`.** Hemiciclo agora
  é instalável nativamente em Windows 10/11 sem WSL: o usuário Windows
  clona o repo, executa ``install.bat`` (CMD ou PowerShell) e em seguida
  ``run.bat``, e vê o dashboard Streamlit abrir em ``localhost:8501``
  exatamente como no Linux/macOS. Os scripts `.bat` usam CRLF + UTF-8 +
  ``chcp 65001`` (mensagens PT-BR com acentos íntegros), detectam Python
  3.11+ em cascata (``where python`` -> ``py -3.11`` -> erro com link
  ``python.org``), instalam ``uv`` via instalador oficial PowerShell e
  rodam ``uv sync --all-extras``. Modo ``--check`` (espelha
  ``install.sh``) valida o ambiente sem instalar -- usado pelo CI smoke
  no runner ``windows-2022``. ADR-014 (Python pré-instalado) honrado:
  scripts não auto-instalam Python, apenas detectam e orientam.
  ``docs/usuario/instalacao.md`` ganhou seção Windows 10/11 completa com
  troubleshooting (Defender, PATH, encoding cp1252, paths com espaços);
  ``README.md`` apresenta os três SOs lado a lado na "Instalação rápida".
  15 testes unit cross-OS validam estrutura dos `.bat` (CRLF, UTF-8,
  ``chcp``, ``@echo off``, paridade de comandos canônicos, acentuação
  PT-BR consistente) + 3 testes de integração Windows-only (smoke real
  de ``install.bat --check``). Última sprint bloqueante de release
  público amplo do Hemiciclo 2.1.x.
- **S23.1 -- Fontes auto-hospedadas (Inter + JetBrains Mono).** Bundla 6 TTFs
  sob SIL Open Font License 1.1 em
  ``src/hemiciclo/dashboard/static/fonts/`` -- 4 pesos Inter v4.0 (Regular,
  Medium, SemiBold, Bold) + 2 pesos JetBrains Mono v2.304 (Regular, Bold).
  Carregados em runtime via ``_carregar_fontes_inline()`` (decorada com
  ``@st.cache_resource``), que codifica os TTFs em base64 e injeta
  ``@font-face`` data-URLs no header do dashboard. Zero rede em runtime
  (I1 do BRIEF), zero rastreio de Google Fonts sobre o cidadão usuário.
  Integridade verificada por SHA256 em ``scripts/baixar_fontes.py``
  (idempotente; ``make fonts`` valida 6/6 TTFs). LICENSE SIL OFL 1.1
  presente, README documenta origens oficiais. ADR-021 formaliza a
  decisão; ``docs/arquitetura/ui_design_tokens.md`` consolida paleta +
  tipografia + auto-hospedagem como referência única.
- **S27.1 -- ``votacoes.proposicao_id`` (Migration M002).** Destrava o JOIN
  ``votos × votacoes × proposicoes`` no classificador C1: a agregação de
  voto por parlamentar passa a retornar recall real em DBs com dados
  coletados pós-S27.1. Schema do parquet de votações ganha
  ``proposicao_id BIGINT`` na Câmara e renomeia ``materia_id ->
  proposicao_id`` no Senado (alinhamento com Câmara).
- ``hemiciclo.etl.schema.criar_schema(conn)`` -- atalho que aplica todas as
  migrations registradas (recomendado para fixtures e smoke locais).
- ``SCHEMA_VERSAO_ATUAL = 2`` -- constante refletindo a versão alvo do
  schema "vivo" pós-S27.1.
- ``scripts/migracao_m002.py`` -- utilitário CLI para aplicar M002 em DBs
  v1 existentes sem reconsolidar (idempotente, exit 0 em sucesso, exit 1
  em DB inexistente).
- 19 testes novos cobrindo M002 (idempotência, preservação de dados v1),
  schema v2, propagação de ``proposicao_id`` no consolidador (com compat
  retroativa para parquets ``materia_id``), normalizadores Câmara/Senado
  (com ``None`` em vez de ``0`` como sentinel) e fluxo e2e
  parquet → consolidador → classificador C1 sem ``ALTER TABLE`` manual.

### Alterado

- ``hemiciclo.modelos.classificador_c1.agregar_voto_por_parlamentar``: chama
  ``aplicar_migrations(conn)`` antes do JOIN. Removido o fallback dinâmico
  via ``information_schema.columns``: o JOIN é direto e DBs v1 antigos são
  auto-migrados na primeira chamada (com ``NULL`` em ``proposicao_id``).
- ``hemiciclo.coleta.camara._normalizar_votacao``: extrai ``proposicao_`` da
  API real (com fallback para ``proposicaoPrincipal_``) e retorna ``None``
  quando ausente (votação de requerimento interno, parecer, etc.). Nunca
  mais usa ``0`` como sentinel -- ``0`` é BIGINT válido e quebraria o JOIN.
- ``hemiciclo.coleta.senado._normalizar_votacao``: campo renomeado de
  ``materia_id`` para ``proposicao_id`` para alinhar com Câmara. Mesma
  semântica (``CodigoMateria`` do XML do Senado), mesmo tipo.
- ``hemiciclo.etl.consolidador._inserir_votacoes_camara``: detecta
  dinamicamente as colunas presentes no parquet -- aceita parquets v2
  (``proposicao_id``), parquets do Senado legado (``materia_id``, mapeado
  via alias) e parquets ainda mais antigos sem nenhuma das duas (preenche
  ``NULL``).

### Documentação

- ``docs/arquitetura/cache_e_db.md`` documenta schema v2 e o utilitário
  ``scripts/migracao_m002.py``.
- ``docs/arquitetura/classificacao_multicamada.md`` substitui a seção
  "limitação atual" pela seção "compatibilidade retroativa S27.1".

## [2.0.0] - 2026-04-28

### Highlights

- **Hemiciclo 2.0.0** -- primeira release pública da plataforma cidadã de
  perfilamento parlamentar em Python + Streamlit + DuckDB + Polars, fechando
  17 sprints (S22-S38) ao longo do ciclo R2.
- **Pipeline cidadão ponta a ponta:** instalação em dois comandos, coleta
  resiliente das APIs Câmara + Senado, classificador multicamada (regex +
  voto + embeddings + LLM opcional), Sessão de Pesquisa persistente em
  subprocess detached, dashboard com 6 widgets visuais, exportação samizdat
  via zip auditável SHA256.
- **Rigor metodológico aberto:** 477 testes verdes em CI multi-OS
  (Linux + macOS + Windows × Python 3.11 + 3.12), cobertura ≥ 90%, mypy
  `--strict` zero erros, ruff zero violações, `random_state=42` propagado em
  todos os modelos para reprodutibilidade bit a bit cross-máquina.
- **Documentação completa:** 20 ADRs no formato MADR adaptado, manifesto
  político longo (~1500 palavras), guias de instalação / primeira pesquisa /
  interpretação do relatório / exportação / arquitetura de cada subsistema
  modular.
- **Soberania radical:** zero servidor central, zero rastreio, zero
  dependência de API paga, GPL v3 garantindo abertura permanente.

### Invariantes da release

- I1 -- Tudo local (ADR-006).
- I2 -- PT-BR sem perda em texto visível ao usuário.
- I3 -- Determinismo (ADR-018, `random_state=42`).
- I9 -- Cobertura ≥ 90% sobre `src/hemiciclo/`.
- I10 -- Conventional Commits (ADR-017).
- I12 -- CHANGELOG sempre atualizado.

### Adicionado (S34 -- ML de convertibilidade)

- feat(s34): entrega do eixo `convertibilidade` da assinatura multidimensional (D4 / ADR-004) -- modelo `LogisticRegression` (sklearn) treinado sobre features de S33 + S32 + S27, com proof-of-work runtime real e caveats metodológicos publicizados (manifesto político: rigor científico sem maquiagem).
- `src/hemiciclo/modelos/convertibilidade.py` (~640 linhas) com 2 classes públicas + 2 exceções + 1 helper end-to-end:
  - `ExtratorFeatures.extrair(sessao_dir)` -- lê os 3 artefatos JSON da sessão (`historico_conversao.json` da S33, `metricas_rede.json` da S32, `classificacao_c1_c2.json` da S27) e devolve `polars.DataFrame` com features (`indice_volatilidade`, `centralidade_grau`, `centralidade_intermediacao`, `proporcao_sim_topico`, `n_votos_topico`) + target binário `mudou_recentemente`. Tolerante: artefatos ausentes geram DataFrame vazio (skip graceful), entradas com tipos errados são ignoradas sem quebrar.
  - `ModeloConvertibilidade` (`@dataclass`) -- `treinar(X, y)` classmethod com split 70/30 estratificado (`random_state=42` em 3 pontos: `train_test_split`, `LogisticRegression`, solver `lbfgs` determinístico), `prever_proba(X)` retorna `pl.Series[Float64]` em [0, 1], `salvar(dir)` grava `joblib + meta.json` com SHA256 (precedente S28), `carregar(dir)` valida hash e versão antes de desserializar, `coeficientes()` retorna dict feature->coef como proxy de SHAP. Métricas registradas: accuracy, precision (`zero_division=0`), recall (`zero_division=0`), f1 (`zero_division=0`), roc_auc (defesa: 0.0 se `y_te` tem 1 classe), n_treino, n_teste.
  - `IntegridadeViolada` (Exception) levantada em hash divergente / versão incompatível.
  - `AmostraInsuficiente` (Exception) levantada em < 30 amostras, monoclasse em y, ou colunas faltando em X.
  - `treinar_convertibilidade_sessao(sessao_dir, top_n=100)` -- helper end-to-end que extrai features, treina, persiste `joblib + meta.json` em `<sessao_dir>/modelo_convertibilidade/` e ranqueia top N em `<sessao_dir>/convertibilidade_scores.json`. Skip graceful exposto via `{"skipped": true, "motivo": "..."}` -- nunca levanta para o caller.
- `src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py` -- widget Streamlit com tabela ranqueada (top 50 default), 2 colunas com `ProgressColumn` amarela-ouro (probabilidade prevista + volatilidade histórica), expansível com coeficientes da regressão para interpretabilidade. Cabeçalho informa amostra + accuracy + F1 + ROC-AUC e linka para o doc de caveats. Tolerante: `None`, `skipped=True` e lista vazia caem em `st.info` neutro.
- `src/hemiciclo/sessao/pipeline.py` ganha `_etapa_convertibilidade` (95-98%) entre `_etapa_historico` e `_etapa_relatorio`. Só roda se `params.incluir_convertibilidade=True` (default `False` -- custo controlado). Skip graceful em 3 caminhos: features vazias, amostra < 30, erro inesperado. Persiste sempre `convertibilidade_scores.json` (mesmo SKIPPED) para o dashboard ter sentinela.
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` ganha `_renderizar_secao_convertibilidade(sessao_dir)` chamada de dentro de `_renderizar_concluida`. Banner honesto sobre limitações metodológicas (target proxy, vazamento parcial, correlacional não causal, amostra pequena) com link para `docs/arquitetura/convertibilidade.md`.
- `src/hemiciclo/cli.py` ganha grupo Typer `convertibilidade` com 2 subcomandos:
  - `treinar <id_sessao> [--top-n 100]` -- treina e persiste o modelo + scores. Exit 0 em SKIPPED graceful (amostra insuficiente / sem features), exit 2 só para sessão inexistente.
  - `prever <id_sessao>` -- recarrega modelo já treinado (validando SHA256), regenera apenas scores. Exit 1 para `IntegridadeViolada`, exit 2 para sessão / modelo inexistente.
- 32 testes novos: 22 unit em `tests/unit/test_modelos_convertibilidade.py` (extrator com 3 artefatos, sem histórico, sem grafo, grafo skipped, entradas inválidas, JSON corrompido, treino determinístico com `random_state=42`, métricas no intervalo, `prever_proba` em [0,1], amostra insuficiente, monoclasse, colunas ausentes, coeficientes, salvar/carregar round-trip, hash divergente, versão incompatível, arquivo ausente, `prever_proba` DataFrame vazio, helper sucesso/skipped) + 4 unit em `tests/unit/test_dashboard_widget_convertibilidade.py` (None, skipped, lista vazia, lista preenchida com renderização real) + 3 e2e em `tests/integracao/test_convertibilidade_e2e.py` (etapa em sessão real, skip graceful sem artefatos, CLI ponta-a-ponta) + 3 sentinelas em `tests/unit/test_sentinela.py` (`convertibilidade --help`, `convertibilidade treinar --help`, sessão inexistente).
- `pyproject.toml` -- nenhuma dep nova: `scikit-learn>=1.4` e `joblib>=1.3` já presentes desde S28.
- `docs/arquitetura/convertibilidade.md` documenta pipeline, skip graceful, caveats metodológicos honestos, instrução de leitura do ranking no dashboard, comandos CLI, ADRs vinculados.
- 477 testes passando (444 baseline + 33 S34); cobertura total ≥ 90.22% (`make check` verde); cobertura S34: `convertibilidade.py` 95%, `ranking_convertibilidade.py` ≥ 95%.
- Branch `feature/s34-ml-convertibilidade`, sem push automático.

### Adicionado (S33 -- Histórico de conversão por parlamentar)

- feat(s33): entrega do eixo `volatilidade` da assinatura multidimensional (D4 / ADR-004) -- alimenta a S34 (ML de convertibilidade) com a primeira feature temporal real do produto.
- `src/hemiciclo/modelos/historico.py` (~360 linhas) com 3 classes públicas + 1 exceção + 1 helper batch:
  - `HistoricoConversao.calcular(conn, parlamentar_id, casa, granularidade)` -- agrupa votos por bucket temporal (`ano` ou `legislatura`), calcula `proporcao_sim`/`proporcao_nao`/`posicao_dominante` por bucket. SQL `JOIN votos x votacoes via (votacao_id, casa)` (precedente S32), `UPPER(v.voto) = 'SIM'` (valores brutos `Sim`/`Nao`/`Abstencao`/`Obstrucao`/`Art.17`), `TRY_CAST(vt.data AS DATE)` defensivo contra VARCHAR malformado. `HAVING n_votos >= 5` filtra buckets pobres.
  - `DetectorMudancas.detectar(historico, threshold_pp=30.0)` -- compara buckets adjacentes; mudança = `abs(delta_pp) >= threshold`. Sinal preservado (positivo = mais SIM).
  - `IndiceVolatilidade.calcular(historico)` -- `std_populacional(proporcao_sim) / 0.5` saturado em 1.0. Std máxima teórica de série binária 0/1 é 0.5.
  - `AmostraInsuficiente` (Exception, noqa N818 por precedente S32) levantada quando tabela `votos` ausente.
  - `calcular_historico_top(conn, top_n=100, granularidade, threshold_pp)` -- helper batch sobre os top N parlamentares mais ativos (ORDER BY COUNT desc), retornando dict canônico pronto pra `historico_conversao.json`.
  - Limiares de posição idênticos a `classificador_c1` (0.70/0.30) -- coerência cross-sprint.
- `src/hemiciclo/dashboard/widgets/timeline_conversao.py` -- substitui o stub S31 por implementação real. Plotly `Scatter(mode="lines+markers")` com cor de marker por posição (verde-folha = a_favor, vermelho-argila = contra, cinza-pedra = neutro), anotações com seta amarelo-ouro em cada mudança detectada (`+/-Npp`), eixo Y formatado como porcentagem `[0%, 100%]`. Caption resume `indice_volatilidade` + número de mudanças. Skip graceful em 3 caminhos: dict ausente, parlamentar não encontrado, < 2 buckets.
- `src/hemiciclo/sessao/pipeline.py` ganha `_etapa_historico` (93-95%) entre `_etapa_grafos` e `_etapa_relatorio`. Lazy import de `duckdb` e `calcular_historico_top`. Skip graceful em 3 níveis: `dados.duckdb` ausente, erro inesperado em runtime, `metadata.skipped` propagado do helper. Persiste `<sessao_dir>/historico_conversao.json` UTF-8 indent=2 (lição S32 -- Windows cp1252).
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` ganha `_renderizar_secao_historico(sessao_dir)` chamada de dentro de `_renderizar_concluida`. Selectbox dos top 20 parlamentares mais voláteis (ordenação desc por `indice_volatilidade`), label `"<nome> (volatilidade=0.42)"`, timeline Plotly do parlamentar selecionado, lista de mudanças detectadas com formato `2018 -> 2024: -60pp (a_favor -> contra)`. Tolerante a JSON ausente, JSON corrompido, SKIPPED.
- `src/hemiciclo/cli.py` ganha grupo Typer `historico` com subcomando `calcular <id_sessao> [--granularidade ano|legislatura] [--threshold-pp 30] [--top-n 100]`. Exit 0 mesmo em SKIPPED graceful (sem `dados.duckdb` no diretório); exit 2 para sessão inexistente ou granularidade inválida.
- 16 testes novos: 15 unit em `tests/unit/test_modelos_historico.py` (granularidade ano/legislatura, posição dominante, threshold padrão/customizado, volatilidade consistente=0/errática=1, skip graceful por tabela ausente / parlamentar inexistente / DB sem votos, batch helper) + 6 unit em `tests/unit/test_dashboard_timeline_conversao.py` (Plotly chamado, anotações de mudança, dados vazios, parlamentar inexistente, único bucket, cor por posição) + 5 e2e em `tests/integracao/test_historico_e2e.py` (pipeline gera JSON em sessão real, skip graceful sem DB, CLI ponta-a-ponta com sessão real, CLI SKIPPED, dashboard renderiza seção histórico) + 4 sentinelas (`historico --help`, `historico calcular --help`, sessão inexistente, granularidade inválida). Test stub S31 do widget (`test_timeline_stub_mostra_placeholder`) atualizado para refletir comportamento real (`test_timeline_sem_historico_emite_info`).
- Sem dependências runtime novas. Sem overrides mypy adicionais.
- `docs/arquitetura/historico_conversao.md` documenta granularidades, detecção de mudanças, índice de volatilidade, limitação atual (depende de S27.1 para filtragem por tópico), schema do JSON e decisões fundamentais.
- Branch `feature/s33-historico-conversao`, sem push automático.

### Adicionado (S32 -- Grafos de rede: coautoria + voto + pyvis embedável)

- feat(s32): entrega do eixo `centralidade` da assinatura multidimensional (D4) via 2 grafos parlamentares complementares (coautoria + afinidade de voto), calculados em `networkx`, visualizados em `pyvis` HTML standalone interativo embedado no Streamlit.
- `src/hemiciclo/modelos/grafo.py` (~330 linhas) com 3 classes públicas e 1 exceção:
  - `GrafoCoautoria.construir(conn, peso_minimo=5)` -- proxy honestamente documentado: enquanto S27.1 não traz `votacoes.proposicao_id`, "coautoria" é aproximada por "votar nas mesmas votações". Peso = contagem de votações compartilhadas, corte mínimo 5.
  - `GrafoVoto.construir(conn, peso_minimo=0.5)` -- afinidade de posição calculada via SQL DuckDB (`SUM(CASE WHEN v1.voto = v2.voto THEN 1 ELSE 0 END) / COUNT(*)`), peso ∈ [0, 1].
  - `MetricasGrafo` -- `calcular_centralidade` (degree centrality), `detectar_comunidades` (Louvain via `python-louvain` com `random_state=42` ou fallback `nx.community.greedy_modularity_communities` se `community` ImportError), `tamanho_maior_componente`, `aplicar_atributos` (anota cada nó in-place com centralidade + comunidade), `top_centrais(top_n=10)`, `filtrar_top(max_nos=200)` (poda para pyvis legível).
  - `AmostraInsuficiente` (Exception) levantada em < 5 nós ou tabela `votos` ausente -- caller trata como SKIPPED graceful, jamais erro fatal.
- `src/hemiciclo/modelos/grafo_pyvis.py` (~115 linhas) com `renderizar_pyvis(grafo, html_path, titulo)`. Usa `pyvis.network.Network` com `cdn_resources="in_line"` (HTML 100% standalone, zero dep externa em runtime), paleta institucional do `tema.py` ciclando entre 6 cores por comunidade, tamanho de nó proporcional à centralidade (`10 + 30 * cent`), tooltip com `nome (partido/UF)`, layout `barnes_hut` com parâmetros estáveis. Grafo vazio gera HTML placeholder coerente com a paleta (não levanta).
- `src/hemiciclo/dashboard/widgets/rede.py` -- widget `renderizar_rede(html_path, altura=600)` lê o HTML como string e injeta via `st.components.v1.html(conteudo, height=altura, scrolling=False)`. Tolerante: arquivo ausente → `st.info` amigável; OSError → `st.warning`.
- `src/hemiciclo/sessao/pipeline.py` ganha `_etapa_grafos` (88-93%) entre C3 e relatório, honrando `params.incluir_grafo` (default True). Skip graceful em três níveis: dados.duckdb ausente, AmostraInsuficiente por tipo, erro inesperado por tipo. Persiste `grafo_coautoria.html`, `grafo_voto.html` e `metricas_rede.json` (top 10 mais centrais + n_nos + n_arestas + maior_componente + n_comunidades por tipo).
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` ganha seção "Redes de coautoria e voto" via `_renderizar_secao_redes(sessao_dir)`. 3 tabs Streamlit (`Coautoria`, `Voto`, `Métricas`). Cada tab tolera SKIPPED graceful (mostra aviso) e renderiza top centrais via `st.dataframe`. `_renderizar_concluida` ganha parâmetro opcional `sessao_dir` para roteamento à seção.
- `src/hemiciclo/cli.py` ganha subcomando `hemiciclo rede analisar <id> [--tipo coautoria|voto|ambos]`. Útil para sessões antigas (anteriores à S32) ou para regenerar grafos sem rodar o pipeline inteiro. Exit 0 em SKIPPED graceful, exit 2 só para sessão inexistente / dados.duckdb ausente / tipo inválido.
- 23 testes novos: 13 unit em `tests/unit/test_modelos_grafo.py` + 4 unit em `tests/unit/test_modelos_grafo_pyvis.py` + 3 unit em `tests/unit/test_dashboard_widget_rede.py` + 3 e2e em `tests/integracao/test_grafos_e2e.py`.
- 4 sentinelas adicionadas: `test_rede_help`, `test_rede_analisar_help`, `test_rede_analisar_sessao_inexistente`, `test_rede_analisar_tipo_invalido`.
- Suite cresce de 378 para 401 testes; cobertura mantida ≥ 90%.
- 3 dependências runtime novas: `networkx>=3.2` (já transitivo, formalizado), `pyvis>=0.3`, `python-louvain>=0.16`. mypy overrides para `networkx`, `pyvis`, `community`.
- `docs/arquitetura/grafos_redes.md` documenta os 2 grafos, algoritmos (Louvain + degree centrality), limitações conhecidas (S27.1 dependency, proxy de coautoria) e como interpretar comunidades.
- Branch `feature/s32-grafos-rede`, sem push automático.

### Adicionado (S35 -- Exportação/importação de sessão: zip stdlib + verificação SHA256 contra manifesto)

- feat(s35): primeira jornada cidadã ponta-a-ponta de compartilhamento de sessão. Pesquisadora A roda análise localmente, exporta zip (50-200 KB), envia por email/USB/drive, pesquisadora B importa e abre no próprio dashboard sem refazer coleta nem confiar cegamente nos bytes.
- `src/hemiciclo/sessao/exportador.py` (~260 linhas) substitui o stub S29: 3 funções públicas (`exportar_zip`, `exportar_zip_bytes`, `importar_zip` com kw-only `validar=True`) + 1 exception (`IntegridadeImportadaInvalida`) + 3 helpers internos (`_artefatos_persistentes`, `_resolver_id_unico`, `_validar_manifesto`).
- `zipfile.ZipFile(..., compression=ZIP_DEFLATED)` da stdlib -- zero dependência nova. `exportar_zip_bytes` usa `io.BytesIO` para gerar bytes in-memory, alimentando o `st.download_button` do dashboard sem tocar disco.
- Seleção consciente de artefatos: o zip **inclui** `params.json`, `status.json`, `manifesto.json`, `relatorio_state.json`, `classificacao_c1_c2.json`, `c3_status.json`, parquets de `raw/`. **Exclui** `dados.duckdb` (regenerado pelo consolidador), `modelos_locais/` (regenerado por re-projeção C3), `pid.lock` e `log.txt` (efêmeros).
- Validação de integridade compara SHA256 truncado em 16 chars (precedente S24/S25/S26/S30 confirmado em S25.1) de cada artefato extraído contra o registrado em `manifesto.json`. Entradas do manifesto que apontam para arquivos intencionalmente excluídos do zip (como `dados.duckdb`) são puladas silenciosamente -- o manifesto descreve a sessão original, não o zip. Hash divergente levanta `IntegridadeImportadaInvalida` com mensagem `Hash divergente em <path>: calculado=<sha> esperado=<sha>`.
- `_resolver_id_unico` sufixa `_2`, `_3` etc se o id já existe -- jamais sobrescreve sessão pré-existente.
- CLI ganha 2 subcomandos novos: `hemiciclo sessao exportar <id> [--destino <path>]` (default `~/Downloads/<id>.zip`) reportando `sessao exportar: zip=<path> tamanho=<KB> artefatos=<n>`, e `hemiciclo sessao importar <zip> [--sem-validar]` reportando `sessao importar: sessao=<id_final> validacao=<OK|pulada>`. Tratamento granular de `BadZipFile` (exit 2) e `IntegridadeImportadaInvalida` (exit 1).
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` substitui o botão stub `st.info("Exportação completa chega em S35.")` por `st.download_button(label="Exportar zip", data=<bytes>, file_name="<id>.zip", mime="application/zip", disabled=not zip_bytes)` lendo bytes via `exportar_zip_bytes` no momento do render. Adicionado parâmetro `sessao_dir: Path` em `_renderizar_header_sessao`.
- `src/hemiciclo/dashboard/paginas/importar.py` (98 linhas) é página nova com `st.file_uploader(type=["zip"])`, checkbox "Pular validação de integridade", botão `Importar` com persistência via `tempfile.NamedTemporaryFile` + `Path` para a função, mensagens claras de erro (`zipfile.BadZipFile`, `IntegridadeImportadaInvalida`, `OSError`) e redirect via `st.session_state["pagina_ativa"] = "sessao_detalhe"` ao sucesso.
- `src/hemiciclo/dashboard/app.py` registra a rota interna `importar` em `PAGINAS_INTERNAS` (ao lado de `sessao_detalhe`) -- alcançável via `session_state` mas sem botão na navegação top.
- `src/hemiciclo/dashboard/tema.py` ganha entrada `STORYTELLING["importar"]` ("Importe a sessão de outro pesquisador como se fosse sua. Verificamos a integridade dos artefatos antes de abrir -- zero confiança cega.").
- `src/hemiciclo/sessao/__init__.py` re-exporta `IntegridadeImportadaInvalida`, `exportar_zip`, `exportar_zip_bytes`, `importar_zip`.
- 18 testes novos: 12 unit em `tests/unit/test_sessao_exportador.py` reescrito (gera_zip, exclui_efemeros, inclui_manifesto, pasta_inexistente, bytes_em_memoria, ordenação determinística, extrai_corretamente, valida_hash_ok, recusa_hash_adulterado, sem_validar_aceita_adulterado, id_colidindo_gera_sufixo, sem_manifesto_nao_falha, manifesto_corrompido_levanta) + 4 unit em `tests/unit/test_dashboard_importar.py` novo (renderiza uploader via AppTest, sucesso com mock de UploadedFile, erro em zip inválido, erro em hash adulterado) + 3 e2e em `tests/integracao/test_export_import_e2e.py` novo (round_trip preserva bytes idênticos, zip_adulterado falha import, workflow CLI ponta-a-ponta com `HEMICICLO_HOME` por monkeypatch) + 2 sentinelas (`test_sessao_exportar_help`, `test_sessao_importar_help`) + sentinela `sessao --help` cobre 8 subcomandos (era 6).
- Suite cresce de 360 para 378 testes; cobertura 90.07% (≥ 90% exigido). `make check` verde em ~36s (ruff + format + mypy --strict + pytest com cobertura). `exportador.py` individualmente em 97% de cobertura.
- **Smoke real validado** em home temporária `/tmp`: (1) `seed_dashboard` cria 3 sessões fake; (2) `hemiciclo sessao exportar _seed_concluida --destino /tmp/_seed_concluida.zip` produz `2.6KB, 5 artefatos`; (3) `hemiciclo sessao importar /tmp/_seed_concluida.zip --sem-validar` extrai como `_seed_concluida_2` (sufixo por colisão); (4) sessão sintética com manifesto coerente importa com `validacao=OK`; (5) zip com 1 byte de `params.json` adulterado falha import com `Hash divergente em params.json: calculado=82c95939f435e43b esperado=1f8283f1d579c265`.
- `IntegridadeImportadaInvalida` mantém nome em PT-BR sem sufixo `Error` (precedente `IntegridadeViolada` em `persistencia_modelo.py`), suprimindo N818 com `noqa`.
- `docs/usuario/exportar_compartilhar.md` cobre jornada típica (dashboard ou CLI), o que vai/não vai no zip, importação dos dois lados, verificação de integridade, conflito de id, e a filosofia samizdat: o zip é o artefato cidadão portável, sem servidor central, sem rede social, copia-e-manda.
- Branch `feature/s35-export-import`, sem push automático.

### Adicionado (S31 -- Dashboard sessão: relatório multidimensional + word clouds + séries)

- feat(s31): primeira entrega visual com dados reais ao usuário cidadão. Conecta o dashboard Streamlit aos artefatos JSON produzidos pelo `pipeline_real` da S30 (`params.json` + `status.json` + `relatorio_state.json` + `manifesto.json` + `classificacao_c1_c2.json`).
- `src/hemiciclo/dashboard/widgets/__init__.py` marker do pacote de widgets.
- `src/hemiciclo/dashboard/widgets/word_cloud.py` -- `renderizar_word_cloud(textos, titulo, max_palavras=100, cor_dominante=None)` usa `wordcloud.WordCloud` com `background_color=tema.BRANCO_OSSO`, `color_func` retornando uma cor única (default `tema.AZUL_HEMICICLO`), `random_state=42` (I3) e conjunto de 60+ stop words PT-BR mínimas embutidas. Renderiza PNG via PIL → BytesIO → `st.image`. Lista vazia ou strings só com espaço caem em `st.info` sem quebrar.
- `src/hemiciclo/dashboard/widgets/radar_assinatura.py` -- `renderizar_radar(parlamentares, eixos=None, top_n=20, titulo)` usa Plotly `Scatterpolar` com até 7 eixos do D4 do plano R2 (`posicao`, `intensidade`, `hipocrisia`, `volatilidade`, `centralidade`, `convertibilidade`, `enquadramento`). Eixos rotulados `(em SXX)` para os 5 ainda não disponíveis (chegam em S32/S33/S34/S34b). Polígono fechado repetindo primeira coordenada; range polar fixo `[0, 1]` com tickformat de %; default `top_n=20` para performance.
- `src/hemiciclo/dashboard/widgets/heatmap_hipocrisia.py` -- `renderizar_heatmap(parlamentares, topico, top_n=50, titulo)` usa Plotly `Heatmap` com escala divergente `[VERMELHO_ARGILA, CINZA_AREIA, VERDE_FOLHA]` (zmin=0, zmax=1). Na S31 o eixo X é único (recorte da sessão); em S33/S38 ganha múltiplos tópicos.
- `src/hemiciclo/dashboard/widgets/timeline_conversao.py` -- stub `renderizar_timeline_conversao(parlamentar_id, dados=None)` emite `st.info` apontando S33 (anti-débito do plano R2 §10).
- `src/hemiciclo/dashboard/widgets/progresso_sessao.py` -- `renderizar_progresso(status, etapa_atual, mensagem, eta_segundos=None)` mostra barra de progresso, caption da mensagem e lista canônica de 6 etapas (`CRIADA → COLETANDO → ETL → EMBEDDINGS → MODELANDO → CONCLUIDA`) com símbolos `[OK]`, `[em andamento]`, `[pendente]` colorizados. ETA formatado humano (`~2min`, `~1h30min`, `--`).
- `src/hemiciclo/dashboard/widgets/top_pro_contra.py` -- `renderizar_top(top_a_favor, top_contra, top_n=100)` desenha duas colunas Streamlit com cabeçalho colorido (verde-folha/vermelho-argila) e `st.dataframe` com `column_config.ProgressColumn` para a coluna Score (formato `%.0f%%`). Lista vazia → `st.info`.
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` (294 linhas) -- página completa da S31. Lê `caminho_sessao(cfg.home, sessao_id)`, valida `params.json` antes de qualquer render, carrega `status.json + relatorio + manifesto` tolerante a ausência. Header com `← Voltar`, tópico+badge de estado, caption `casas · UFs · legislaturas · sessão` e botão `Exportar` (stub apontando S35). Estado `concluida` renderiza top a-favor/contra + radar + heatmap + 2 word clouds + lista de limitações conhecidas. Estado em andamento entra em loop de polling 2 s via `st.empty() + placeholder.container()` que sai assim que o estado vira terminal e força `st.rerun()`. Estados `erro`, `interrompida`, `pausada` mostram mensagem clara + botões retomar/voltar.
- `src/hemiciclo/dashboard/paginas/lista_sessoes.py` -- ganha botão "Abrir relatório" por card que seta `session_state["sessao_id"]` + `session_state["pagina_ativa"] = "sessao_detalhe"` + `st.rerun()`.
- `src/hemiciclo/dashboard/app.py` -- distingue `PAGINAS` (4 abas top: intro, lista_sessoes, nova_pesquisa, sobre) de `PAGINAS_INTERNAS` (rota `sessao_detalhe` invocável apenas por session_state, sem botão na nav). Roteador resolve por dict-lookup com fallback seguro pra intro em chave desconhecida.
- `src/hemiciclo/dashboard/tema.py` -- extensão: `STORYTELLING["sessao_detalhe"]` ("Relatório multidimensional da pesquisa..."), `CORES_EIXOS` mapeando cada um dos 7 eixos a uma cor da paleta institucional (azul-hemiciclo, amarelo-ouro, vermelho-argila, azul-claro, verde-folha, marrom terra `#8B5A3C`, cinza-pedra) e tupla `EIXOS_ASSINATURA = tuple(CORES_EIXOS.keys())`.
- `scripts/seed_dashboard.py` (~210 linhas) -- popula `~/hemiciclo/sessoes/` com 3 sessões fake prefixadas `_seed_*` para nunca colidirem com sessões reais do dev. `_seed_concluida` (CONCLUIDA, params=aborto, top de 8 a-favor + 8 contra com nomes inspirados em mockups do plano R2, manifesto com `limitacoes_conhecidas=["S24b","S24c","S25.3","S27.1"]`), `_seed_em_andamento` (COLETANDO 30%, `etapa_atual="coleta_camara"`, mensagem "página 12 de 47"), `_seed_erro` (ERRO 15%, mensagem `HTTPError: 503 Service Unavailable em /proposicoes`). Determinismo garantido via `random.Random(42)` (I3).
- `tests/unit/test_dashboard_widgets.py` -- 15 testes mockando `pytest-mock` em cada chamada Streamlit: word cloud (renderiza, lista vazia, strings em branco), radar (4 parlamentares, lista vazia, top_n limita traços), heatmap (vazia, com dados), timeline (stub menciona S33 e id), progresso (renderiza barra+caption+md, ETA `None` → `--`, parametrize com 6 estados canônicos), top (2 colunas, lista vazia → `st.info`, top_n respeitado).
- `tests/unit/test_dashboard_sessao_detalhe.py` -- 15 testes via `streamlit.testing.v1.AppTest.from_file(default_timeout=15)` cobrindo: carrega concluída sem exceção, renderiza top a-favor/contra, renderiza radar + storytelling, exibe mensagem clara em erro, exibe botão retomar em interrompida/pausada, artefato ausente vira warning, manifesto lista limitações, sem `sessao_id` mostra warning + botão voltar, sessão inexistente mostra erro, params corrompido vira erro claro, status ausente vira warning de inicialização, polling termina em estado terminal (mock `time.sleep`+`st.rerun`+`carregar_status`), polling status some emite `st.error`, `_carregar_json` lida com JSON inválido. `_FakeEmpty` simula `st.empty()` como context manager.
- `tests/integracao/test_dashboard_sessao_e2e.py` -- 3 testes carregando `scripts/seed_dashboard.py` via `importlib.util.spec_from_file_location` e validando fluxo ponta-a-ponta: app renderiza `_seed_concluida` com top a-favor/contra + tópico aborto, app renderiza `_seed_erro` com HTTP 503 visível, navegação lista → detalhe expõe ≥3 botões `abrir_sessao_*`.
- `tests/unit/test_sentinela.py` -- 1 sentinela nova `test_seed_dashboard_script_executavel` carrega `scripts/seed_dashboard.py` via importlib, roda `main()` em home isolada e verifica que as 3 pastas `_seed_*` foram criadas.
- Suite total cresce de **321 para 360 testes** (39 novos -- 17 acima dos 22 prometidos no spec); cobertura **90.42%** (≥ 90% exigido). `make check` verde em ~36s (ruff + format + mypy strict + pytest). `pyproject.toml` ganha overrides mypy `ignore_missing_imports` para `wordcloud` e `PIL`.
- **Smoke real validado** em http://localhost:8501 com Playwright (Chromium headless, viewport 1440×2400, `wait_for_selector + networkidle`):
  - Lista mostra 3 cards seed com badges coloridas (`ERRO` vermelho-argila, `COLETANDO` azul-claro com "progresso: 30%", `CONCLUIDA` verde-folha) e botões "Abrir relatório".
  - Página `_seed_concluida` (PNG 640 KB, sha256 `57bcaea0...`) renderiza header "aborto (concluida) · Casas: camara · UFs: todas · Legislaturas: 57 · Sessão: `_seed_concluida`", subhead "87 proposições analisadas · 513 parlamentares ranqueados", duas tabelas com 8 linhas ranqueadas cada com barra de score, radar polar com 16 traços (8+8) sobrepostos e eixos `posicao`/`intensidade` ativos + 5 marcados `(em SXX)`, heatmap divergente, 2 word clouds (verde-folha à esquerda com Bomfim/Sâmia/Rosário/Maria/Benedita; vermelho-argila à direita com Sóstenes/Gilberto/Biondini/Malta/Diego/Eros).
  - Página `_seed_erro` (PNG 49 KB, sha256 `082d65b1...`) mostra caixa vermelha "Erro na sessão `_seed_erro`: HTTPError: 503 Service Unavailable em /proposicoes" + botões "Retomar pesquisa" + "Voltar à lista".
  - Acentuação PT-BR íntegra em todos os screenshots (Sâmia, Talíria, Sóstenes, "está", "câmara", "sessão(ões)", "Início", "análise").
- Dependências runtime novas: `wordcloud>=1.9`, `pillow>=10.0`. Dependência indireta instalada pelo wordcloud: `matplotlib==3.10.9`. `uv.lock` regenerado.
- `docs/usuario/interpretando_relatorio.md` -- guia de leitura: significado de top a-favor/contra, mapeamento dos 7 eixos da assinatura por sprint (`posicao` e `intensidade` disponíveis; `hipocrisia`+`volatilidade` em S33; `centralidade` em S32; `convertibilidade` em S34; `enquadramento` em S34b), heatmap, word clouds, limitações conhecidas com referência a S24b/S24c/S25.3/S27.1, estados da sessão e como retomar via CLI, determinismo via `random_state=42` + SHA256 16-char.

### Adicionado (S30 -- Pipeline integrado: coleta -> ETL -> C1+C2+C3 -> projeção + persistência da sessão)

- feat(s30): orquestrador real conecta todos os subsistemas anteriores (S24/S25 coleta, S26 ETL, S27 C1+C2, S28 C3) em uma execução autocontida na pasta da sessão. Substitui `_pipeline_dummy` da S29 como callable default do `SessaoRunner`.
- `src/hemiciclo/sessao/pipeline.py` (419 linhas) -- `pipeline_real(params, sessao_dir, updater)` com mesma assinatura do `_pipeline_dummy`. Estrutura por etapas com `updater.atualizar()` em cada transição: validar (2%) -> coleta Câmara (10%) -> coleta Senado (22%) -> ETL (35%) -> C1+C2 (55%) -> C3 (70-88%) -> relatório (95%) -> CONCLUIDA (100%). Cada etapa em `try/except` no orquestrador: erro vira `EstadoSessao.ERRO` com mensagem `<TipoExc>: <texto>` e re-raise para o worker (S29) emitir exit 1.
- **Imports lazy por etapa** (precedente S28 com `WrapperEmbeddings`) -- `from hemiciclo.coleta.camara import executar_coleta` etc só carrega quando a etapa roda. Preserva boot do CLI ~200ms e permite mock cirúrgico via `monkeypatch.setattr("hemiciclo.<sub>.<fn>", mock)`.
- **C3 skip graceful** -- bge-m3 ausente, modelo base não treinado ou base com `IntegridadeViolada` não falham o pipeline. Apenas marcam `c3_status.json` com `skipped=True` + motivo, atualizam progresso para 85% e seguem para a etapa de relatório. Sessão termina CONCLUIDA mesmo sem C3.
- **`manifesto.json`** -- gerado em `_gerar_manifesto` com SHA256 truncado em 16 chars (precedente S24/S25 confirmado pela S25.1) de cada artefato `.parquet` / `.duckdb` / `.json` da sessão (excluindo o próprio manifesto), `criado_em` ISO 8601 UTC, `versao_pipeline = "1"` e lista `limitacoes_conhecidas = ["S24b", "S24c", "S25.3", "S27.1"]` documentando o que esta versão *ainda* não cobre.
- **`relatorio_state.json`** -- agregação final por `_agregar_relatorio` combinando `classificacao_c1_c2.json` + `c3_status.json` + parâmetros da sessão. Estrutura pronta para o dashboard de S31.
- **`_resolver_topico(topico)`** -- aceita path absoluto/relativo a YAML existente OU slug curto (ex: `"aborto"` -> `<cwd>/topicos/aborto.yaml`). Levanta `FileNotFoundError` em ambos os caminhos vazios.
- CLI `hemiciclo sessao iniciar` ATUALIZADA: default callable agora é `hemiciclo.sessao.pipeline:pipeline_real`. Flag `--dummy` opcional força o pipeline antigo da S29 (compat para testes locais sem rede). Saída inclui `pipeline=real` ou `pipeline=dummy` para diagnóstico.
- `src/hemiciclo/sessao/__init__.py` re-exporta `pipeline_real`, `LIMITACOES_CONHECIDAS` e `VERSAO_PIPELINE`.
- 19 testes novos: 15 `test_pipeline_real.py` (status em cada etapa, coletor por casa, ETL com paths corretos, C1+C2 invocada, C3 SKIPPED com bge-m3 ausente, C3 SKIPPED com modelo base ausente, persistência de relatório + manifesto, falha de API marca ERRO, tópico inexistente bloqueia antes de coleta, helpers `_resolver_topico` e `_gerar_manifesto`); 2 `test_pipeline_e2e.py` (in-process com mocks + subprocess via dummy callable -- compat S29 garantida); 2 sentinelas adicionais (`sessao iniciar --help` documenta `--dummy`, `--dummy` explícito funciona). Suite cresce de 302 para 321 testes; cobertura 90.29% (>= 90% exigido).
- `tests/integracao/test_sessao_e2e.py::test_workflow_iniciar_listar_status_cli` atualizado para usar `--dummy` explícito (caso contrário tentaria rede em CI).
- `make check` verde em ~34s (ruff + format + mypy --strict + pytest com cobertura).
- `docs/arquitetura/pipeline_integrado.md` -- diagrama das 5 etapas, mapeamento etapas -> EstadoSessao, tratamento de erro por etapa, layout final da pasta da sessão, decisões fundamentais (imports lazy + SHA256 16-char + skip graceful), smoke local opcional, testes, próximas sprints destravadas.

### Adicionado (S28 -- Modelo base v1 (C3): bge-m3 + PCA + persistência com SHA256)

- feat(s28): camada 3 do classificador multicamada (D11/ADR-011) -- modelo base global treinado uma vez sobre amostra estratificada do DuckDB unificado e persistido com validação de integridade SHA256.
- `src/hemiciclo/modelos/embeddings.py` -- `WrapperEmbeddings` com **lazy import** de `FlagEmbedding.BGEM3FlagModel` em `_garantir_modelo` (boot do CLI ~200ms vs ~5s sem lazy). Métodos `embed(textos) -> np.ndarray` shape (N, 1024) com `batch_size=64` e `embed_sparse(textos) -> list[dict]` para uso futuro. `_resolver_device` testa `torch.cuda.is_available` via lazy import; fallback `cpu` sem torch instalado. Função `embeddings_disponivel(dir)` checa presença de `*.safetensors` recursivamente sem importar a lib pesada.
- `src/hemiciclo/modelos/base.py` -- `ModeloBaseV1` (dataclass com PCA + n_componentes + feature_names `pc_0..pc_{N-1}` + versao "1" + treinado_em UTC + hash_amostra SHA256). `amostrar_estratificadamente(conn, n_amostra)` usa sintaxe DuckDB 1.x `USING SAMPLE reservoir(N ROWS) REPEATABLE (42)` (determinismo I3); tabela vazia ou inexistente retorna DataFrame vazio sem erro (smoke local). `treinar_base_v1(conn, embeddings, n_amostra=30000, n_componentes=50)` orquestra amostragem -> embed em batches -> PCA fit com `random_state=Configuracao().random_state`.
- `src/hemiciclo/modelos/persistencia_modelo.py` -- `salvar_modelo_base(modelo, dir)` serializa via `joblib.dump` em `base_v1.joblib`, calcula SHA256 streaming (chunks 8 KiB) e grava manifesto `base_v1.meta.json` (UTF-8 indent=2). `carregar_modelo_base(dir)` valida versão "1" + recalcula SHA256 e compara com `meta.json:hash_sha256` -- divergência levanta `IntegridadeViolada`. `info_modelo_base(dir)` lê apenas `meta.json` sem desserializar binário (CLI `info` barato).
- `src/hemiciclo/modelos/projecao.py` -- `projetar_em_base(modelo, X_local)` aplica apenas `modelo.transform` (nunca refit). Ajuste fino local fica em S30.
- `src/hemiciclo/modelos/topicos_induzidos.py` -- `WrapperBERTopic` stub com lazy import de `bertopic.BERTopic`. Método `treinar` levanta `NotImplementedError` (treino real em S30/S31).
- Subcomando `hemiciclo modelo base` no CLI Typer com 4 ações: `baixar` (pré-baixa bge-m3 ~2GB), `treinar --n-amostra --n-componentes --db-path` (treina e persiste em `~/hemiciclo/modelos/`), `carregar` (valida integridade e mostra stats), `info` (estado coerente sem carregar artefatos pesados).
- Dependências runtime novas: `FlagEmbedding>=1.3` (wrapper bge-m3), `joblib>=1.3` (persistência), `numpy>=1.26` (vetores). `uv.lock` regenerado com torch e dependências CUDA.
- Override mypy `ignore_missing_imports` estendido para `FlagEmbedding`, `torch`, `bertopic`, `joblib`.
- 33 testes novos: 9 `test_modelos_embeddings.py` (lazy import, embed dense, embed_sparse, cuda detect via mock, fallback cpu sem torch, device explícito, disponivel false/true), 8 `test_modelos_base.py` (PCA random_state=42, amostragem respeita N, REPEATABLE seed determinística, treino completo, n_componentes aplicado, transform idempotente, amostra vazia falha, tabela inexistente retorna vazio), 8 `test_modelos_persistencia.py` (salvar gera meta.json, hash_sha256 64-hex, round-trip transform identico, corrupção 1-byte detectada, versão diferente falha, arquivos ausentes FileNotFoundError, info sem/com modelo), 4 `test_modelos_topicos_induzidos.py` (init não carrega bertopic, treinar NotImplementedError, lazy import idempotente), 2 `test_modelos_e2e.py` (treinar->salvar->carregar->projetar com transform idêntico, ciclo cross-process), 3 sentinelas CLI (`modelo base --help` cobre 4 subcomandos, `treinar --help` documenta flags, `info` reporta estado coerente sem modelo). Suite total cresce de 269 para 302 testes; cobertura 90.09% (>= 90%).
- **REGRA DE OURO** documentada em `docs/arquitetura/modelo_base.md`: zero teste pode baixar o modelo bge-m3 real (~2GB). Todos os testes mockam `FlagEmbedding.BGEM3FlagModel` via `unittest.mock`.
- `make check` verde em ~32s (ruff + format + mypy --strict + pytest com cobertura).
- Smoke CLI local: `hemiciclo --version` em ~200ms (lazy import preservado), `hemiciclo modelo base info` retorna estado coerente sem modelo presente, `hemiciclo modelo base treinar --help` lista todas as flags.
- `docs/arquitetura/modelo_base.md` cobre escolha do bge-m3 (D9), determinismo triplo (amostragem + PCA + hash_amostra), arquivos persistidos com schema do `meta.json`, validação SHA256, política de mock em CI, smoke local manual.

### Adicionado (S29 -- Sessão de Pesquisa: runner subprocess + persistência + retomada)

- feat(sessao): runner subprocess + persistência + retomada (D7/ADR-007/ADR-013).
- `src/hemiciclo/sessao/persistencia.py` -- 7 funções de read/write da pasta `<home>/sessoes/<id>/`: `gerar_id_sessao` (slug ASCII + timestamp UTC microssegundos), `caminho_sessao`, `salvar_params/carregar_params`, `salvar_status/carregar_status`, `listar_sessoes` (ordenado iniciada_em desc, pula corrompidas), `deletar_sessao` (recusa path traversal). Toda escrita via `tempfile.NamedTemporaryFile + Path.replace` (precedente S24/S26).
- `src/hemiciclo/sessao/runner.py` -- `SessaoRunner` cria pasta + status CRIADA, `iniciar(callable_path)` spawnsa `python -m hemiciclo._sessao_worker --callable mod:func --sessao-dir <p>` via `subprocess.Popen` com `start_new_session=True` (POSIX) ou `CREATE_NEW_PROCESS_GROUP` (Windows), persiste `pid.lock` com PID + ISO timestamp. `StatusUpdater` preserva `iniciada_em` cacheado relendo o primeiro status, escreve atomicamente. `pid_vivo(pid_lock_path)` usa `psutil.pid_exists` + `psutil.Process(pid).status() != STATUS_ZOMBIE`. `_pipeline_dummy(params, sessao_dir, updater)` exercita 4 transições (COLETANDO/ETL/MODELANDO/CONCLUIDA) com sleep 0.5s entre; gera `dummy_artefato.txt` como marcador.
- `src/hemiciclo/_sessao_worker.py` -- entrypoint top-level (fora de `hemiciclo.sessao` pra evitar import circular) invocado via `python -m`. Argparse simples + `_resolver_callable("mod:func")` via `importlib.import_module + getattr` + verificação `callable()`. Captura `(ValueError, TypeError, ImportError, AttributeError)` na resolução e `Exception` no pipeline; em ambos os casos, marca status como ERRO com `{type}: {msg}` e exit 1.
- `src/hemiciclo/sessao/retomada.py` -- `ESTADOS_TERMINAIS = {CONCLUIDA, ERRO, INTERROMPIDA, PAUSADA}`, `detectar_interrompidas(home)` itera sessões e marca como interrompidas as que NÃO estão em terminal E `pid_vivo()` retorna False, ordenado iniciada_em desc. `marcar_interrompida(sessao_dir, motivo)` é idempotente (não-op em terminal), preserva `iniciada_em` original, zera `pid`. `retomar(home, id_sessao, callable_path)` relê `params.json`, instancia runner via `__new__` (preservando id da pasta original) e dispara novo subprocess.
- `src/hemiciclo/sessao/exportador.py` -- *stub* da S29: `exportar_zip` cria `.zip` excluindo `modelos_locais/`, `dados.duckdb`, `pid.lock` (usa `relativo.parts.replace("\\", "/")` pra cross-OS). `importar_zip` extrai pra `<home>/sessoes/<id>/`, recusa se destino existe. Manifesto + integridade ficam em S35.
- Subcomando `hemiciclo sessao` no CLI Typer com 6 ações: `iniciar --topico [--casas] [--legislatura] [--max-itens]` (cria sessão + dispara pipeline DUMMY), `listar`, `status <id>` (JSON formatado indent=2), `retomar <id>`, `pausar <id>` (SIGTERM), `cancelar <id>` (SIGKILL + INTERROMPIDA). Mensagens em formato `key=value` (lição S27 sobre `rich.markup` interpretar `[tag]` como style).
- Dependências runtime: `psutil>=5.9` (PID checking cross-OS). Dev: `types-psutil>=5.9`.
- 47 testes novos: 9 `test_sessao_persistencia.py` (id único, slug acentos, round-trip, atomic, ordenação, deletar, path traversal, corrompido, lista pula corrompida), 8 `test_sessao_runner.py` (cria pasta+arquivos, atomic write, preserva iniciada_em, pid vivo/morto/ausente/corrompido, subprocess real completa em ≤10s), 9 `test_sessao_retomada.py` (4 cenários detectar + 3 marcar + retomar real + estados terminais), 9 `test_sessao_worker.py` (resolver_callable 5 ramos + worker sem params + callable inválido + exceção pipeline + happy path em-processo), 5 `test_sessao_exportador.py` (zip metadados, exclui caches, importar OK/destino existe/zip ausente), 3 sentinelas (`sessao_help` cobre 6 subcomandos, `sessao_listar_vazio`, `sessao_status_inexistente`), 3 e2e em `tests/integracao/test_sessao_e2e.py` (pipeline dummy completa 100%, kill -9 marca INTERROMPIDA, ciclo CLI iniciar->listar->status). Suite total cresce de 222 para 269 testes; cobertura 91.18% (≥ 90%).
- `docs/arquitetura/sessao_de_pesquisa.md` -- layout pasta sessão, ciclo de vida com diagrama de estados, mecânica do subprocess detached por OS, detecção de morte via psutil, retomada idempotente, CLI, smoke local end-to-end, próximos passos S30/S31/S35.

### Adicionado (S27 -- Classificador multicamada C1+C2 + tópicos YAML)

- feat(s27): primeira entrega de valor analítico real do produto -- camadas 1 e 2 de classificação por tópico (D11/ADR-011 do plano R2).
- `topicos/_schema.yaml` em JSON Schema draft 2020-12 com 5 campos obrigatórios (`nome`, `versao`, `descricao_curta`, `keywords`, `regex`) e 9 opcionais (`mantenedor`, `categorias_oficiais_camara`, `categorias_oficiais_senado`, `proposicoes_seed`, `exclusoes`, `embeddings_seed`, `limiar_similaridade`).
- 3 tópicos seed: `topicos/aborto.yaml` (12 keywords, 6 regex, 4 categorias oficiais Câmara+Senado, 5 proposições seed -- PL 1904/2024, PL 882/2015, PL 5069/2013, PEC 29/2015, PL 1135/1991, 2 exclusões cobrindo 'aborto espontâneo' e uso metafórico 'aborto da emenda'), `topicos/porte_armas.yaml` (13 keywords, 5 regex, Estatuto do Desarmamento, exclui armas brancas/químicas/biológicas/nucleares), `topicos/marco_temporal.yaml` (9 keywords, 4 regex, exclui Marco Civil da Internet).
- `topicos/README.md` documentando como contribuir tópicos novos via PR.
- `scripts/validar_topicos.py` -- validador Python puro (stdlib + pyyaml + jsonschema), CLI + biblioteca, exit 0/1, mensagens descritivas em stderr. 4 verificações: schema, regex compila (`re.compile`), keywords não-vazias, `nome:` interno bate com filename.
- `src/hemiciclo/etl/topicos.py` -- carregador runtime: `Topico` Pydantic v2 frozen com `casa_keywords(ementa)` (aplica exclusões primeiro, depois keywords case-insensitive, depois regex como veio do YAML) e `casa_categoria_oficial(tema, casa)`. `regex_compilados` / `exclusoes_compiladas` como propriedades pré-compiladas.
- `src/hemiciclo/modelos/__init__.py` marker do pacote.
- `src/hemiciclo/modelos/classificador_c1.py` -- camada 1 determinística: `proposicoes_relevantes(topico, conn)` faz SQL `LOWER(ementa) LIKE` em keywords + `tema_oficial IN (...)` em categorias oficiais (DuckDB regex é POSIX ERE; evita), refinado por exclusões via Polars; `agregar_voto_por_parlamentar(props, conn)` detecta dinamicamente se `votacoes` tem coluna `proposicao_id` (S27.1). Sem ela, retorna DataFrame vazio com log de aviso e não bloqueia o classificador. Com ela, JOIN votos × votacoes × proposições_relevantes via TEMP TABLE produz `proporcao_sim` e `posicao_agregada` (`A_FAVOR >= 0.70`, `CONTRA <= 0.30`, `NEUTRO` entre).
- `src/hemiciclo/modelos/classificador_c2.py` -- camada 2 estatística leve: `tfidf_relevancia(props, max_features=100)` aplica `TfidfVectorizer` (sklearn) com input ordenado (`sort by casa,id`) para determinismo; sklearn é importado lazy. `intensidade_discursiva(parlamentar_id, casa, topico, conn)` conta discursos do parlamentar que casam o tópico via `Topico.casa_keywords` e normaliza por total -- frequência relativa em [0.0, 1.0].
- `src/hemiciclo/modelos/classificador.py` -- orquestrador: `classificar(topico_yaml, db_path, camadas, top_n, home)` valida camadas contra `CAMADAS_VALIDAS = {regex, votos, tfidf}`, aplica em cascata, persiste DataFrame de proposições em `<home>/cache/classificacoes/<topico>_<hash16>.parquet` (lição S26: cache transversal por hash) e devolve dict serializável com `top_a_favor`, `top_contra`, `n_props`, `n_parlamentares`, `cache_parquet`. `salvar_resultado_json` helper para `--output`.
- Subcomando `hemiciclo classificar` no CLI Typer com `--topico`, `--db-path`, `--camadas` (csv default `regex,votos,tfidf`), `--top-n` (default 100), `--output` (opcional, JSON UTF-8 indent=2). Mensagens de log usam `key=value` em vez de `[tag][nome]` para evitar `rich.markup` interpretar nomes de tópicos como style tags.
- Hook pre-commit `validar-topicos` ativado em `.pre-commit-config.yaml` (entry `python scripts/validar_topicos.py`, dispara em `topicos/*.yaml`).
- Step CI `Validar tópicos` ativado em `.github/workflows/ci.yml` rodando `uv run python scripts/validar_topicos.py` em todas as combinações OS×Python.
- 47 testes novos: 8 `test_validar_topicos.py`, 11 `test_topicos.py`, 8 `test_classificador_c1.py`, 6 `test_classificador_c2.py`, 8 `test_classificador.py`, 3 e2e `test_classificador_e2e.py`, 3 sentinelas. Suite total cresce de 175 para 222 testes; cobertura 92.46% (≥ 90% mantida).
- Dependências runtime novas: `scikit-learn>=1.4` (TfidfVectorizer), `pyyaml>=6.0` (load), `jsonschema>=4.20` (validação JSON Schema). `uv.lock` regenerado.
- Override mypy estende `ignore_missing_imports` para `sklearn` e `jsonschema`.
- `docs/arquitetura/classificacao_multicamada.md` documentando cascata C1-C4, schema YAML, função de cada camada, decisões fundamentais (regex Python não DuckDB, lazy import sklearn, cache por hash do DB), exemplos de output, smoke local end-to-end.
- Achado colateral: `sprints/SPRINT_S27_1_VOTACOES_PROPOSICAO_ID.md` -- nova sprint READY que adiciona `proposicao_id` à tabela `votacoes` (Migration M002) para destravar o JOIN de votos. Sem essa coluna, a camada de voto retorna agregação vazia mas o classificador continua funcional.

### Adicionado (S26 -- Cache transversal + DuckDB)

- feat(etl): cache transversal SHA256 + DuckDB schema unificado + migrations.
- `src/hemiciclo/etl/__init__.py` marker do pacote ETL.
- `src/hemiciclo/etl/schema.py` definindo `SCHEMA_VERSAO = 1` e `criar_schema_v1` -- cinco tabelas de domínio (`proposicoes`, `votacoes`, `votos`, `discursos`, `parlamentares`) com `casa` discriminador (PK composta `(id, casa)` permite cross-casa em uma tabela), tabela meta `_migrations` e três indexes (`idx_proposicoes_ementa`, `idx_discursos_parlamentar`, `idx_votos_parlamentar`). Todos os DDLs usam `IF NOT EXISTS` -- idempotente.
- `src/hemiciclo/etl/migrations.py` com `Migration` dataclass + lista `MIGRATIONS = [M001]` + `aplicar_migrations(conn) -> int` (idempotente) e `versao_atual(conn) -> int`. Migrations futuras (M002+) ficam para sprints subsequentes.
- `src/hemiciclo/etl/cache.py` com cache transversal por hash SHA256: `caminho_cache_discurso(home, sha256)` -> `<home>/cache/discursos/<hash>.parquet`, `caminho_cache_proposicao(home, id_completo)` -> `<home>/cache/proposicoes/<id>.parquet`, `salvar_cache(df, path)` com escrita atômica via `tempfile + Path.replace`, `carregar_cache(path)` retornando `pl.DataFrame | None`, `existe_no_cache(path)`.
- `src/hemiciclo/etl/consolidador.py` com `consolidar_parquets_em_duckdb(dir_parquets, db_path) -> dict[tabela, linhas]` mapeando 10 nomes de parquet (S24+S25) para as 5 tabelas via `INSERT OR IGNORE INTO ... SELECT ... FROM read_parquet(?)` com SELECT explícito coluna a coluna. Robusto: arquivo corrompido é logado e ignorado, não interrompe os demais.
- Subcomando `hemiciclo db` no CLI Typer com 3 ações: `init` (cria/atualiza schema), `consolidar --parquets <dir>` (carrega parquets), `info` (mostra schema vN + contagens). Default `--db-path = ~/hemiciclo/cache/hemiciclo.duckdb`.
- 25 testes novos: 6 schema (5 tabelas, PKs compostas com discriminador casa, índices, idempotência, versão), 5 migrations (DB vazio aplica todas, atualizado não faz nada, parcial aplica pendentes, versão atual, lista ordenada/única), 6 cache (path por hash, path por id, escrita atômica sem .tmp órfão, carregar inexistente -> None, round-trip Polars, existe_no_cache), 5 consolidador (Câmara, Senado, idempotente, dir vazio, arquivo corrompido), 3 e2e (workflow CLI completo, cross-casa em proposicoes, query LIKE), 4 sentinela CLI (db init --help, db consolidar --help com COLUMNS=200 + TERM=dumb + NO_COLOR=1, db info em DB vazio, db consolidar com diretório inexistente exit 2). Suite total cresce para 169 testes.
- Dependência runtime nova: `duckdb>=1.0` (pinada em 1.5.2). `uv.lock` regenerado.
- `docs/arquitetura/cache_e_db.md` documentando schema, migrations, cache transversal, mapeamento parquet -> tabela do consolidador, queries comuns e smoke local end-to-end.

### Adicionado (S25 -- Coleta Senado)

- feat(coleta): coletor do Senado replicando padrão da Câmara, com helper XML/JSON dedicado.
- `src/hemiciclo/coleta/senado.py` com `URL_BASE = "https://legis.senado.leg.br/dadosabertos"` (apenas governo BR -- I1) e cinco coletores (`coletar_senadores`, `coletar_materias`, `coletar_votacoes`, `coletar_votos_de_votacao`, `coletar_discursos`) iterando via `Iterator[dict]` e respeitando `TokenBucket` + `@retry_resiliente` herdados de S24.
- Helper `_parse_xml_ou_json` negocia `Accept: application/json` mas faz fallback para parse XML via `lxml.etree` para endpoints que retornam apenas XML; `_xml_para_dict` converte recursivamente preservando múltiplos filhos como lista e removendo namespaces.
- Helper `_itens_de` navega payload aninhado e normaliza dict-solto vs lista-de-dicts em sempre-lista, simplificando o normalizador.
- Cinco normalizadores (`_normalizar_materia`, `_normalizar_votacao`, `_normalizar_voto`, `_normalizar_discurso`, `_normalizar_senador`) achatando estrutura aninhada para schemas alinhados com Câmara (12 colunas em matérias, 6 em votações, 5 em votos, 9 em discursos, 7 em senadores), com `casa = "senado"` permitindo `UNION ALL` direto em S26.
- `hash_conteudo` é SHA256 da ementa (lição S24, ACHADO 3): determinístico e útil para deduplicação cross-casa.
- `CheckpointSenado` em `coleta/checkpoint.py` paralelo a `CheckpointCamara`, com `materias_baixadas: set[int]`, `votacoes_baixadas: set[int]`, `votos_baixados: set[tuple[int, int]]`, `discursos_baixados: set[str]`, `senadores_baixados: set[int]`. Coexiste com checkpoint da Câmara em `~/hemiciclo/cache/checkpoints/` graças ao prefixo `senado_<hash>.json` vs `camara_<hash>.json`.
- `hash_params_senado` adiciona prefixo `senado:` na seed do SHA256, garantindo hashes distintos mesmo com parâmetros numéricos coincidentes entre as casas.
- `executar_coleta` (Senado) parametriza por ano (mais granular que legislatura), derivando faixa de `data_inicio`/`data_fim` quando presentes ou de `legislaturas` (4 anos cada) caso contrário.
- Subcomando `hemiciclo coletar senado` no CLI Typer com flags `--legislatura`, `--ano`, `--tipos`, `--max-itens`, `--output`.
- 21 testes novos: 13 unit (9 cobrindo coletores via respx incluindo retry 503, 404, max_itens e parse XML; 4 cobrindo helpers `_itens_de`, `_xml_para_dict` e normalizadores defensivos), 7 checkpoint unit (round-trip, tuples, hypothesis, coexistência com Câmara, determinismo de hash), 8 e2e mockados (coleta completa, retomada idempotente, parse XML, sobrevivência a kill, orquestrador multi-tipo, votações+votos, discursos, I1 URLs governo BR), e 2 sentinelas CLI (--help com `COLUMNS=200` + `TERM=dumb` + `NO_COLOR=1` resistente a CI multi-OS, e tipo inválido com exit 2).
- `TipoColeta` em `coleta/__init__.py` extendido com `"materias"` e `"senadores"` (Câmara mantém `proposicoes`, `votacoes`, `votos`, `discursos`, `deputados`).
- Suite total cresce para 144 testes (114 herdados + 21 da S25 + 8 extras de cobertura adicionados em ajuste fino).
- Dependência runtime nova: `lxml>=5.0` para parse XML do Senado. `uv.lock` regenerado.
- Override mypy adicionado em `pyproject.toml` para `lxml.*` (sem stubs públicos disponíveis).
- `docs/arquitetura/coleta.md` estendido com seção "API Senado (S25)" cobrindo endpoints, três diferenças vs Câmara, coexistência de checkpoints e smoke test local.

### Adicionado (S24 -- Coleta Câmara)

- feat(coleta): coletor da Câmara dos Deputados com checkpoint resumível.
- `src/hemiciclo/coleta/__init__.py` com `ParametrosColeta` Pydantic v2 (legislaturas, tipos, intervalo de data, max_itens, dir_saida) + `TipoColeta` Literal.
- `src/hemiciclo/coleta/http.py` com cliente httpx + decorator `@retry_resiliente` (tenacity, 5 tentativas, backoff exponencial 1s..16s, max 60s), User-Agent identificável `Hemiciclo/<v>` e `raise_para_status` que distingue 4xx (sem retry) de 5xx (retry).
- `src/hemiciclo/coleta/rate_limit.py` com `TokenBucket` thread-safe (default 10 req/s, capacidade 20, override via `HEMICICLO_RATE_LIMIT`).
- `src/hemiciclo/coleta/checkpoint.py` com `CheckpointCamara` Pydantic (sets de IDs por tipo, votos como `set[tuple[str, int]]`), `hash_params` determinístico (ordem irrelevante), `salvar_checkpoint` atômico (`tempfile + Path.replace`), `carregar_checkpoint` com reidratação de tuples.
- `src/hemiciclo/coleta/camara.py` com cinco coletores (`coletar_proposicoes`, `coletar_votacoes`, `coletar_votos_de_votacao`, `coletar_discursos`, `coletar_cadastro_deputados`) iterando via `Iterator[dict]` e respeitando paginação `Link: rel="next"` (RFC 5988); orquestrador `executar_coleta` salva checkpoint a cada 50 requisições e escreve Parquet via Polars com schema explícito (12 colunas em proposições, conforme spec).
- Subcomando `hemiciclo coletar camara` no CLI Typer com flags `--legislatura`, `--tipos`, `--data-inicio`, `--data-fim`, `--max-itens`, `--output`.
- 28 testes novos: 5 http (retry/4xx/timeout/backoff), 6 rate_limit (token bucket, env override, valores inválidos), 9 checkpoint (round-trip, atomic write, hypothesis property-based, hash determinístico), 8 camara (paginação, max_itens, 503 retry, 404 sem retry), e 6 e2e mockados (retomada idempotente, schema Parquet, I1 URLs governo BR para legs 55/56/57). Suite total cresce para 105 testes.
- Dependências runtime: `httpx>=0.27`, `tenacity>=8.2`, `polars>=1.0`. Dependências dev: `respx>=0.21`, `freezegun>=1.5`. `uv.lock` regenerado.
- `docs/arquitetura/coleta.md` documentando filosofia, endpoints alvo, padrão de retry, escrita atômica do checkpoint, schema dos Parquet, padrão para S25 e smoke test manual.

### Adicionado (S23 -- Shell visível)

- feat(dashboard): shell visível Streamlit + install.sh / run.sh (Linux/macOS).
- `src/hemiciclo/dashboard/` com `app.py`, `tema.py` (8 cores institucionais hex
  literais + storytelling por aba + 21 partidos canônicos), `style.css` (CSS
  injetado com Inter + JetBrains Mono via Google Fonts, paleta institucional
  sóbria, responsivo até 1024 px) e `componentes.py` (header, footer,
  navegação, card de sessão, CTA, storytelling).
- `src/hemiciclo/dashboard/paginas/` com 4 páginas (`intro`,
  `lista_sessoes`, `nova_pesquisa`, `sobre`) navegadas via
  `st.session_state["pagina_ativa"]` (sidebar collapsed, layout wide).
- `src/hemiciclo/sessao/modelo.py` com Pydantic v2 estrito: enums `Camada`,
  `Casa`, `EstadoSessao`, modelos `ParametrosBusca` e `StatusSessao` com
  validação completa (tópico não-vazio, casa/legislatura mínimas, UFs
  canônicas, período coerente, progresso `[0, 100]`).
- `install.sh` Linux/macOS detecta SO via `uname -s`, valida Python 3.11+,
  instala `uv` se ausente, roda `uv sync --all-extras`. Modo `--check` valida
  ambiente sem instalar (CI smoke).
- `run.sh` sobe Streamlit em `localhost:8501` com `--server.headless=false`.
- Subcomando `hemiciclo dashboard` no CLI Typer (paridade com `./run.sh`).
- Form de Nova Pesquisa valida via Pydantic e persiste rascunho em
  `~/hemiciclo/sessoes/<slug>_rascunho/params.json` enquanto o pipeline
  real (S30) não está disponível -- mensagem `Funcionalidade chega em S30`.
- 13 testes do modelo Pydantic + 8 testes de componentes via `pytest-mock`
  + 8 smoke tests via `streamlit.testing.v1.AppTest` = 29 novos testes.
- Dependências runtime: `streamlit>=1.40`, `plotly>=5.20`. Dependência dev:
  `pytest-mock>=3.14`. `uv.lock` regenerado.
- `docs/manifesto.md` versão curta (~580 palavras; final fica em S38).
- `docs/usuario/instalacao.md` cobrindo Ubuntu, Fedora, macOS, M1 vs Intel,
  troubleshooting (Python ausente, SSL, porta ocupada).
- `docs/usuario/primeira_pesquisa.md` documentando jornada esperada quando
  S30 estiver pronta + comportamento atual de rascunho na S23.
- `README.md` substitui seção "Migração em andamento" por "Instalação
  rápida" + "Primeira pesquisa".

### Adicionado (S37 -- CI multi-OS)

- ci: pipeline multi-OS configurado (3 OS x 2 Python).
- `.github/workflows/ci.yml` com matriz `{ubuntu-22.04, macos-14, windows-2022} x {3.11, 3.12}` (6 jobs, `fail-fast: false`), rodando `uv sync --frozen`, validar_adr, ruff check/format, mypy --strict e pytest com cobertura. Codecov apenas em `ubuntu-22.04 + python-3.11`.
- `.github/workflows/release.yml` esqueleto tag-triggered (`v*.*.*`) reaproveitando matriz CI; etapa `publish` placeholder para S38.
- `.github/workflows/adr-check.yml` valida formato MADR em PRs que tocam `docs/adr/**` ou o validador.
- `.github/workflows/stale.yml` marca issues/PRs sem atividade após 90 dias e fecha após 14 dias adicionais.
- `.github/dependabot.yml` com atualizações semanais de pip (grupos runtime/dev) e mensais de github-actions.
- `.github/CODEOWNERS` apontando @AndreBFarias como dono default.
- Templates de issue (`bug.md`, `feature.md`, `topico.md`, `config.yml`) e de PR (`PULL_REQUEST_TEMPLATE.md`) com checklist baseado em I4-I12.
- `scripts/validar_adr.py` -- validador MADR em Python puro (apenas stdlib): cabeçalho, metadados obrigatórios, seções estruturais, numeração sequencial, sincronia com `docs/adr/README.md`.
- `tests/unit/test_validar_adr.py` -- 12 casos cobrindo ADR válido, ausência de Status/Decisão, numeração com buraco (warning), README desatualizado, filename inválido, divergência número filename vs cabeçalho, diretório vazio, diretório real.
- Badges CI, Codecov, Python 3.11+ e GPLv3 no topo do `README.md`.
- `docs/dev/workflow.md` documentando clone → branch → commit → PR → CI → review → merge + regras de branch protection para configuração manual.

### Adicionado (S22 -- Bootstrap Python)

- `pyproject.toml` PEP 621 com metadata, deps base (Typer, Rich, Pydantic v2, Pydantic Settings, Loguru) e extras de dev (pytest, ruff, mypy, pre-commit, hypothesis).
- `uv.lock` determinístico gerado via `uv sync --all-extras`.
- `.python-version` fixando Python 3.11.
- Estrutura `src/hemiciclo/` com `__init__.py` (exporta `__version__ = "0.1.0"`), `__main__.py`, `cli.py` (Typer com `--version` e `info`) e `config.py` (Pydantic Settings com `HEMICICLO_HOME`, `LOG_LEVEL`, `RANDOM_STATE`).
- Suite `tests/unit/test_sentinela.py` cobrindo versão, help, criação de diretórios, override de env e propriedades de `Configuracao`.
- `Makefile` com targets `bootstrap`, `install`, `test`, `lint`, `format`, `check`, `run`, `cli`, `seed`, `clean`, `release`.
- `.pre-commit-config.yaml` com Ruff, Mypy strict e checks padrão (whitespace, EOL, YAML/TOML lint, large files, private keys).
- `.editorconfig`, `.gitattributes` (line endings consistentes), `.gitignore` expandido para Python preservando padrões R.
- `.devcontainer/` (Python 3.11 slim + uv + extensões VS Code) e `.vscode/` (settings, launch, extensions) prontos para dev.
- `scripts/bootstrap.sh` (Linux/macOS) e `scripts/bootstrap.bat` (Windows) com detecção de SO, validação de Python 3.11+, instalação automática de uv e setup de pre-commit.
- 11 ADRs canônicos (ADR-001 a ADR-011) cobrindo decisões fundadoras D1-D11, no formato MADR adaptado, com índice em `docs/adr/README.md`.
- Seção "Migração para Python 2.0 em andamento" no `README.md` com link para o plano R2 e `legacy-r`.

### Mudado

- `.gitignore` reorganizado preservando padrões R legados e adicionando padrões Python (uv, pytest, ruff, mypy, streamlit, hemiciclo runtime).

### Preservado

- Branch `legacy-r` mantém o código R original em estado funcional para auditoria histórica.

### Adicionado (S38 -- Higienização final + manifesto longo + release v2.0.0)

- chore(s38): bump `__version__` para `2.0.0` em `src/hemiciclo/__init__.py`,
  `version` em `pyproject.toml` e sentinela `test_versao_constante` em
  `tests/unit/test_sentinela.py`. Sentinela agora valida `2.0.0` em vez do
  histórico `0.1.0` da S22.
- docs(s38): `docs/manifesto.md` reescrito de stub curto (~400 palavras
  legados da S23) para versão expandida (~1519 palavras) seguindo a
  estrutura definida em `sprints/SPRINT_S38_RELEASE_V2.md` §5.1, com
  experiência prévia do autor no mercado de inteligência política privada,
  diagnóstico do mercado, justificativa GPL v3, três casos concretos de
  uso (jornalista / ativista / eleitor curioso), limitações honestas e
  roadmap político.
- docs(s38): `README.md` em polish completo: badges CI / codecov / Python
  3.11+3.12 / GPLv3 / coverage 90%+ / 477 testes / release v2.0.0 / 20
  ADRs, `docs/assets/demo.png` embedado no topo (full-page screenshot da
  página `sessao_detalhe` com `_seed_concluida`, capturada via Playwright,
  176 KB, dimensões 1440 × 1800), 6 seções concisas (O que é / Início
  rápido / O que faz / Limitações honestas / Estatísticas / Comandos
  dev), versão R legada movida integralmente para `legacy-r`.
- docs(s38): 9 ADRs novos no formato MADR adaptado (precedente ADR-001 a
  ADR-011 da S22), todos com status `accepted` e data 2026-04-28:
  - ADR-012 -- DuckDB + Parquet como storage analítico local.
  - ADR-013 -- Subprocess detached + status.json + pid.lock como modelo
    de execução.
  - ADR-014 -- install.sh / install.bat exigem Python 3.11+ pré-instalado.
  - ADR-015 -- CI multi-OS Linux + macOS + Windows × Python 3.11 + 3.12.
  - ADR-016 -- Dependências fixadas em pyproject.toml com uv lock.
  - ADR-017 -- Conventional Commits + branches feature/fix/docs/chore.
  - ADR-018 -- random_state fixo em todos os modelos estatísticos.
  - ADR-019 -- Ruff + Mypy strict + pytest --cov 90 como portões de
    qualidade.
  - ADR-020 -- Logs estruturados via Loguru, arquivo rotacionado por
    sessão.
  - `docs/adr/README.md` atualizado com índice 001-020. Validador
    `scripts/validar_adr.py` reporta `20 ADRs validados em docs/adr/.
    Zero erros.`
- docs(s38): normaliza acentuação PT-BR em `.github/PULL_REQUEST_TEMPLATE.md`
  e nos 3 templates de issue (`bug.md`, `feature.md`, `topico.md`),
  resolvendo a sprint READY S37b. Slugs e identificadores em código
  permanecem ASCII (precedente do projeto).
- docs(s38): `docs/usuario/instalacao.md` revisado com pré-requisitos
  finais (Python 3.11+ ou 3.12, RAM 4 GB / 8 GB com bge-m3, disco 5-8 GB)
  e nota sobre o pipeline real da S30 substituindo o stub da S23.
- docs(s38): `CHANGELOG.md` consolidado -- `[Unreleased]` esvaziada,
  conteúdo migrado para `## [2.0.0] - 2026-04-28` com seções `Highlights`
  e `Invariantes da release`. Entrada R legada renumerada de `[2.0.0] -
  2026-04-16` para `[1.5.0] - 2026-04-16` (último estado do código R
  preservado em branch `legacy-r`).
- docs(s38): `sprints/ORDEM.md` -- S25.2 / S37b / S37c / S38 marcadas como
  DONE (2026-04-28). 23 sprints READY remanescentes (listadas abaixo)
  ficam para o ciclo v2.1.x.

### Próximas releases (v2.1.x e além)

23 sprints READY remanescentes do anti-débito incremental,
sequenciadas em `sprints/ORDEM.md`:

- **S23.1** -- Bundla Inter + JetBrains Mono como TTF local.
- **S23.2** -- install.sh detecta Python via `uv python find 3.11+`.
- **S23.3** -- Tema do botão CTA primário (AMARELO_OURO / AZUL_HEMICICLO).
- **S24b** -- Enriquecer proposições via GET /proposicoes/{id}.
- **S24c** -- coletar_proposicoes itera 4 anos da legislatura.
- **S24d** -- Progress bar Rich em `hemiciclo coletar camara`.
- **S24e** -- Pular páginas inteiras em retomada via `ultima_url`.
- **S24f** -- Mocks e2e refletem schema real da API.
- **S25.1** -- Decidir hash_conteudo 16-char vs 64-char + ADR.
- **S25.3** -- ADR registrando schema dual da API Senado v7.
- **S27.1** -- `votacoes.proposicao_id` (Migration M002) destrava JOIN.
- **S29.1** -- `sessao listar` auto-detecta PID morto.
- **S29.2** -- Trocar `write_text` de pid.lock por escrita atômica.
- **S28-polish** -- Acentuação periférica em `src/hemiciclo/modelos/`.
- **S30.1** -- Propagar `--max-itens` em ParametrosColeta.
- **S30.2** -- Aplicar filtros `params.ufs` e `params.partidos`.
- **S30.3** -- Trocar `Path.cwd()` por `Configuracao().topicos_dir`.
- **S35a** -- Teste documentando artefato listado mas ausente do zip.
- **S35b** -- Subir cobertura de `paginas/importar.py` para ≥ 92%.
- **S35c** -- Padronização de mensagens CLI da família `sessao`.
- **S34b** -- Camada 4 LLM opcional (ollama + cache + flag de sessão).
- **S36** -- install.bat Windows + run.bat (paridade nativa).
- **(novo)** -- catálogo comunitário de tópicos curados em `topicos/`.

## [1.5.0] - 2026-04-16

> Renumerada de `2.0.0` para `1.5.0` na consolidação da release v2.0.0 (S38).
> A versão `2.0.0` agora pertence ao port-completo Python; esta entrada
> registra o último estado do código R legado (sprint S19-S21 do portfólio
> R), preservado em branch `legacy-r`.

### Mudado
- Projeto renomeado de `Ranking-Congressistas` para `Hemiciclo` (sprint S19 do portfólio)
- Estrutura reorganizada: scripts movidos para `src/coleta/` e `src/ranking/`
- Lógica reutilizável extraída para `src/lib/` (rtf.R, ranking.R, api.R)
- Removidos comentários dramáticos dos scripts; mantida clareza técnica

### Adicionado
- `DESCRIPTION` com metadados do projeto
- Suite de testes `testthat` com cobertura de funções de RTF, ranking e API
- CI via GitHub Actions (`r-lib/actions`, testthat, lintr)
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- `.mailmap` para unificação de identidade
- `install.sh` e `uninstall.sh`
- Configuração de paralelismo via variável `HEMICICLO_CORES`

### Corrigido
- Removido `setwd("~/Desktop/DiscursosCongresso")` hardcoded
- Paths relativos via `file.path()` e raiz autodetectada
- Tratamento explícito de `NULL`/vazio em `decode_rtf`
- Proteção contra `NA` em listas de parlamentares

## [1.0.0] - 2022-01-01

### Adicionado
- Coleta de discursos da Câmara via API Dados Abertos
- Coleta de discursos do Senado via API Dados Abertos
- Processamento com regex para identificação de posicionamento
- Ranking de deputados por tema
- Ranking de senadores por tema
