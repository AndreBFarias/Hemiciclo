# Sprint S27.1 -- `votacoes.proposicao_id` para destravar JOIN de votos

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (primeira release do nível 1 anti-débito)
**Data criação:** 2026-04-28 (registrado em S27); promovido a IN_PROGRESS em 2026-04-28 após release v2.0.0
**Autor:** descoberto pelo executor-sprint da S27
**Status:** DONE (2026-04-28)
**Depende de:** S26 (DONE), S27 (DONE)
**Bloqueia:** recall completo da camada de voto -- ouro analítico do produto
**Esforço:** P (1 dia)
**ADRs vinculados:** ADR-012 (schema DuckDB unificado)
**Branch:** feature/s27-1-migration-m002

---

## 1. Problema

A tabela `votacoes` (S26 schema v1) tem `(id, casa, data, hora, descricao, resultado, totais...)` mas **não tem `proposicao_id`**. Resultado: o JOIN `votos x votacoes x proposicoes` em `agregar_voto_por_parlamentar` (S27, classificador C1) não consegue filtrar votações ligadas às proposições relevantes para um tópico.

A função detecta dinamicamente via `information_schema.columns` se a coluna existe; sem ela, retorna DataFrame vazio com log de aviso. Isso preserva o pipeline mas **zera o recall da camada de voto** em DBs reais.

## 2. Achado original

Exposto durante implementação da S27 (`src/hemiciclo/modelos/classificador_c1.py:agregar_voto_por_parlamentar`). Test `test_agregar_voto_sem_proposicao_id_retorna_vazio` documenta o comportamento atual; `test_agregar_voto_com_proposicao_id_funciona` simula a situação pós-S27.1 via `ALTER TABLE votacoes ADD COLUMN proposicao_id BIGINT` no fixture.

## 3. Escopo

### 3.1 In-scope

- [ ] **Migration M002** em `src/hemiciclo/etl/migrations.py`:
  - `ALTER TABLE votacoes ADD COLUMN IF NOT EXISTS proposicao_id BIGINT`
  - Idempotente (DuckDB suporta `IF NOT EXISTS`)
- [ ] **Schema v2** em `src/hemiciclo/etl/schema.py`:
  - Nova versão constante `SCHEMA_VERSAO = 2`
  - DDL canônico de `votacoes` ganha `proposicao_id BIGINT`
- [ ] **Coletor Câmara** em `src/hemiciclo/coleta/camara.py`:
  - `_normalizar_votacao` extrai `proposicao_.id` da resposta da API e popula
  - `SCHEMA_VOTACAO` ganha `proposicao_id: pl.Int64()`
- [ ] **Coletor Senado** em `src/hemiciclo/coleta/senado.py`:
  - `_normalizar_votacao` mapeia o campo equivalente (`Materia/CodigoMateria` no XML do Senado)
- [ ] **Consolidador** em `src/hemiciclo/etl/consolidador.py`:
  - `_inserir_votacoes_camara` e `_inserir_votacoes_senado` incluem `proposicao_id` no INSERT
- [ ] **Backfill opcional** em `scripts/backfill_proposicao_id.py`:
  - Para parquets de votação já coletados sem `proposicao_id`, re-fetch leve da API por ID
  - Documentar que é opcional (rodar coleta de novo também resolve)
- [ ] **Testes unit** novos:
  - `test_migrations.py::test_m002_adiciona_proposicao_id`
  - `test_schema.py::test_votacoes_tem_proposicao_id_em_v2`
  - `test_consolidador.py::test_proposicao_id_persiste`
- [ ] **Testes e2e**:
  - `test_classificador_e2e.py::test_agregar_voto_em_db_pos_s27_1` -- usa fluxo real de migração
- [ ] Atualizar `docs/arquitetura/cache_e_db.md` e `classificacao_multicamada.md` removendo a "limitação atual"

### 3.2 Out-of-scope

- Backfill automático de votações antigas (mantém-se como script manual)
- Campos adicionais de votação (orientação de bancada, etc.) -- futura sprint S30+

## 4. Proof-of-work runtime-real

```bash
$ make check                                  # 207+ testes
$ uv run hemiciclo db init --db-path /tmp/s27_1.duckdb
$ uv run hemiciclo db info --db-path /tmp/s27_1.duckdb  # schema v2
$ uv run hemiciclo coletar camara --legislatura 57 --tipos votacoes --max-itens 30 --output /tmp/v27_1
$ uv run hemiciclo db consolidar --parquets /tmp/v27_1 --db-path /tmp/s27_1.duckdb
$ uv run hemiciclo classificar --topico topicos/aborto.yaml --db-path /tmp/s27_1.duckdb --camadas regex,votos --output /tmp/r.json
# Esperado: n_parlamentares > 0 (com dados reais coletados)
```

## 5. Critério de aceite

- [ ] Migration M002 aplica em DBs v1 sem perder dados.
- [ ] `votacoes.proposicao_id` é populado por novas coletas (Câmara e Senado).
- [ ] `agregar_voto_por_parlamentar` retorna agregação não-vazia em DB com votações reais.
- [ ] `make check` continua verde com cobertura ≥ 90%.

## 6. Próximo passo após DONE

Desbloqueia recall completo da camada de voto (C1) e habilita métricas reais para S28 (modelo base PCA).
