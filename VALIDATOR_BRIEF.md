# VALIDATOR_BRIEF.md

> Documento de invariantes do projeto Hemiciclo 2.0. Lido OBRIGATORIAMENTE por todo agente Claude antes de executar ou validar qualquer sprint. Tem precedência sobre specs individuais de sprint quando houver conflito.

## Identidade do projeto

Hemiciclo 2.0 -- plataforma cidadã de perfilamento parlamentar.

- **Stack:** Python 3.11+ / Streamlit / DuckDB / Polars
- **Filosofia:** tudo local na máquina do usuário; soberania total dos dados; zero infra central
- **Licença:** GPL v3 (open-source GPL'd)
- **Manifesto:** ferramenta de inteligência política aberta, equivalente em rigor metodológico ao que se vende a lobistas, mas disponível pra qualquer cidadão sem custo nem rastreio

## Tipo de projeto

Backend Python + dashboard Streamlit + CLI Typer. Não é TUI puro. UI tem componente visual via Streamlit que pode/deve ser validada com skill `validacao-visual` quando diff toca `src/hemiciclo/dashboard/`.

## Invariantes inegociáveis

| ID | Regra | Verificação |
|---|---|---|
| I1 | **Tudo local.** Nunca chamada a servidor central proprietário em código de produção. LLM camada 4 é opcional e desligada por default. | grep por hosts proprietários em `src/` |
| I2 | **PT-BR sem perda.** Textos visíveis ao usuário em PT-BR com acentuação correta. Identifiers em código podem ser PT-BR mas paths de arquivo apenas ASCII. | inspeção de arquivos modificados |
| I3 | **Determinismo.** Todo modelo (PCA, BERTopic, etc.) recebe `random_state` fixo declarado em `src/hemiciclo/config.py`. | grep `random_state` |
| I4 | **Sem prints.** Logs via Loguru, nunca `print()`. | `grep -rn "print(" src/` deve retornar zero |
| I5 | **Sem TODO sem ID.** Comentário `# TODO` exige `# TODO(SXX)` apontando sprint que cuidará. | grep `TODO` sem `(S` |
| I6 | **Pydantic v2 estrito.** Toda Sessão, Params, Status é Pydantic; sem dicts soltos atravessando módulos. | inspeção de assinaturas |
| I7 | **Tipagem estrita.** `mypy --strict` zero erros. Sem `Any` em assinatura pública. | `uv run mypy --strict src` |
| I8 | **Ruff zero violações.** `ruff check` e `ruff format --check` limpos. | `uv run ruff check src tests` |
| I9 | **Cobertura >= 90%** em arquivos novos da sprint. | `pytest --cov` |
| I10 | **Conventional Commits.** Todo commit segue `<tipo>(<escopo>): descrição`. PRs sem isso são rejeitados. | inspeção de `git log` do PR |
| I11 | **YAML de tópico valida contra `topicos/_schema.yaml`.** Nunca commitar tópico inválido. | `python scripts/validar_topicos.py` |
| I12 | **CHANGELOG sempre atualizado.** PR sem entrada `## [Unreleased]` no CHANGELOG é rejeitado. | inspeção de CHANGELOG.md |

## Comandos runtime-real canônicos

- `make check` -- lint + test completo
- `make bootstrap` -- setup completo do ambiente
- `uv run pytest tests/unit -v` -- testes unit
- `uv run pytest tests/integracao -v` -- testes integração
- `uv run hemiciclo --help` -- sanidade do CLI
- `uv run streamlit run src/hemiciclo/dashboard/app.py` -- sobe dashboard
- `python scripts/validar_topicos.py` -- valida YAMLs

## Fontes de verdade

- **ADRs** em `docs/adr/` -- decisões imutáveis. Mudar ADR exige criar novo ADR substituindo o anterior.
- **Plano R2** em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` -- referência mestre.
- **Sprints** em `sprints/SPRINT_S*.md` -- contratos de execução.
- **ORDEM.md** em `sprints/ORDEM.md` -- status global e grafo de dependências.

## Anti-débito (zero follow-up acumulado)

Toda descoberta colateral durante execução vira:
- (a) **Edit-pronto na própria sprint** (se trivial e dentro do espírito do escopo), OU
- (b) **Spec de sprint nova** com ID próprio (`sprints/SPRINT_S<N+1>_*.md`), criada pelo agente que descobriu

Nunca "issue depois". Nunca "TODO solto". Nunca "consertar próximo". Nunca código morto comentado.

## Branches e merges

- `main` -- protegido. PR obrigatório, CI verde, validação aprovada.
- `feature/s<NN>-<slug>` -- branch de sprint.
- `legacy-r` -- preserva código R em estado funcional. Não tocar.
- `fix/<id>-<slug>`, `docs/<slug>`, `chore/<slug>` -- branches auxiliares.

## Modelo de execução de sessão (referência rápida)

Sessão de Pesquisa = unidade autocontida em `~/hemiciclo/sessoes/<id>/` com:
- `params.json` (ParametrosBusca)
- `status.json` (StatusSessao, atualizado pelo subprocess)
- `pid.lock` (PID + timestamp + checksum)
- `dados.duckdb`, `discursos.parquet`, `votos.parquet`
- `modelos_locais/`, `relatorio_state.json`, `log.txt`, `manifesto.json`

Subprocess Python autônomo. Streamlit faz polling em `status.json`. PID lockfile detecta morte sem update. Retomada via checkpoint persistente.

## Decisões fundadoras (D1-D11)

Todas registradas como ADRs (001-011). Mudar qualquer uma exige nova rodada de brainstorming + ADR substituindo. Resumo:

- D1: Stack Python+Streamlit+DuckDB+Polars
- D2: Voto nominal como espinha dorsal
- D3: Mapeamento tópico->PL híbrido (regex + categoria oficial + YAML curado)
- D4: Assinatura indutiva 7 eixos (posição, intensidade, hipocrisia, volatilidade, centralidade, convertibilidade, enquadramento)
- D5: Caminho indutivo data-driven, não dedutivo-teórico
- D6: Tudo local
- D7: Sessão de Pesquisa cidadão de primeira classe
- D8: Modelo base global + ajuste fino local
- D9: Embeddings BAAI/bge-m3
- D10: Shell visível antes de ETL real (UX-first)
- D11: Classificação multicamada em cascata (regex + voto + embeddings + LLM opcional)
