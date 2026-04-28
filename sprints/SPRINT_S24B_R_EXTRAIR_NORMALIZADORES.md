# Sprint S24b-r -- Extrair `_normalizar_*` de `coleta/camara.py` para `coleta/normalizar.py`

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.x (housekeeping pós S24b)
**Data criação:** 2026-04-28
**Autor:** executor-sprint S24b (achado colateral previsto pelo próprio spec da S24b §6 e §R6)
**Status:** READY
**Depende de:** S24b (DONE)
**Bloqueia:** -- (apenas higiene; futura sprint S24g/h reusa o módulo extraído)
**Esforço:** P (1 dia)
**Branch sugerida:** `refactor/s24b-r-extrair-normalizadores-camara`

---

## 1. Objetivo

Extrair as 5 funções `_normalizar_*` de `src/hemiciclo/coleta/camara.py` para um módulo dedicado `src/hemiciclo/coleta/normalizar.py`, devolvendo `camara.py` para abaixo do limite operacional de **800 linhas** acordado em §6 do spec da S24b.

## 2. Contexto

Aritmética da S24b confirmada empiricamente após implementação:

```
src/hemiciclo/coleta/camara.py:
  baseline (pré-S24b) = 692 linhas
  pós-S24b           = 898 linhas (+206 linhas: SCHEMA, 2 funções públicas, bloco no orquestrador)
  meta operacional   = ≤ 800 linhas
  excedente          = 98 linhas
```

O próprio spec da S24b já antecipou esta sub-sprint em §6 e §R6 ("Atenção: ultrapassa 800L -- se executor confirmar (`wc -l`), abrir sub-sprint de extração `S24b-r`...").

Funções candidatas a mudar de casa (todas privadas, todas puras):

- `_normalizar_proposicao(item)` -- ~16 linhas
- `_normalizar_votacao(item)` -- ~30 linhas
- `_normalizar_voto(votacao_id, item)` -- ~10 linhas
- `_normalizar_discurso(item)` -- ~14 linhas
- `_normalizar_deputado(item, legislatura)` -- ~10 linhas
- (`_hash_texto(texto)` é dependência -- vai junto)

Total estimado: ~85-95 linhas saem de `camara.py`. Camara.py projetado: **~803-813 linhas** (perto do limite). Se ainda assim ficar acima, extrair também `_escrever_parquet` (~14 linhas), `ano_inicial_legislatura` (~7 linhas) e os schemas Polars.

## 3. Escopo

### 3.1 In-scope

- [ ] Criar `src/hemiciclo/coleta/normalizar.py` com docstring de módulo explicando que reúne normalizadores puros (sem rede, sem checkpoint) usados pelo coletor da Câmara.
- [ ] Mover as 5 funções `_normalizar_*` + `_hash_texto` mantendo assinaturas e docstrings idênticas.
- [ ] Em `coleta/camara.py`, substituir as definições por `from hemiciclo.coleta.normalizar import (_normalizar_proposicao, _normalizar_votacao, _normalizar_voto, _normalizar_discurso, _normalizar_deputado, _hash_texto)`.
- [ ] Confirmar `wc -l src/hemiciclo/coleta/camara.py ≤ 800` após extração.
- [ ] Se ainda > 800: extrair `_escrever_parquet` para `coleta/parquet_io.py` e os schemas (`SCHEMA_*`) para `coleta/schemas.py`.
- [ ] Rodar `uv run pytest tests/unit/test_coleta_camara.py tests/unit/test_coleta_camara_detalhe.py tests/integracao/test_coleta_camara_e2e.py tests/integracao/test_coleta_camara_enriquecimento_e2e.py` -- todos verdes (refactor puro).
- [ ] Rodar `make check` -- ruff/mypy/pytest verde com cobertura ≥ 90%.
- [ ] Atualizar `docs/arquitetura/coleta.md` -- citar o novo módulo `normalizar.py`.
- [ ] Atualizar `sprints/ORDEM.md` -- marcar S24b-r como DONE com data ao final.

### 3.2 Out-of-scope

- Mudar comportamento dos normalizadores (qualquer mudança não-cosmética é blocker).
- Refatorar o orquestrador `executar_coleta`.
- Modificar testes a não ser para corrigir imports caso usem `from hemiciclo.coleta.camara import _normalizar_*` diretamente.

## 4. Implementação detalhada

### 4.1 Passo a passo

1. Criar `src/hemiciclo/coleta/normalizar.py` com:
   - Imports mínimos: `from typing import Any` e `import hashlib`.
   - Docstring de módulo.
   - 5 funções `_normalizar_*` + `_hash_texto`, copiadas literalmente.
2. Em `coleta/camara.py`:
   - Apagar as 5 funções e `_hash_texto`.
   - Adicionar import: `from hemiciclo.coleta.normalizar import (...)`.
3. Rodar `wc -l src/hemiciclo/coleta/camara.py`. Se > 800:
   - Criar `src/hemiciclo/coleta/parquet_io.py` com `_escrever_parquet`.
   - Criar `src/hemiciclo/coleta/schemas.py` com os 6 dicts `SCHEMA_*` (incluindo `SCHEMA_PROPOSICAO_DETALHE`).
   - Atualizar imports em `camara.py`.
4. Rodar `make check` -- todo verde.
5. Acentuação periférica em todos arquivos novos/modificados.
6. Commit conventional: `refactor(coleta): extrai normalizadores de camara.py para normalizar.py (S24b-r)`.

### 4.2 Critério numérico

```
wc -l src/hemiciclo/coleta/camara.py  # esperado: ≤ 800
wc -l src/hemiciclo/coleta/normalizar.py  # esperado: ~110-130
```

## 5. Riscos

| # | Risco | Probabilidade | Mitigação |
|---|---|---|---|
| R1 | Algum teste importa `_normalizar_*` direto de `camara.py` | A | Re-export em `camara.py` ou ajustar imports nos testes (preferível) |
| R2 | Após extração ainda > 800L | M | Plano B previsto: extrair também schemas e parquet_io |
| R3 | Refactor introduz regressão sutil | B | Testes existentes da S24+S24b cobrem todos os ramos |

## 6. Proof-of-work

```bash
# Antes da extração
wc -l src/hemiciclo/coleta/camara.py  # 898

# Após extração
wc -l src/hemiciclo/coleta/camara.py src/hemiciclo/coleta/normalizar.py
# Esperado camara.py ≤ 800, normalizar.py ~110-130

# Sanidade total
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict src
uv run pytest tests/unit tests/integracao -q --cov=src/hemiciclo --cov-report=term-missing
# Esperado: todos verdes, cobertura ≥ 90% mantida.
```

## 7. Referências

- Spec da sprint mãe: `sprints/SPRINT_S24B_PROPOSICOES_DETALHE.md` §6 e §R6
- Bitácula de implementação: `sprints/ORDEM.md` linha S24b
- BRIEF: `VALIDATOR_BRIEF.md`
- Código tocado: `src/hemiciclo/coleta/camara.py` (898L baseline)
