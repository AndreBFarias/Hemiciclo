# Hemiciclo 2.0 -- Plataforma cidadã de perfilamento parlamentar

> **Versão expandida (R2)** -- pensada para ser executável por qualquer agente Claude (Opus/Sonnet/Haiku), com proof-of-work runtime-real verificável em cada sprint. Cobre: arquitetura, ADRs, infraestrutura, CI/CD, documentação, workflow, quality-of-life do dev, UI/UX, decomposição em sprints, validação multi-agente.

---

## 0. Sumário executivo

Hemiciclo 2.0 é o port-completo do projeto Hemiciclo (R, coleta+ranking) para Python+Streamlit, virando-o em **plataforma cidadã de perfilamento psicossocial-político de parlamentares** organizada em torno do conceito de **Sessão de Pesquisa**: cada cidadão configura uma busca pelo navegador (tópico, casa, UF, período, partido), dispara coleta sob demanda em background, e recebe um relatório multidimensional persistido localmente.

A motivação política é virar do avesso o produto que empresas de inteligência política vendem a lobistas e marcas: a inteligência quantitativa parlamentar como bem comum auditável, soberano, instalável pelo usuário comum. Sem servidor central. Sem rastreio. Sem dependência de API paga.

**Estado atual:** repo R higienizado (saúde 10/10, S21 concluída) -- embrião funcional mas sem dashboard, sem cruzar votos, sem chegar ao usuário final.

**Estado-alvo (release v2.0.0):** 17 sprints de S22 a S38 entregando: Streamlit + install.sh/install.bat + ETL Câmara/Senado + cache transversal + classificador multicamada + modelo base + sessão runner + dashboard multidimensional + grafos + histórico + ML de convertibilidade + LLM opcional + exportação + CI/CD + docs.

---

## 1. Contexto e por quê

### 1.1 Estado atual do repo

```
Hemiciclo/
  DESCRIPTION         # metadados R
  install.sh          # instala R deps
  src/
    coleta/           # camara.R, senado.R (XML/RTF)
    lib/              # api.R, ranking.R, rtf.R
    ranking/          # deputados.R, senadores.R
  tests/testthat/     # 14 testes passando
  .github/workflows/ci.yml
```

R tem o que o Hemiciclo faz hoje: coleta XML, decodifica RTF Base64, normaliza min-max, gera ranking de produtividade discursiva. Não há dashboard, não há cruzamento com votos, não há perfil multidimensional.

### 1.2 Por que migrar

- **Streamlit** entrega o "João comum" via navegador local em minutos; o R atual exige R+pacotes+linha de comando.
- O ecossistema científico Python (sentence-transformers, BERTopic, scikit-learn, networkx, pyvis) tem pacotes e benchmarks atualizados que R não acompanha em NLP semântico.
- O autor já tem o projeto Streamlit `stilingue-energisa-etl` em produção como referência estilística.
- Voto nominal está disponível nas mesmas APIs já usadas (Câmara/Senado Dados Abertos) -- coletar é trivial, valor é altíssimo.

### 1.3 Manifesto político (declarado)

> "Open source completo com novas e melhores features porém que vai dar a chance pro seu João de saber de tudo."

A ferramenta serve a quem quer entender o Congresso sem pagar pesquisa de mercado. Inverte o vetor histórico -- do lobista de volta ao cidadão. Esse é o critério de design quando houver ambiguidade entre conveniência técnica e radicalidade do manifesto.

### 1.4 Lente do autor

O autor traz experiência prévia em perfilamento comportamental quantitativo aplicado a clientes corporativos (cientista de dados/netnógrafo). Decisões metodológicas devem assumir que ele:
- Não precisa explicação básica de NLP, embeddings, PCA, topic modeling, clustering, fatorial.
- Conhece trade-offs indutivo vs dedutivo, frameworks teóricos psicossociais, e o ofício de transformar dados em assinatura.
- Quer rigor metodológico equivalente ao corporativo, com radicalidade política do open-source.

---

## 2. Decisões fundadoras (D1-D11)

Decisões validadas no brainstorming. Cada uma vira ADR formal (seção 4). Mudar qualquer uma exige nova rodada de brainstorming.

| # | Decisão | Implicação direta |
|---|---|---|
| D1 | Stack: **Python 3.11+ / Streamlit / DuckDB / Polars** | Substitui R legado. R fica preservado em branch `legacy-r` |
| D2 | **Voto nominal como espinha dorsal** da posição parlamentar | Resolve "a favor / contra" sem NLP. Discursos viram camada qualitativa |
| D3 | **Mapeamento tópico -> proposições híbrido**: categoria oficial Câmara/Senado + curadoria comunitária via YAML versionado | Permite busca livre + categorização auditável + crescimento comunitário |
| D4 | **Assinatura multidimensional indutiva**: 7 eixos (posição, intensidade, hipocrisia, volatilidade, centralidade, convertibilidade, enquadramento) | PCA + topic modeling + grafo emergem dos dados |
| D5 | **Caminho indutivo data-driven**, não dedutivo-teórico | Sem Schwartz/Haidt forçados. Frameworks teóricos só como interpretação a posteriori |
| D6 | **Tudo local** na máquina do usuário | Zero infra central. Soberania total. CI publica só código |
| D7 | **Sessão de Pesquisa como cidadão de primeira classe** | Cada busca é unidade autocontida, persistida, exportável, retomável |
| D8 | **Modelo base global + ajuste fino local (híbrido)** | Eixos comparáveis entre sessões + insight do recorte específico |
| D9 | **Embeddings BAAI/bge-m3** (~2GB) | Estado-da-arte multilíngue 2024-25. Dense + sparse + colbert numa só call |
| D10 | **MVP: Shell visível primeiro** (Streamlit + install antes do ETL real) | UX/UI antes de profundidade técnica |
| D11 | **Classificação multicamada em cascata** -- keywords/regex + voto + embeddings + LLM opcional | Cada camada independente, transparente, auditável e desligável |

---

## 3. Classificação multicamada (D11 -- detalhamento)

A pergunta "esse parlamentar é a favor ou contra X?" é respondida em **cascata de quatro camadas**, das mais transparentes pras mais opacas. Cada camada é executável de forma independente; o usuário pode desligar camadas via flag de sessão.

### 3.1 Camada 1 -- Determinística (sempre ligada, baseline auditável)

- **Keywords + regex sobre ementas de proposições.** Cada tópico em `topicos/<topico>.yaml` declara `keywords: [...]` e `regex: [...]`.
- **Categoria oficial da Câmara/Senado.** YAML pode declarar `categorias_oficiais: [...]`.
- **Voto nominal.** SIM/NÃO/ABSTENÇÃO/OBSTRUÇÃO/ART.17 por parlamentar. Posição agregada = proporção de SIM no conjunto de proposições do tópico.
- **Autoria/coautoria/relatoria.** Sinal positivo de engajamento.

**Saída:** vetor de posição binária com confiança alta. **Resultado canônico** -- todas as outras camadas são complementos.

### 3.2 Camada 2 -- Estatística leve (default ligada, sem GPU)

- **TF-IDF** sobre ementas + discursos filtrados pela camada 1.
- **Booleanas com proximidade** (`aborto NEAR/5 contra`).
- **Contagens normalizadas** (intensidade discursiva por baseline do parlamentar).

**Saída:** intensidade e ranking de relevância dentro do conjunto.

### 3.3 Camada 3 -- Semântica via embeddings (default ligada, ~2GB modelo)

- **bge-m3** sobre ementas que **não** casaram regex/keywords mas podem ser semanticamente relevantes (similaridade > limiar configurável).
- **bge-m3 sobre discursos** dos parlamentares já identificados, pra clustering retórico via BERTopic.
- **PCA / FactorAnalysis** sobre matriz parlamentar x votos pra eixos induzidos.

**Saída:** complemento ao mapeamento tópico->PL + dimensões da assinatura + clusters retóricos.

### 3.4 Camada 4 -- LLM opcional (desligada por default)

- Análise individual de discursos pra detectar **ironia**, **contradição fala x voto**, **intensidade emocional**, **enquadramento moral fino**.
- Local (`ollama` + modelo PT-BR pequeno) ou via API com chave do usuário.
- Cache agressivo por hash de discurso.

**Saída:** anotações qualitativas. Nunca muda posição da camada 1.

### 3.5 Por que essa arquitetura importa

- **Auditabilidade radical.** Camada 1 verificável abrindo YAML + CSV de votos.
- **Funciona offline e sem GPU.** Camadas 1+2 já entregam relatório útil.
- **Falha graciosamente.** Modelo bge-m3 corrompido? Sessão segue com 1+2.
- **Cada camada tem proof-of-work próprio nos testes.**
- **Configurável por sessão.** `params.camadas: ["regex", "votos", "embeddings"]`.

### 3.6 Schema canônico do YAML de tópico

```yaml
# topicos/aborto.yaml
nome: aborto
versao: 1
mantenedor: comunidade
descricao_curta: "Pauta sobre interrupção da gravidez no ordenamento jurídico brasileiro"
keywords:
  - aborto
  - interrupção da gravidez
  - aborto legal
  - aborto terapêutico
regex:
  - "(?i)aborto\\s+(?:legal|terap[êe]utico|provocado)"
  - "(?i)interrup[çc][ãa]o\\s+(?:vol[ui]nt[áa]ria|legal)\\s+da\\s+gravidez"
categorias_oficiais_camara:
  - "Direitos Humanos, Minorias e Cidadania"
  - "Saúde"
categorias_oficiais_senado:
  - "Direitos Humanos"
  - "Saúde"
proposicoes_seed:
  - { sigla: "PL", numero: 1904, ano: 2024, casa: "camara", posicao_implicita: contra }
  - { sigla: "ADPF", numero: 442, ano: 2017, casa: "stf", posicao_implicita: a_favor }
exclusoes:
  - regex: "(?i)aborto\\s+espont[âa]neo"   # uso médico, não pauta
embeddings_seed:
  - "regulamentação do aborto legal no Brasil"
  - "criminalização ou descriminalização da interrupção da gravidez"
limiar_similaridade: 0.62
```

---

## 4. Architecture Decision Records (ADRs)

ADRs vivem em `docs/adr/` no formato MADR. Cada decisão fundadora vira ADR formal numerado. ADRs são **imutáveis**: para reverter D-N, criar `ADR-XXX-substitui-ADR-YYY.md` com status `accepted` apontando a substituição, e marcar o anterior `superseded`.

### 4.1 Template ADR (MADR adaptado)

```markdown
# ADR-NNN -- Título da decisão

- **Status:** proposed | accepted | deprecated | superseded by ADR-XXX
- **Data:** YYYY-MM-DD
- **Decisores:** @AndreBFarias
- **Tags:** stack, etl, ml, ux, infra, etc.

## Contexto e problema

[1-2 parágrafos: que problema motiva a decisão, quais constraints existem]

## Drivers de decisão

- [critério 1]
- [critério 2]

## Opções consideradas

### Opção A -- Nome curto
- Prós: ...
- Contras: ...

### Opção B -- Nome curto
- Prós: ...
- Contras: ...

## Decisão

Escolhida: **Opção X**.

Justificativa: ...

## Consequências

**Positivas:**
- ...

**Negativas / custos assumidos:**
- ...

## Pendências / follow-ups

- [ ] ADR-NNN+1 cobrir Y (se decisão depende)

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- Sprint relacionada: SXX
```

### 4.2 Lista canônica de ADRs do Hemiciclo 2.0

| ADR | Título | Vincula |
|---|---|---|
| ADR-001 | Migração de R para Python 3.11+ com Streamlit | D1 |
| ADR-002 | Voto nominal como fonte primária de posição parlamentar | D2 |
| ADR-003 | Mapeamento tópico -> proposições via YAML curado + categoria oficial | D3 |
| ADR-004 | Assinatura multidimensional com 7 eixos definidos | D4 |
| ADR-005 | Caminho indutivo data-driven (não dedutivo-teórico) | D5 |
| ADR-006 | Arquitetura 100% local, sem servidor central | D6 |
| ADR-007 | Sessão de Pesquisa como cidadão de primeira classe | D7 |
| ADR-008 | Modelo base global + ajuste fino local (híbrido) | D8 |
| ADR-009 | Embeddings BAAI/bge-m3 como default | D9 |
| ADR-010 | Shell visível antes de ETL real (UX-first) | D10 |
| ADR-011 | Classificação multicamada em cascata, cada camada desligável | D11 |
| ADR-012 | DuckDB + Parquet como storage analítico, Polars como engine | implicado por D6 |
| ADR-013 | Subprocess + status.json + pid.lock como modelo de execução de sessão | implicado por D7 |
| ADR-014 | install.sh/.bat exigem Python 3.11+ pré-instalado (sem PyInstaller no v1) | implicado por D1, D6 |
| ADR-015 | CI multi-OS (Linux + macOS + Windows) com matriz Python 3.11 e 3.12 | infra |
| ADR-016 | Dependências fixadas por versão exata em pyproject.toml | reprodutibilidade |
| ADR-017 | Padrão de commit Conventional Commits + branch `feature/*`, `fix/*`, `docs/*` | workflow |
| ADR-018 | random_state fixo em todos os modelos pra determinismo entre máquinas | implicado por D8 |
| ADR-019 | Ruff + Mypy strict + pytest --cov=90 como portões de qualidade | QoL |
| ADR-020 | Logs estruturados via Loguru + arquivo rotacionado por sessão | observabilidade |

ADRs S22+ podem nascer durante execução conforme decisões emergirem.

---

## 5. Arquitetura

### 5.1 Layout do filesystem do usuário final

```
~/hemiciclo/
  modelos/
    base_v1.pkl                      # Modelo base global treinado uma vez
    base_v1.meta.json                # Versão, data treino, amostra, hiperparâmetros, hash
    embeddings_cache_index.parquet   # Índice de hashes já embeddados
  cache/
    discursos/<hash>.parquet         # Por hash SHA256 do conteúdo
    votos/<parlamentar_id>_<votacao_id>.json
    proposicoes/<sigla>_<num>_<ano>.json
    embeddings/bge-m3/<hash>.npy
  sessoes/
    2026-04-27_aborto_DF/
      params.json                    # ParametrosBusca serializado
      status.json                    # StatusSessao, atualizado pelo subprocess
      pid.lock                       # PID + timestamp + checksum
      dados.duckdb                   # Banco local da sessão
      discursos.parquet
      votos.parquet
      proposicoes.parquet
      modelos_locais/                # Ajuste fino sobre o recorte
      relatorio_state.json           # Estado do dashboard
      log.txt                        # Loguru rotacionado
      manifesto.json                 # Hashes de tudo, pra integridade
  topicos/                           # YAML curado, sincronizado do repo
    aborto.yaml
    porte_armas.yaml
  config.toml                        # Preferências do usuário
  logs/
    hemiciclo.log                    # Log global rotacionado
```

### 5.2 Layout do repositório

```
Hemiciclo/
  .github/
    workflows/
      ci.yml                         # pytest + ruff + mypy + matriz OS x Python
      release.yml                    # tag v*.* dispara build + GitHub Release
      adr-check.yml                  # valida formato MADR de ADRs novas
      stale.yml                      # fecha issues sem atividade
    ISSUE_TEMPLATE/
      bug.md
      feature.md
      topico.md                      # template pra contribuir YAML de tópico
    PULL_REQUEST_TEMPLATE.md
    dependabot.yml
    CODEOWNERS
  .vscode/
    settings.json                    # ruff, pytest, mypy integrados
    launch.json                      # debug Streamlit + CLI
    extensions.json
  .devcontainer/
    devcontainer.json                # ambiente reproduzível
    Dockerfile
  docs/
    README.md                        # mapa da documentação
    adr/
      README.md                      # índice de ADRs
      ADR-NNN-titulo.md
    superpowers/
      specs/
        2026-04-27-hemiciclo-2-design.md   # cópia versionada deste plano
    arquitetura/
      visao_geral.md
      classificacao_multicamada.md
      sessao_de_pesquisa.md
      modelo_base.md
      grafos_redes.md
    usuario/
      instalacao.md
      primeira_pesquisa.md
      interpretando_relatorio.md
      exportar_compartilhar.md
      faq.md
    dev/
      setup.md
      workflow.md
      padrao_codigo.md
      testes.md
      sprints.md
      adr.md
      soltar_release.md
    topicos/
      README.md                      # como contribuir YAML de tópico
      schema.md                      # schema validado em CI
    manifesto.md                     # texto político longo
  src/
    hemiciclo/
      __init__.py
      __main__.py                    # python -m hemiciclo == cli
      cli.py                         # Typer entry-point
      config.py                      # Pydantic Settings
      coleta/
        __init__.py
        camara.py
        senado.py
        checkpoint.py
        http.py                      # httpx + tenacity
        rate_limit.py
      etl/
        __init__.py
        transformacoes.py
        topicos.py                   # camada 1+2 do classificador
        cache.py                     # SHA256 + lookup + escrita atômica
        schema.py                    # DuckDB schema + migrations
      modelos/
        __init__.py
        embeddings.py                # bge-m3 wrapper
        base.py                      # treino/load do modelo base v1
        projecao.py                  # aplicar base + ajuste local
        topicos_induzidos.py         # BERTopic
        grafo.py                     # networkx
        convertibilidade.py          # ML
        llm.py                       # ollama / API opcional (camada 4)
      sessao/
        __init__.py
        modelo.py                    # Pydantic schemas
        runner.py                    # subprocess + status + pid.lock
        persistencia.py
        exportador.py                # zip + verificação de integridade
        retomada.py                  # detecção e retomada de sessões interrompidas
      dashboard/
        __init__.py
        app.py                       # Streamlit entry-point
        tema.py                      # design tokens
        style.css
        componentes.py
        widgets/
          word_cloud.py
          grafo_pyvis.py
          radar_assinatura.py
          heatmap_hipocrisia.py
          timeline_conversao.py
          progresso_sessao.py
        paginas/
          intro.py
          lista_sessoes.py
          nova_pesquisa.py
          sessao_detalhe.py
          grafo.py
          conversao.py
          exportar.py
          sobre.py
  topicos/
    README.md                        # como contribuir
    _schema.yaml                     # JSON Schema validado em CI
    aborto.yaml
    porte_armas.yaml
    marco_temporal.yaml
  tests/
    __init__.py
    conftest.py                      # fixtures globais
    unit/
      test_coleta_camara.py
      test_classificador_camadas.py
      test_modelo_base.py
    integracao/
      test_pipeline_sessao.py
      test_exportar_importar.py
    e2e/
      test_jornada_completa.py       # @pytest.mark.slow
    fixtures/
      ementas_aborto.json
      votos_seed.parquet
      discursos_seed.parquet
      modelo_base_fixture.pkl
    snapshots/                       # snapshot tests para regressão
  sprints/
    README.md                        # padrão e como usar
    ORDEM.md                         # grafo de dependências, status atual
    SPRINT_S22_BOOTSTRAP.md
    SPRINT_S23_SHELL_VISIVEL.md
  scripts/
    bootstrap.sh                     # criar venv + deps + hooks
    lint.sh
    format.sh
    test.sh
    release.sh
    seed_dados.py                    # popular ~/hemiciclo com seed pra dev
    benchmark_embeddings.py
  .editorconfig
  .gitattributes
  .gitignore
  .mailmap
  .pre-commit-config.yaml
  .python-version                    # 3.11
  pyproject.toml
  uv.lock                            # lock file determinístico
  Makefile                           # atalhos universais
  install.sh
  install.bat
  run.sh
  run.bat
  uninstall.sh
  uninstall.bat
  VALIDATOR_BRIEF.md                 # invariantes do projeto pra agentes
  README.md
  CHANGELOG.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  LICENSE                            # GPL v3
  DESCRIPTION                        # legacy R, manter pelo tempo de transição
```

### 5.3 Stack técnico definitivo

| Camada | Lib | Versão | Justificativa |
|---|---|---|---|
| Linguagem | Python | 3.11+ | f-strings + match + walrus + type hints generics |
| HTTP coleta | httpx + tenacity | 0.27 + 8.x | Async opcional, retry com backoff exponencial |
| Storage analítico | DuckDB + Parquet | 1.0+ | Colunar, sem servidor, integra com Polars |
| DataFrames | Polars | 1.0+ | Mais rápido que pandas pra esse perfil |
| Embeddings | FlagEmbedding (bge-m3) | 1.3+ | Estado-da-arte multilíngue 2024-25 |
| Topic modeling | BERTopic | 0.16+ | UMAP + HDBSCAN + c-TF-IDF |
| Redução dimensional | scikit-learn | 1.4+ | PCA, FactorAnalysis com `random_state` |
| Grafos | networkx + pyvis | 3.x + 0.3+ | Calc + HTML interativo |
| Dashboard | Streamlit + Plotly | 1.40+ + 5.x | Referência stilingue-energisa-etl |
| CLI | Typer + Rich | 0.12+ + 13.x | Progress bars, prompts, ergonomia |
| Validação | Pydantic v2 | 2.7+ | Models para Sessão, Params, Status, configs |
| Logs | Loguru | 0.7+ | Estrutura simples + rotação |
| Testes | pytest + pytest-cov + pytest-asyncio + hypothesis | 8+ | Padrão moderno, property-based |
| Lint/format | Ruff | 0.6+ | Velocidade, substitui black+isort+flake8 |
| Type check | Mypy strict | 1.10+ | Tipagem estrita |
| Pre-commit | pre-commit | 3.7+ | Portão local |
| Gerenciador deps | uv | 0.4+ | Lock determinístico, instalação rápida |
| Packaging | pyproject.toml (PEP 621) | -- | Sem PyInstaller no v1 |

### 5.4 Modelos de dados (Pydantic v2)

```python
# src/hemiciclo/sessao/modelo.py

from datetime import date, datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

class Camada(str, Enum):
    REGEX = "regex"
    VOTOS = "votos"
    EMBEDDINGS = "embeddings"
    LLM = "llm"

class Casa(str, Enum):
    CAMARA = "camara"
    SENADO = "senado"

class ParametrosBusca(BaseModel):
    topico: str = Field(..., description="Texto livre OU id de YAML curado")
    casas: list[Casa]
    legislaturas: list[int] = Field(..., description="ex: [55, 56, 57]")
    ufs: list[str] | None = None
    partidos: list[str] | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    camadas: list[Camada] = Field(
        default_factory=lambda: [Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS]
    )
    incluir_grafo: bool = True
    incluir_convertibilidade: bool = False

class EstadoSessao(str, Enum):
    CRIADA = "criada"
    COLETANDO = "coletando"
    ETL = "etl"
    EMBEDDINGS = "embeddings"
    MODELANDO = "modelando"
    CONCLUIDA = "concluida"
    ERRO = "erro"
    INTERROMPIDA = "interrompida"
    PAUSADA = "pausada"

class StatusSessao(BaseModel):
    id: str
    estado: EstadoSessao
    progresso_pct: float = Field(ge=0, le=100)
    etapa_atual: str
    mensagem: str
    iniciada_em: datetime
    atualizada_em: datetime
    pid: int | None = None
    erro: str | None = None
```

---

## 6. Infraestrutura & DevOps

### 6.1 CI/CD -- `.github/workflows/ci.yml`

Matriz: `{ubuntu-22.04, macos-14, windows-2022} x {python-3.11, python-3.12}` = 6 jobs.

Etapas por job:

1. **Checkout** com `fetch-depth: 0` (necessário pra hooks que olham histórico).
2. **Setup uv** via `astral-sh/setup-uv@v3` com cache.
3. **uv sync --frozen** (não permite drift do lock).
4. **Validação de YAMLs** de tópico contra `topicos/_schema.yaml`.
5. **Validação de ADRs** (formato MADR, `docs/adr/ADR-NNN-titulo.md`).
6. **Ruff check + format check** (zero tolerância).
7. **Mypy --strict** (zero tolerância).
8. **Pytest unit** (cobertura mínima 90%).
9. **Pytest integração** com fixtures locais (sem chamar API real -- mocks).
10. **Pytest e2e** marcado `@pytest.mark.slow`, executa só em `main` ou via label `e2e`.
11. **Smoke install** (`./install.sh --check` ou `install.bat /verify`) que valida script sem instalar tudo.
12. **Upload coverage** pro Codecov.

### 6.2 Workflow de release -- `.github/workflows/release.yml`

Triggered por tag `v*.*.*`:

1. Roda CI completo, falha = release abortado.
2. Gera CHANGELOG.md a partir de Conventional Commits desde a tag anterior.
3. Cria GitHub Release com:
   - Nota gerada
   - Assets: `topicos/*.yaml` zipados, `docs/superpowers/specs/*.md`, hash do `uv.lock`
4. (Opcional v2.x+) publica wheel no PyPI via OIDC.

### 6.3 Outros workflows

- **adr-check.yml**: valida que toda ADR tem campos obrigatórios e numeração sequencial.
- **stale.yml**: fecha issues sem atividade 90 dias com label `stale`.
- **dependabot.yml**: PRs semanais pra deps Python, mensais pra GitHub Actions.
- **codeql.yml**: análise de segurança Python semanal.

### 6.4 Pre-commit (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-PyYAML]
        args: [--strict]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: detect-private-key
  - repo: local
    hooks:
      - id: validar-topicos
        name: Validar YAMLs de topico
        entry: python scripts/validar_topicos.py
        language: system
        files: ^topicos/.*\.yaml$
      - id: validar-adr
        name: Validar formato MADR de ADRs
        entry: python scripts/validar_adr.py
        language: system
        files: ^docs/adr/ADR-.*\.md$
```

### 6.5 Devcontainer (`.devcontainer/devcontainer.json`)

Ambiente reproduzível pra qualquer dev -- VS Code abre o repo dentro de um container já configurado:

- Imagem Python 3.11 slim
- uv pré-instalado
- Ruff, Mypy, pytest extensões
- Streamlit port-forward 8501
- Pré-comando: `uv sync && pre-commit install`

### 6.6 Padrão de commit (Conventional Commits)

`<tipo>(<escopo>): <descrição>`

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`, `build`, `revert`.

Exemplos:
- `feat(coleta): adiciona coletor de votos da Camara com checkpoint`
- `fix(sessao): retomada nao recriava pid.lock apos kill -9`
- `docs(adr): registra ADR-009 sobre embeddings bge-m3`
- `chore(deps): atualiza httpx para 0.27.2`

Hook local valida formato via `commitlint` (configurado em `.commitlintrc.yml`).

### 6.7 Branches

- `main` -- release-only, protegido. PR obrigatório, CI verde, 1 review.
- `feature/<sprint-id>-<slug>` -- exemplo: `feature/s24-coleta-camara`.
- `fix/<id>-<slug>`, `docs/<slug>`, `chore/<slug>`.
- `legacy-r` -- preserva código R em estado funcional.

---

## 7. Documentação

### 7.1 Mapa de `docs/`

```
docs/
  README.md                          # voce esta aqui
  adr/                               # decisoes imutaveis
  arquitetura/                       # como o sistema funciona internamente
  usuario/                           # como usar
  dev/                               # como contribuir
  topicos/                           # como criar/contribuir topicos
  superpowers/specs/                 # specs versionadas das features
  manifesto.md                       # texto politico
```

### 7.2 README.md raiz

Estrutura obrigatória:

1. Logo + tagline
2. Badges (CI, license, python version, coverage)
3. **Manifesto curto** (3 frases)
4. **Demo gif** (gerar no fim, S38)
5. Instalação rápida (3 linhas)
6. Primeira pesquisa (3 linhas)
7. Roadmap visual (sprints concluídas/pendentes)
8. Documentação completa (link `docs/`)
9. Como contribuir (link `CONTRIBUTING.md`)
10. Licença

### 7.3 docs/usuario/instalacao.md

Cobertura: Linux, macOS, Windows, WSL. Inclui:
- Pré-requisitos (Python 3.11+, RAM, disco)
- Comandos por SO
- Troubleshooting comum (Python não está no PATH, certificado SSL no Windows, M1 vs Intel)
- Como verificar a instalação

### 7.4 docs/dev/sprints.md

Documenta o padrão de sprint completo (seção 9 deste plano), o ciclo `/sprint-ciclo`, o protocolo de validação, e como contribuir uma nova sprint.

### 7.5 docs/manifesto.md

Texto longo declarando intenção política. Não é README -- é peça de pensamento. Audiência: jornalista lendo pra escrever sobre o projeto.

### 7.6 CHANGELOG.md

Padrão Keep-a-Changelog + SemVer. Cada release tem seções `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

---

## 8. Quality of Life do dev (QoL)

### 8.1 Makefile (atalhos universais)

```makefile
.PHONY: help bootstrap install test lint format check run clean release

help:
	@echo "Hemiciclo -- comandos disponiveis:"
	@echo "  bootstrap      - Setup completo (venv + deps + hooks)"
	@echo "  install        - Sincroniza dependencias"
	@echo "  test           - Roda testes (unit + integracao)"
	@echo "  test-e2e       - Roda testes end-to-end (lento)"
	@echo "  lint           - Ruff check + Mypy strict"
	@echo "  format         - Ruff format"
	@echo "  check          - lint + test (CI local)"
	@echo "  run            - Sobe Streamlit em localhost:8501"
	@echo "  cli            - Atalho pra hemiciclo CLI (use ARGS=...)"
	@echo "  seed           - Popula ~/hemiciclo com dados seed pra dev"
	@echo "  clean          - Remove __pycache__, .pytest_cache, .ruff_cache"
	@echo "  release VERSION=x.y.z - Cria tag e dispara release"

bootstrap:
	uv venv
	uv sync --all-extras
	uv run pre-commit install
	@echo "Bootstrap concluido. Ative com: source .venv/bin/activate"

install:
	uv sync --all-extras

test:
	uv run pytest tests/unit tests/integracao -v --cov=src/hemiciclo --cov-report=term-missing

test-e2e:
	uv run pytest tests/e2e -v -m slow

lint:
	uv run ruff check src tests
	uv run mypy --strict src

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint test

run:
	uv run streamlit run src/hemiciclo/dashboard/app.py

cli:
	uv run hemiciclo $(ARGS)

seed:
	uv run python scripts/seed_dados.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

release:
	@test -n "$(VERSION)" || (echo "Use: make release VERSION=x.y.z" && exit 1)
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin v$(VERSION)
```

Equivalente Windows: `make.bat` com mesmos targets.

### 8.2 Scripts em `scripts/`

- **bootstrap.sh / bootstrap.bat** -- primeiro setup. Detecta SO, valida Python 3.11+, cria venv, instala uv se faltar, sincroniza deps, instala pre-commit.
- **seed_dados.py** -- popula `~/hemiciclo/sessoes/` com 2 sessões fake pra dev ver tela cheia sem rodar coleta real.
- **lint.sh, format.sh, test.sh** -- wrappers chamados pelo Makefile, mas usáveis isolados.
- **release.sh** -- bumpversion + tag + push.
- **validar_topicos.py** -- usado pelo pre-commit + CI.
- **validar_adr.py** -- idem.
- **benchmark_embeddings.py** -- utilitário pra medir tempo de embed em CPU vs GPU.

### 8.3 .editorconfig

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 4
insert_final_newline = true
trim_trailing_whitespace = true

[*.{md,yaml,yml,toml,json}]
indent_size = 2

[*.bat]
end_of_line = crlf
```

### 8.4 .vscode/

- **settings.json** -- Ruff como formatter, Mypy ativo, pytest discovery.
- **launch.json** -- duas configs: "Streamlit dashboard" e "CLI: nova pesquisa fake".
- **extensions.json** -- recomenda Ruff, Mypy, Python, Streamlit.

### 8.5 Logs estruturados

Loguru com sinks configurados em `src/hemiciclo/config.py`:

- **Console**: nível INFO+ com cor.
- **Arquivo global** (`~/hemiciclo/logs/hemiciclo.log`): rotação 10MB, retenção 7 dias.
- **Arquivo por sessão** (`~/hemiciclo/sessoes/<id>/log.txt`): tudo daquela sessão.

Convenção: campos estruturados via `logger.bind(sessao_id=..., etapa=...)`.

---

## 9. Padrão ULTRA-DETALHADO de spec de sprint

### 9.1 Princípios

Uma sprint bem escrita tem que ser executável por qualquer agente Claude (Opus, Sonnet, Haiku) sem ambiguidade. Três regras:

1. **Proof-of-work runtime-real obrigatório.** Cada sprint declara um comando shell verificável que prova que ela está pronta.
2. **Aritmética literal quando aplicável.** Se a sprint envolve contagem/cálculo, declarar valor exato esperado.
3. **Out-of-scope explícito.** Listar o que NÃO faz pra evitar scope creep.

### 9.2 Template (SPRINT_SXX_TITULO.md)

```markdown
# Sprint SXX -- Titulo curto

**Projeto:** Hemiciclo
**Versao alvo:** v2.0.0
**Data criacao:** YYYY-MM-DD
**Autor:** @AndreBFarias
**Status:** READY | DEPENDS | IN_PROGRESS | BLOCKED | DONE | PAUSED
**Depende de:** [lista de sprint IDs]
**Bloqueia:** [lista de sprint IDs]
**Esforco:** P (1-2d) | M (3-5d) | G (1-2sem)
**ADRs vinculados:** [ADR-NNN, ...]
**Branch:** feature/sXX-slug

---

## 1. Objetivo (uma frase)

[Frase unica descrevendo o resultado entregue]

## 2. Contexto

[1-2 paragrafos: por que essa sprint existe agora, o que destrava]

## 3. Escopo

### 3.1 In-scope

- [x] Item entregavel 1
- [x] Item entregavel 2

### 3.2 Out-of-scope (explicito)

- Item NAO feito 1 -- fica pra sprint SYY
- Item NAO feito 2 -- fica pra ZZ

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Proposito |
|---|---|
| `src/hemiciclo/...` | ... |
| `tests/...` | ... |

### 4.2 Arquivos modificados

| Caminho | Mudanca |
|---|---|
| `pyproject.toml` | Adiciona dep X |

### 4.3 Arquivos removidos

| Caminho | Motivo |
|---|---|
| `src/...` | Substituido por Y |

## 5. Implementacao detalhada

### 5.1 Passo a passo

1. **[Passo 1]** -- descricao concreta. Comando ou pseudo-codigo.
2. **[Passo 2]** -- ...

### 5.2 Decisoes tecnicas

- **Decisao A:** [escolha + razao curta]
- **Decisao B:** ...

### 5.3 Trechos de codigo de referencia

[Quando ha padrao a seguir, mostrar trecho exato]

## 6. Testes

### 6.1 Unit

- `test_X` -- verifica Y. Fixture: Z.

### 6.2 Integracao

- ...

### 6.3 Snapshot/Regressao (se aplicavel)

- ...

## 7. Proof-of-work runtime-real

**Comando que valida a sprint:**

bash
$ make check && uv run hemiciclo <comando-especifico>

**Saida esperada (literal/aritmetica):**

[saida exata ou padrao verificavel]

**Criterio de aceite:**
- [ ] Saida casa com o esperado
- [ ] Cobertura >= 90% nos arquivos novos
- [ ] CI verde em todas as plataformas
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violacoes
- [ ] CHANGELOG.md atualizado
- [ ] Documentacao atualizada (`docs/...`)

## 8. Riscos e mitigacoes

| Risco | Probabilidade | Impacto | Mitigacao |
|---|---|---|---|
| ... | M | A | ... |

## 9. Validacao multi-agente

**Executor (executor-sprint):** le este spec, implementa, roda proof-of-work, reporta.

**Validador (validador-sprint):** roda proof-of-work independentemente, verifica:
- Aritmetica/saida literal
- Cobertura
- Invariantes do `VALIDATOR_BRIEF.md`
- Acentuacao periferica em arquivos modificados (PT-BR sem perda)
- Ausencia de debito tecnico ("# TODO" sem ID, prints sobrando, etc.)

Se REPROVADO: validador escreve patch-brief, executor refaz. Ate 3 iteracoes.

## 10. Proximo passo apos DONE

S(XX+1): [titulo da proxima sprint] OU [nada -- terminal]
```

### 9.3 Regras de execução pra agentes

Quando um agente (Opus/Sonnet/Haiku) recebe uma sprint:

1. **Sempre ler `VALIDATOR_BRIEF.md` primeiro** -- invariantes do projeto têm precedência sobre o spec da sprint.
2. **Verificar dependências** -- se sprint declara `Depende de: SXX, SYY`, validar que ambas estão DONE antes de começar.
3. **Trabalhar no branch declarado** -- `feature/sXX-slug`.
4. **Seguir Conventional Commits**.
5. **Rodar `make check` antes de qualquer commit**.
6. **Rodar o proof-of-work declarado** ao terminar; se falhar, não declarar DONE.
7. **Atualizar `sprints/ORDEM.md`** mudando status para DONE com data.
8. **Atualizar `CHANGELOG.md`** com entrada Unreleased.
9. **Abrir PR** com template padrão (link pro spec, screenshots se UI, output do proof-of-work).
10. **Acionar validador-sprint** via `/validar-sprint` antes de fundir.

---

## 10. UI/UX

### 10.1 Princípios

1. **João comum primeiro.** Se não dá pra explicar uma tela em 1 frase pra leigo, redesenha.
2. **Narrativa antes de dado.** Cada tela começa com pergunta-de-negócio (storytelling estilo `stilingue-energisa-etl`).
3. **Estado visível.** Pipeline rodando = barra de progresso + etapa atual + tempo estimado. Sempre.
4. **Reversibilidade.** Toda ação destrutiva (deletar sessão, sobrescrever modelo base) confirma 2x.
5. **Compartilhar é botão de primeiro nível.** Exportar relatório como zip não pode estar enterrado em menu.
6. **Acessibilidade.** Cores não são único canal de informação (texto + ícone). Contraste WCAG AA mínimo.

### 10.2 Design tokens (`dashboard/tema.py`)

```python
# Paleta inspirada em institucional sobrio (nao-partidaria)
AZUL_HEMICICLO = "#1E3A5F"        # primary
AZUL_CLARO = "#4A7BAB"            # primary-light
AMARELO_OURO = "#D4A537"          # accent (Brasil sem ser kitsch)
VERDE_FOLHA = "#3D7A3D"           # success
VERMELHO_ARGILA = "#A8403A"       # danger / contra
CINZA_PEDRA = "#4A4A4A"           # neutral-strong
CINZA_AREIA = "#E8E4D8"           # neutral-light bg
BRANCO_OSSO = "#FAF8F3"           # bg principal

TIPOGRAFIA = {
    "titulo": "'Inter', system-ui, sans-serif",
    "corpo": "'Inter', system-ui, sans-serif",
    "mono": "'JetBrains Mono', monospace",
}

ESPACAMENTO = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32, "xxl": 48}
```

### 10.3 Jornadas do usuário (mockups ASCII)

#### J1 -- Primeira execução (instalação)

```
[terminal]
$ git clone ... && cd Hemiciclo && ./install.sh
[Hemiciclo] Verificando Python 3.11+... OK (3.11.7)
[Hemiciclo] Criando venv em .venv... OK
[Hemiciclo] Instalando deps via uv... [###       ] 30%
[Hemiciclo] Baixando modelo bge-m3 (~2GB)... [#####     ] 50%
[Hemiciclo] Instalacao concluida em 4m 12s.
[Hemiciclo] Para iniciar: ./run.sh
$ ./run.sh
[Hemiciclo] Subindo Streamlit em http://localhost:8501
[Hemiciclo] Abrindo navegador...
```

#### J2 -- Primeira pesquisa

Tela 1 (Intro narrativo, mostrada só na primeira vez):
```
+------------------------------------------------------------+
|  HEMICICLO                                       [config]  |
|  Inteligencia politica aberta. Soberana. Local.            |
|                                                            |
|  Quem vota a favor do que. Quem mudou de lado. Quem fala   |
|  uma coisa e vota outra. Sem opiniao nossa -- so dados.    |
|                                                            |
|             [ Fazer minha primeira pesquisa -> ]           |
|                                                            |
|             [ Ler manifesto * Como funciona ]              |
+------------------------------------------------------------+
```

Tela 2 (Lista de sessões -- vazia na primeira execução):
```
+------------------------------------------------------------+
|  Hemiciclo  [Pesquisas] [Sobre]                  [+ Nova]  |
+------------------------------------------------------------+
|                                                            |
|  Voce ainda nao fez nenhuma pesquisa.                      |
|                                                            |
|             [ Comecar minha primeira pesquisa ]            |
|                                                            |
+------------------------------------------------------------+
```

Tela 3 (Form Nova Pesquisa):
```
+------------------------------------------------------------+
|  Nova Pesquisa                                             |
|                                                            |
|  Topico: +-------------------------------+                  |
|          | aborto                        | v (sugestoes)   |
|          +-------------------------------+                  |
|                                                            |
|  Casas:  [x] Camara   [ ] Senado                           |
|  Estado: [Todos v]  * Partido: [Todos v]                   |
|  Periodo: [01/01/2015 -----------*---- 27/04/2026]         |
|                                                            |
|  Camadas de analise:                                       |
|  [x] Voto + regex (rapido, sempre confiavel)               |
|  [x] Embeddings semanticos (resgata PLs implicitas)        |
|  [ ] LLM (anota nuance, custa 30min extras)                |
|                                                            |
|  Tempo estimado: ~12 min  *  Espaco: ~340 MB               |
|                                                            |
|             [ Cancelar ]    [ Iniciar pesquisa -> ]        |
+------------------------------------------------------------+
```

Tela 4 (Pipeline rodando):
```
+------------------------------------------------------------+
|  Pesquisa: aborto * Camara * Brasil * 2015-2026            |
|                                                            |
|  [#############                  ] 38%                     |
|  Etapa: Coletando votacoes da Camara (3.421 / 8.900)       |
|  Tempo decorrido: 4m 22s  *  Restante estimado: 7m         |
|                                                            |
|  [ok] Mapeamento topico -> 87 proposicoes relevantes       |
|  [ok] Cadastro parlamentar (513 deputados)                 |
|  [..] Coletando votacoes                                   |
|  [-]  ETL                                                  |
|  [-]  Embeddings                                           |
|  [-]  Modelagem                                            |
|                                                            |
|  Pode fechar o navegador. A coleta continua em background. |
|                                                            |
|             [ Pausar ]    [ Cancelar ]                     |
+------------------------------------------------------------+
```

Tela 5 (Relatório concluído):
```
+------------------------------------------------------------+
|  aborto * Camara * Brasil * 2015-2026         [Exportar]   |
+------------------------------------------------------------+
|  87 proposicoes * 513 deputados * 234 votacoes nominais    |
|                                                            |
|  +- Top 100 a-favor -+  +- Top 100 contra --+              |
|  | 1. Samia Bomfim   |  | 1. Eros Biondini  |              |
|  | 2. Erika Hilton   |  | 2. Pastor Marco   |              |
|  | ...               |  | ...               |              |
|  +-------------------+  +-------------------+              |
|                                                            |
|  +- Assinatura multidimensional (top 20) -------+          |
|  |    [radar/heatmap]                            |         |
|  +-----------------------------------------------+         |
|                                                            |
|  [Grafo da rede] [Historico de conversao] [Word clouds]    |
+------------------------------------------------------------+
```

#### J3 -- Retomar pesquisa interrompida

Streamlit detecta sessão com estado `INTERROMPIDA`:
```
+------------------------------------------------------------+
|  [!]  Pesquisa "aborto-DF" foi interrompida em 2026-04-26  |
|       (etapa: Embeddings, 67% concluido)                   |
|                                                            |
|             [ Retomar de onde parou ]                      |
|             [ Recomecar do zero ]                          |
|             [ Ignorar por agora ]                          |
+------------------------------------------------------------+
```

#### J4 -- Importar sessão de outro João

```
+------------------------------------------------------------+
|  Importar sessao                                           |
|                                                            |
|  [ Escolher .zip ]                                         |
|                                                            |
|  Validacoes automaticas apos upload:                       |
|  * Schema da sessao                                        |
|  * Hash de integridade                                     |
|  * Versao do modelo base usado                             |
|                                                            |
+------------------------------------------------------------+
```

### 10.4 Estados sempre visíveis

Toda página do dashboard tem rodapé fixo:
- Versão do app
- Versão do modelo base instalado
- Quantas sessões existem localmente
- Tamanho do `~/hemiciclo`
- Botão "Abrir pasta de dados"

---

## 11. Validação multi-agente

### 11.1 VALIDATOR_BRIEF.md (na raiz do repo)

Documento curto (< 200 linhas) lido OBRIGATORIAMENTE por todo agente antes de executar/validar sprint. Define invariantes do projeto. Estrutura:

```markdown
# VALIDATOR_BRIEF.md

## Identidade do projeto
Hemiciclo 2.0 -- plataforma cidada de perfilamento parlamentar. Stack Python 3.11+ / Streamlit / DuckDB / Polars. Tudo local. Soberano. Open-source GPLv3.

## Invariantes inegociaveis
- I1. **Tudo local.** Nunca introduzir chamada a servidor central proprietario (Anthropic, OpenAI, etc.) em codigo de producao. LLM camada 4 e opcional e desligada por default.
- I2. **PT-BR sem perda.** Todos os textos visiveis ao usuario em PT-BR com acentuacao correta. Codigos em Python podem ter identifiers PT-BR mas nunca caracteres nao-ASCII em nomes de arquivo ou paths.
- I3. **Determinismo.** Todo modelo (PCA, BERTopic, etc.) recebe `random_state` fixo declarado em `src/hemiciclo/config.py`.
- I4. **Sem prints.** Logs via Loguru, nunca print().
- I5. **Sem TODO sem ID.** Comentario `# TODO` deve ter `# TODO(SXX)` apontando sprint que cuidara.
- I6. **Pydantic v2 estrito.** Todo modelo de dados (Sessao, Params, Status) e Pydantic; sem dicts soltos atravessando modulos.
- I7. **Tipagem estrita.** Mypy --strict zero erros. Sem `Any` em assinatura publica.
- I8. **Ruff zero violacoes.**
- I9. **Cobertura >= 90%** em arquivos novos.
- I10. **Conventional Commits.** Todo commit segue padrao; PRs sem isso sao rejeitados.
- I11. **YAML de topico valida contra _schema.yaml.** Nunca commitar topico invalido.
- I12. **CHANGELOG sempre atualizado.** PR sem entrada Unreleased no CHANGELOG e rejeitado.

## Comandos runtime-real canonicos
- `make check` -- lint + test completo
- `uv run pytest tests/unit -v` -- testes unit
- `uv run hemiciclo --help` -- sanidade do CLI
- `uv run streamlit run src/hemiciclo/dashboard/app.py` -- sobe dashboard
- `python scripts/validar_topicos.py` -- valida YAMLs

## Fontes de verdade
- ADRs em `docs/adr/` -- decisoes imutaveis
- Plano em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- Sprints em `sprints/SPRINT_S*.md`
- ORDEM.md em `sprints/ORDEM.md` -- status global

## Anti-debito (zero follow-up)
Toda descoberta colateral durante execucao vira:
- (a) Edit-pronto na propria sprint, OU
- (b) Spec de sprint nova com ID proprio (`sprints/SPRINT_S<N+1>_*.md`)

Nunca "issue depois". Nunca "TODO solto". Nunca "consertar proximo".

## Tipo de projeto
Backend Python + dashboard Streamlit + CLI. Nao e TUI puro. UI tem componente visual via Streamlit que pode/deve ser validada com skill `validacao-visual` quando diff toca `src/hemiciclo/dashboard/`.
```

### 11.2 Protocolo executor-sprint

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê `sprints/SPRINT_SXX_*.md`.
3. Verifica dependências DONE.
4. Cria/checkout `feature/sXX-slug`.
5. Implementa entregas conforme spec.
6. Roda `make check`.
7. Roda proof-of-work declarado.
8. Atualiza `sprints/ORDEM.md`, `CHANGELOG.md`, docs relevantes.
9. Commits Conventional.
10. Push + PR usando template.
11. Reporta saída do proof-of-work no PR body.

### 11.3 Protocolo validador-sprint

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê spec da sprint.
3. Faz checkout do branch do PR.
4. Roda independentemente:
   - `make check`
   - Proof-of-work do spec
   - `git diff main...HEAD` pra inspeção visual
   - Skill `validacao-visual` se diff toca dashboard
5. Verifica invariantes I1-I12.
6. Verifica acentuação periférica em arquivos modificados.
7. Decide:
   - **APROVADO** -- comenta no PR, libera merge.
   - **APROVADO_COM_RESSALVAS** -- comenta com ressalvas; se forem cosméticas, libera; se forem estruturais, REPROVA.
   - **REPROVADO** -- escreve patch-brief listando fixes específicos. Auto-dispatcha executor-sprint pra refazer.
8. Achados colaterais (não escopo da sprint) viram spec de sprint nova auto-criada (anti-débito).

### 11.4 /sprint-ciclo (skill já disponível)

Comando que orquestra: `/sprint-ciclo <ideia>` ->
1. Dispatcha planejador-sprint (escreve spec).
2. Dispatcha executor-sprint (implementa).
3. Dispatcha validador-sprint (valida).
4. Se REPROVADO, volta a 2 (até 3 retries).
5. Se APROVADO, dispatcha `/commit-push-pr` (auto-commit + push + PR).

---

## 12. Decomposição em sprints

### 12.1 Tabela completa

| ID | Título | Status | Depende | Bloqueia | Esforço | ADRs |
|---|---|---|---|---|---|---|
| S22 | Bootstrap Python + estrutura repo + uv + Makefile + pre-commit | READY | -- | S23..S37 | P | 001, 016, 017, 019 |
| S23 | Shell visível: Streamlit + install.sh/.bat + intro narrativo + lista vazia | READY | S22 | S31 | M | 010, 014 |
| S24 | Coleta Câmara: discursos + votos + proposições + checkpoint | READY | S22 | S26 | M | 002 |
| S25 | Coleta Senado: discursos + votos + cadastro + checkpoint | READY | S22 | S26 | M | 002 |
| S26 | Cache transversal SHA256 + DuckDB schema + migrations | READY | S24, S25 | S27, S29 | P | 012 |
| S27 | Classificador C1+C2: regex + categoria oficial + voto + TF-IDF + YAML schema | READY | S26 | S28 | M | 003, 011 |
| S28 | Modelo base v1 (C3): amostragem + bge-m3 + PCA + persistência | DEPENDS | S26, S27 | S30 | G | 008, 009, 018 |
| S29 | Sessão de Pesquisa: runner subprocess + status + pid.lock + retomada | READY | S26 | S30 | M | 007, 013 |
| S30 | Pipeline integrado: coleta -> ETL -> C1+C2+C3 -> projeção + persistência da sessão | DEPENDS | S28, S29 | S31..S35 | M | 008, 011 |
| S31 | Dashboard sessão: relatório multidimensional + word clouds + séries | DEPENDS | S30 | S38 | G | 010 |
| S32 | Grafos de rede: coautoria + voto + pyvis embedável | DEPENDS | S30 | S38 | M | 004 |
| S33 | Histórico de conversão por parlamentar x tópico | DEPENDS | S30 | S34, S38 | M | 004 |
| S34 | ML de convertibilidade (sklearn + features S32+S33) | DEPENDS | S32, S33 | S38 | G | 004 |
| S34b | Camada 4 LLM opcional (ollama + cache por hash + flag de sessão) | DEPENDS | S30 | -- | M | 011 |
| S35 | Exportação/importação de sessão (zip + verificação de integridade) | DEPENDS | S29 | S38 | P | 007 |
| S36 | install.bat Windows + run.bat (paridade) | DEPENDS | S23 | S38 | P | 014 |
| S37 | CI multi-OS: pytest + ruff + mypy + matriz + coverage upload | READY | S22 | -- | P | 015, 019 |
| S38 | Higienização final: docs/ completo + manifesto + demo gif + release v2.0.0 | DEPENDS | S31..S35 | -- | M | -- |

### 12.2 Caminho crítico (texto)

```
S22 -> S23 ----------------------------------------+
   \                                                |
    +-> S37 (CI, paralelo)                          |
                                                    |
S22 -> S24 -+                                       |
            +-> S26 -> S27 -> S28 -> S30 -+-> S31 -+-> S38
S22 -> S25 -+                             |        |
                                          +-> S32 -+
S22 -> S29 ---------------> S30 ----------+-> S33 -+
                                          |    |   |
                                          |    v   |
                                          |   S34 -+
                                          |        |
                                          +-> S35 -+
                                          |        |
                                          +-> S34b
                                                    |
S23 -> S36 (paralelo, paridade Windows) ------------+
```

### 12.3 Ordem pragmática de execução

| # | Sprint | Razão da posição |
|---|---|---|
| 1 | S22 | Bootstrap absoluto |
| 2 | S23 | Sinal de vida visível pro usuário |
| 3 | S37 | CI verde desde cedo protege investimento |
| 4 | S24 + S25 (paralelo) | Coleta de dados real |
| 5 | S26 | Cache + schema unificado |
| 6 | S27 | Classificador C1+C2 (sem ML pesado) |
| 7 | S29 (paralelo a 6) | Runner pode ser desenvolvido sem dados |
| 8 | S28 | Modelo base -- depende de coleta real |
| 9 | S30 | Integra tudo em pipeline |
| 10 | S31 | Dashboard com dados reais |
| 11 | S32, S33, S35 (paralelo) | Profundidade adicional |
| 12 | S34 | ML com features de S32+S33 |
| 13 | S34b | LLM opcional, não bloqueia v2.0.0 |
| 14 | S36 | Paridade Windows quando dashboard maduro |
| 15 | S38 | Higienização + release |

---

## 13. Especificações concretas das 4 primeiras sprints

A seguir, sprints S22, S23, S24 e S37 escritas no padrão ULTRA-DETALHADO da seção 9.2. Servem de gabarito; demais sprints seguem o mesmo padrão e serão escritas durante execução.

---

### 13.1 SPRINT_S22_BOOTSTRAP.md

```markdown
# Sprint S22 -- Bootstrap Python + estrutura repo + uv + Makefile + pre-commit

**Projeto:** Hemiciclo
**Versao alvo:** v2.0.0
**Data criacao:** 2026-04-27
**Autor:** @AndreBFarias
**Status:** READY
**Depende de:** --
**Bloqueia:** S23, S24, S25, S29, S37
**Esforco:** P
**ADRs vinculados:** ADR-001, ADR-016, ADR-017, ADR-019
**Branch:** feature/s22-bootstrap

---

## 1. Objetivo

Criar a infraestrutura minima do projeto Python (estrutura de diretorios, pyproject.toml, uv lock, Makefile, pre-commit, .editorconfig, .gitignore, devcontainer) preservando o codigo R em branch `legacy-r`.

## 2. Contexto

O repo esta em R. Antes de qualquer feature, precisa virar projeto Python com tooling moderno. Sem isso, sprints subsequentes nao tem onde executar.

## 3. Escopo

### 3.1 In-scope

- [x] Branch `legacy-r` criado preservando estado atual do codigo R
- [x] Branch `feature/s22-bootstrap` para esta sprint
- [x] `pyproject.toml` PEP 621 com metadata + deps minimas + extras dev
- [x] `uv.lock` deterministico
- [x] Estrutura `src/hemiciclo/` com `__init__.py`, `__main__.py`, `cli.py` stub, `config.py`
- [x] Estrutura `tests/` com `conftest.py` e um teste sentinela
- [x] `Makefile` completo (secao 8.1 do plano)
- [x] `.pre-commit-config.yaml` (secao 6.4)
- [x] `.editorconfig` (secao 8.3)
- [x] `.gitignore` Python expandido + manter padroes R
- [x] `.python-version` com `3.11`
- [x] `.devcontainer/` com Dockerfile e devcontainer.json
- [x] `.vscode/settings.json`, `launch.json`, `extensions.json`
- [x] `scripts/bootstrap.sh` e `scripts/bootstrap.bat`
- [x] `VALIDATOR_BRIEF.md` na raiz (secao 11.1 do plano)
- [x] Copia do plano em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- [x] `docs/adr/README.md` + ADR-001 a ADR-011 escritos
- [x] CLI hemiciclo com comandos stub: `hemiciclo --version`, `hemiciclo --help`

### 3.2 Out-of-scope

- Coleta real de APIs -- fica em S24/S25
- Streamlit dashboard -- fica em S23
- Validador de YAML de topico -- fica em S27
- CI no GitHub Actions -- fica em S37 (mas pre-commit local ja esta ativo)

## 7. Proof-of-work runtime-real

bash
$ make bootstrap && make check && uv run hemiciclo --version

**Saida esperada:**

hemiciclo 0.1.0

E `make check` passa todos os testes (3) com cobertura >= 90% nos arquivos criados.

**Criterio de aceite:**
- [ ] `hemiciclo --version` retorna exit 0 com semver valido
- [ ] `make check` passa
- [ ] Pre-commit roda sem alteracao em arquivos
- [ ] `uv.lock` commitado
- [ ] `legacy-r` branch existe no remoto
- [ ] 11 ADRs presentes em `docs/adr/`
- [ ] `VALIDATOR_BRIEF.md` na raiz
- [ ] CHANGELOG.md tem entrada `## [Unreleased]` com bullet do bootstrap

## 10. Proximo passo

S37 (CI) ou S23 (shell visivel) podem iniciar em paralelo.
```

---

### 13.2 SPRINT_S23_SHELL_VISIVEL.md

```markdown
# Sprint S23 -- Shell visivel: Streamlit + install.sh + intro narrativo + lista vazia

**Status:** DEPENDS (S22)
**Depende de:** S22
**Bloqueia:** S31, S36
**Esforco:** M
**ADRs vinculados:** ADR-010, ADR-014
**Branch:** feature/s23-shell-visivel

## 1. Objetivo

Entregar primeiro sinal de vida visivel: usuario roda `./install.sh` (Linux/macOS) e `./run.sh`, navegador abre em `localhost:8501` mostrando intro narrativo + lista de sessoes vazia + botao "Nova pesquisa" funcional (form configurado, mas pipeline ainda nao roda).

## 3. Escopo

### 3.1 In-scope

- [x] `install.sh` Linux/macOS detecta Python 3.11+, cria venv, sincroniza deps, baixa NADA pesado ainda
- [x] `run.sh` ativa venv, roda `streamlit run`, abre browser automaticamente
- [x] `src/hemiciclo/dashboard/app.py` completo
- [x] `tema.py`, `style.css`, `componentes.py`
- [x] Pagina `intro.py` com texto manifesto curto e CTA "Primeira pesquisa"
- [x] Pagina `lista_sessoes.py` le `~/hemiciclo/sessoes/` e renderiza cards (vazia = call-to-action)
- [x] Pagina `nova_pesquisa.py` form completo (topico, casa, UF, partido, periodo, camadas) -- botao "Iniciar" mostra mensagem "Funcionalidade em S30" por enquanto
- [x] Pagina `sobre.py` com manifesto longo
- [x] Rodape global com versao, sessoes, tamanho de `~/hemiciclo`
- [x] Storytelling por aba conforme `stilingue-energisa-etl`
- [x] Tema visual aplicado (cores da secao 10.2)
- [x] Streamlit configurado para `wide` + `collapsed` sidebar
- [x] Testes de UI minimos via `streamlit.testing.v1.AppTest`
- [x] `docs/usuario/instalacao.md` Linux/macOS

### 3.2 Out-of-scope

- install.bat Windows -- fica em S36
- Pipeline real de pesquisa -- botao "Iniciar" so sinaliza
- Mock de sessoes fake na lista -- `seed_dados.py` e separado e opcional

## 7. Proof-of-work runtime-real

bash
$ ./install.sh && ./run.sh &
$ sleep 5 && curl -s http://localhost:8501/healthz
$ uv run pytest tests/integracao/test_dashboard_smoke.py -v

**Saida esperada:**
- `curl` retorna `{"status": "ok"}` (Streamlit health endpoint)
- pytest passa todos os 4 testes (um por pagina)

**Criterio de aceite:**
- [ ] Usuario Linux/macOS limpo consegue rodar `./install.sh && ./run.sh` em < 5min
- [ ] Browser abre em localhost:8501
- [ ] Tela inicial mostra intro narrativo
- [ ] Botao "Nova pesquisa" leva ao form
- [ ] Form valida `ParametrosBusca` antes de submit
- [ ] Tema visual aplicado
- [ ] Cobertura >= 90%
```

---

### 13.3 SPRINT_S24_COLETA_CAMARA.md

```markdown
# Sprint S24 -- Coleta Camara: discursos + votos + proposicoes + checkpoint

**Status:** DEPENDS (S22)
**Bloqueia:** S26, S30
**Esforco:** M
**ADRs vinculados:** ADR-002
**Branch:** feature/s24-coleta-camara

## 1. Objetivo

Implementar coleta resiliente da API Camara dos Deputados -- discursos, votacoes nominais, proposicoes, cadastro -- com checkpoint persistente, retomada idempotente, retry com backoff exponencial e rate limiting.

## 3. Escopo

### 3.1 In-scope

- [x] `src/hemiciclo/coleta/http.py` -- wrapper httpx com tenacity (retry exponencial 5 tentativas, max 60s entre)
- [x] `src/hemiciclo/coleta/rate_limit.py` -- token bucket configuravel (default 10 req/s)
- [x] `src/hemiciclo/coleta/checkpoint.py` -- Pydantic CheckpointCamara serializado em JSON, escrita atomica
- [x] `src/hemiciclo/coleta/camara.py` -- funcoes `coletar_proposicoes()`, `coletar_votacoes()`, `coletar_votos_de_votacao()`, `coletar_discursos()`, `coletar_cadastro_deputados()`
- [x] CLI: `hemiciclo coletar camara --legislatura 55 56 57 --tipos proposicoes votacoes votos discursos`
- [x] Persistencia em Parquet via Polars (nao DuckDB ainda -- schema unificado fica em S26)
- [x] Logs estruturados Loguru
- [x] Testes com `respx` (mock de httpx) cobrindo: caminho feliz, 503 com retry, kill no meio + retomada
- [x] Testes de propriedade (hypothesis) sobre serializacao do checkpoint
- [x] `docs/arquitetura/coleta.md`

### 3.2 Out-of-scope

- Senado -- fica em S25
- DuckDB schema unificado -- fica em S26
- Mapeamento topico->PL -- fica em S27

## 5. Implementacao detalhada

### 5.1 Endpoints alvo (Camara -- Dados Abertos)

- `GET /deputados` -- cadastro
- `GET /deputados/{id}` -- detalhe
- `GET /proposicoes?ano=&siglaTipo=` -- listagem
- `GET /proposicoes/{id}` -- detalhe + autores
- `GET /votacoes?dataInicio=&dataFim=` -- votacoes
- `GET /votacoes/{id}/votos` -- voto individual
- Discursos (legacy SitCamaraWS) -- manter padrao do R

### 5.2 Estrutura do checkpoint

```python
class CheckpointCamara(BaseModel):
    iniciado_em: datetime
    atualizado_em: datetime
    legislaturas: list[int]
    tipos: list[str]
    proposicoes_baixadas: set[int]
    votacoes_baixadas: set[str]
    votos_baixados: set[tuple[str, int]]  # (votacao_id, deputado_id)
    discursos_baixados: set[str]
    deputados_baixados: set[int]
    erros: list[dict]  # {url, codigo, mensagem, timestamp}
```

Salvo em `~/hemiciclo/cache/checkpoints/camara_<hash_params>.json` a cada 50 requisicoes.

## 7. Proof-of-work runtime-real

bash
$ uv run hemiciclo coletar camara \
    --legislatura 57 \
    --tipos proposicoes \
    --max-itens 100 \
    --output /tmp/camara_smoke
$ ls /tmp/camara_smoke/proposicoes.parquet
$ uv run python -c "import polars as pl; df = pl.read_parquet('/tmp/camara_smoke/proposicoes.parquet'); print(f'rows: {len(df)}, cols: {len(df.columns)}')"

**Saida esperada:**

rows: 100, cols: >= 12

(12 colunas minimas: id, sigla, numero, ano, ementa, tema_oficial, autor_principal, data_apresentacao, status, url_inteiro_teor, casa, hash_conteudo)

**Teste de retomada:**
bash
$ uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 200 &
$ sleep 3 && kill -9 $!
$ uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 200

Segunda execucao deve completar em < 50% do tempo da primeira (cache + checkpoint funcionando).

**Criterio de aceite:**
- [ ] Coleta de 100 proposicoes completa em < 60s
- [ ] kill -9 + relancar retoma exatamente de onde parou
- [ ] 503 da API gera retry com backoff visivel em log
- [ ] Cobertura >= 90%
- [ ] Mypy strict zero erros
- [ ] respx mocks cobrem 12 cenarios
```

---

### 13.4 SPRINT_S37_CI.md

```markdown
# Sprint S37 -- CI multi-OS: pytest + ruff + mypy + matriz + coverage

**Status:** DEPENDS (S22)
**Esforco:** P
**ADRs vinculados:** ADR-015, ADR-019
**Branch:** feature/s37-ci

## 1. Objetivo

Configurar GitHub Actions com matriz `{ubuntu-22.04, macos-14, windows-2022} x {python-3.11, python-3.12}`, rodando lint + unit + integracao + smoke install em cada job, e publicando coverage no Codecov.

## 3. Escopo

### 3.1 In-scope

- [x] `.github/workflows/ci.yml` matriz completa
- [x] `.github/workflows/release.yml` esqueleto (nao dispara ainda -- fica armado pro v2.0.0)
- [x] `.github/workflows/adr-check.yml`
- [x] `.github/workflows/stale.yml`
- [x] `.github/dependabot.yml`
- [x] `.github/CODEOWNERS`
- [x] `.github/ISSUE_TEMPLATE/{bug,feature,topico}.md`
- [x] `.github/PULL_REQUEST_TEMPLATE.md`
- [x] Badge CI no README.md
- [x] Badge coverage no README.md
- [x] `docs/dev/workflow.md`

### 3.2 Out-of-scope

- E2E completo -- `@pytest.mark.slow` rodando so em main
- Publicacao no PyPI -- fica para v2.1.x

## 5. Implementacao detalhada

### 5.1 ci.yml literal (esqueleto)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: ${{ matrix.os }} / Python ${{ matrix.python }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-22.04, macos-14, windows-2022]
        python: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv python install ${{ matrix.python }}
      - run: uv sync --frozen --all-extras
      - run: uv run python scripts/validar_topicos.py
      - run: uv run python scripts/validar_adr.py
      - run: uv run ruff check src tests
      - run: uv run ruff format --check src tests
      - run: uv run mypy --strict src
      - run: uv run pytest tests/unit tests/integracao --cov=src/hemiciclo --cov-report=xml
      - uses: codecov/codecov-action@v4
        if: matrix.os == 'ubuntu-22.04' && matrix.python == '3.11'
        with:
          files: coverage.xml
```

## 7. Proof-of-work runtime-real

Pipeline CI verde no PR desta sprint nos 6 jobs da matriz.

**Criterio de aceite:**
- [ ] 6 jobs verdes
- [ ] Coverage >= 90% reportada no Codecov
- [ ] Badges no README atualizados
- [ ] PR template aplicado
```

---

## 14. Verificação end-to-end (definição de "pronto" v2.0.0)

O projeto está em estado entregável quando, **na máquina de um usuário Linux/macOS/Windows que nunca tocou o repo**:

1. `git clone` + `./install.sh` (ou `install.bat`) completa em < 30 min com Python 3.11 instalado
2. `./run.sh` (ou `run.bat`) abre browser em localhost:8501
3. Tela inicial: intro narrativo + lista de sessões + botão "Nova pesquisa"
4. Configurando "aborto / Câmara / DF / 57ª", pipeline:
   a. Mostra progresso em tempo real
   b. Sobrevive a fechar browser
   c. Sobrevive a queda de internet (retoma do checkpoint)
   d. Conclui em < 20 min
5. Sessão concluída exibe: top 100 a-favor / top 100 contra, assinatura multidimensional dos top 20, grafo interativo, histórico de conversão, word clouds, exportação como zip
6. `make check` passa, CI verde nos 6 jobs
7. Sessão exportada (zip) é importável noutra máquina e gera o mesmo relatório (determinismo)
8. Documentação completa em `docs/`, README com gif demo, manifesto.md publicado

---

## 15. Riscos & mitigações (consolidados)

| Risco | Mitigação |
|---|---|
| APIs Câmara/Senado caem | Checkpoint a cada N + tenacity backoff |
| bge-m3 pesado pro install | Detecção de hardware + opção --cpu-only |
| Determinismo do PCA entre máquinas | random_state fixo + base versionado + snapshot tests |
| Streamlit travando com grafos > 500 nós | pyvis HTML standalone + sampling + filtros |
| YAML de tópicos PR-bottleneck | Schema validado em CI + override local sobrescreve repo |
| Windows sem Python 3.11 | install.bat detecta + oferece link Python.org |
| Volume explode em sessões amplas | Aviso de tempo estimado + cancelamento + cache transversal |
| Agente executor toma decisão fora do escopo | VALIDATOR_BRIEF.md + reprovação por validador-sprint |
| Drift entre lock files | uv sync --frozen no CI, falha se drift |
| ADRs ficam desatualizados | adr-check.yml valida formato; PR sem ADR vinculado em decisão grande é rejeitado |

---

## 16. Próximos passos imediatos

Após aprovação deste plano expandido:

1. **Iniciar execução de S22** via `/sprint-ciclo` ou execução manual.
2. Sprint S22 cria todos os artefatos transversais (VALIDATOR_BRIEF, ADRs, devcontainer, Makefile, pre-commit).
3. Após S22 DONE, S37 e S23 podem rodar em paralelo (sub-agentes).
4. Após S22+S23+S37, S24 e S25 em paralelo.
5. Cadeia segue até S38 conforme caminho crítico (seção 12.3).

Cada sprint passa por planejador-sprint -> executor-sprint -> validador-sprint via `/sprint-ciclo`.

---

## 17. Observações finais

Este plano é **denso por design** -- é referência pras 17 sprints, não cartilha linear. Cada sprint individual terá sua própria spec curta seguindo o padrão da seção 9.2, com proof-of-work runtime-real verificável.

A arquitetura entrega o que o manifesto exige: ferramenta de inteligência política aberta, soberana, auditável, instalável pelo cidadão comum, equivalente em rigor metodológico ao que se vende hoje a clientes corporativos -- invertida em direção: do lobista de volta ao cidadão.

Cada sprint é executável por agente Claude Opus, Sonnet ou Haiku desde que o agente:
1. Leia VALIDATOR_BRIEF.md primeiro.
2. Siga o spec literal.
3. Rode o proof-of-work declarado.
4. Não invente escopo fora do declarado in-scope.

O validador-sprint atua como portão final: nenhum PR funde sem validação independente do proof-of-work + verificação de invariantes.

**Fim do plano R2.**
