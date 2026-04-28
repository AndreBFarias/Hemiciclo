# Sprint S35 -- Exportação/importação de sessão (zip + verificação de integridade)

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S29 (DONE), S30 (DONE)
**Bloqueia:** S38
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-007 (sessão como cidadão de primeira classe)
**Branch:** feature/s35-export-import

---

## 1. Objetivo

Substituir os stubs `exportar_zip` e `importar_zip` da S29 por implementação real com verificação de integridade via `manifesto.json` (gerado em S30).

Sessão exportada vira artefato compartilhável: pesquisador A roda análise, gera zip, envia pra pesquisador B que importa e abre no próprio dashboard sem refazer coleta. **Ferramenta de jornalista/ativista**, conforme manifesto.

## 2. Contexto

S29 entregou stubs em `sessao/exportador.py`. S30 popula `manifesto.json` com SHA256 de cada artefato + `limitacoes_conhecidas`. Esta sprint conecta os dois: `importar_zip` valida hashes contra `manifesto.json`, recusa imports adulterados.

O zip exclui artefatos pesados/regeneráveis: `dados.duckdb` (regenerado a partir dos parquets), `modelos_locais/` (regenerado por re-projeção C3), `pid.lock` (efêmero), `log.txt` (efêmero). Inclui apenas: `params.json`, `status.json`, `manifesto.json`, parquets de dados (`discursos.parquet`, `votos.parquet`, `proposicoes.parquet`), `relatorio_state.json`, `classificacao_c1_c2.json`.

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/sessao/exportador.py`** implementação completa (substitui stub):
  - `exportar_zip(sessao_dir: Path, destino: Path) -> Path` -- zipa artefatos persistentes, calcula SHA256 do zip, retorna path
  - `importar_zip(zip_path: Path, home: Path, validar: bool = True) -> str` -- extrai pra `home/sessoes/<id>/`, valida hashes contra `manifesto.json` se `validar=True`
  - `class IntegridadeImportadaInvalida(Exception)` -- raised quando hash de artefato não bate com manifesto
  - `_artefatos_persistentes(sessao_dir) -> list[Path]` -- helper que lista o que vai no zip (exclui pid.lock, log.txt, dados.duckdb, modelos_locais)
  - `_validar_manifesto(extraido_dir) -> None` -- recalcula SHA256 de cada artefato e compara
- [ ] **CLI `hemiciclo sessao exportar <id> --destino <path>`**:
  - Default destino: `~/Downloads/<sessao_id>.zip`
  - Mostra tamanho final + lista artefatos incluídos
- [ ] **CLI `hemiciclo sessao importar <zip> [--sem-validar]`**:
  - Extrai pra `~/hemiciclo/sessoes/<id>/`
  - Valida hashes (default `True`)
  - Se `--sem-validar`, pula validação (útil pra debug)
  - Recusa overwrite (sufixo `_<n>` se id colidir)
- [ ] **Botão "Exportar relatório"** em `sessao_detalhe.py` (substitui stub `st.info`):
  - `st.download_button(label="Exportar como zip", data=<bytes>, file_name="<id>.zip", mime="application/zip")`
- [ ] **Página "Importar sessão"** stub em `dashboard/paginas/importar.py`:
  - Form com `st.file_uploader(type=["zip"])`
  - Ao subir: valida + extrai + redireciona pra detalhe
  - Mensagens claras de erro se hash diverge
- [ ] **Testes unit** `tests/unit/test_exportador_real.py` (8 testes):
  - `test_exportar_gera_zip`
  - `test_exportar_exclui_artefatos_efemeros`
  - `test_exportar_inclui_manifesto`
  - `test_importar_extrai_corretamente`
  - `test_importar_valida_hash_ok`
  - `test_importar_recusa_hash_adulterado`
  - `test_importar_sem_validar_aceita_adulterado`
  - `test_importar_id_colidindo_gera_sufixo`
- [ ] **Testes integração** `tests/integracao/test_export_import_e2e.py` (3 testes):
  - `test_round_trip_exportar_importar` -- exporta sessão fixture, importa em outro home, verifica conteúdo idêntico
  - `test_zip_adulterado_falha_import` -- abre zip, modifica byte, verifica falha
  - `test_workflow_cli_exportar_importar`
- [ ] **Sentinela** `test_sentinela.py`:
  - `test_sessao_exportar_help`
  - `test_sessao_importar_help`
- [ ] **`docs/usuario/exportar_compartilhar.md`** documentando fluxo de compartilhamento entre pesquisadores
- [ ] **CHANGELOG.md** entrada `[Unreleased]`

### 3.2 Out-of-scope (explícito)

- **Compactação cross-platform** (gz/xz alternativos) -- zip stdlib basta
- **Cifragem do zip** -- fica em sprint dedicada se demandado
- **Versão de migração** entre formatos -- v1 só por enquanto
- **Sincronização P2P** entre instalações -- futuro
- **Página `dashboard/paginas/exportar.py`** -- stub via download_button na página de detalhe

## 4. Entregas

### 4.1 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/exportador.py` | Substitui stub por implementação real |
| `src/hemiciclo/cli.py` | Subcomandos `sessao exportar` e `sessao importar` |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` | Botão real `st.download_button` |
| `tests/unit/test_sessao_exportador.py` | Atualiza testes da S29 + adiciona novos |
| `tests/unit/test_sentinela.py` | 2 sentinelas |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S35 -> DONE |

### 4.2 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/dashboard/paginas/importar.py` | Página upload zip |
| `tests/integracao/test_export_import_e2e.py` | 3 testes round-trip |
| `docs/usuario/exportar_compartilhar.md` | Guia |

## 5. Implementação detalhada

### 5.1 `exportar_zip` esqueleto

```python
def exportar_zip(sessao_dir: Path, destino: Path) -> Path:
    """Zipa artefatos persistentes. Exclui efêmeros."""
    import zipfile
    artefatos = _artefatos_persistentes(sessao_dir)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in artefatos:
            zf.write(p, p.relative_to(sessao_dir))
    return destino


def _artefatos_persistentes(sessao_dir: Path) -> list[Path]:
    """Inclui params, status, manifesto, parquets, relatorio. Exclui efêmeros."""
    inclusos = {"params.json", "status.json", "manifesto.json",
                "relatorio_state.json", "classificacao_c1_c2.json"}
    artefatos = []
    for p in sessao_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(sessao_dir)
        if rel.name in inclusos:
            artefatos.append(p)
        elif p.suffix == ".parquet" and "modelos_locais" not in rel.parts:
            artefatos.append(p)
    return sorted(artefatos)
```

### 5.2 `importar_zip` com validação

```python
def importar_zip(zip_path: Path, home: Path, *, validar: bool = True) -> str:
    """Extrai zip e valida hashes contra manifesto.json."""
    import json
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("manifesto.json") as f:
            manifesto = json.load(f)
        # Determina id da sessão a partir de manifesto ou nome do zip
        id_sessao = _resolver_id_unico(home, zip_path.stem)
        destino = home / "sessoes" / id_sessao
        destino.mkdir(parents=True, exist_ok=True)
        zf.extractall(destino)
    if validar:
        _validar_manifesto(destino, manifesto)
    return id_sessao


def _validar_manifesto(extraido_dir: Path, manifesto: dict) -> None:
    """Recalcula SHA256 de cada artefato e compara."""
    import hashlib
    for rel_path, hash_esperado in manifesto["artefatos"].items():
        p = extraido_dir / rel_path
        if not p.exists():
            raise IntegridadeImportadaInvalida(f"Artefato ausente: {rel_path}")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        if sha != hash_esperado:
            raise IntegridadeImportadaInvalida(
                f"Hash divergente em {rel_path}: {sha} != {hash_esperado}"
            )
```

### 5.3 Passo a passo

1. Confirmar branch.
2. Reescrever `sessao/exportador.py` com 4 funções + 1 exception.
3. Atualizar testes da S29 (`test_sessao_exportador.py`) + adicionar novos.
4. Adicionar subcomandos CLI `sessao exportar` e `sessao importar`.
5. Substituir botão stub em `sessao_detalhe.py` por `st.download_button`.
6. Criar página `dashboard/paginas/importar.py` (placeholder funcional).
7. Escrever `tests/integracao/test_export_import_e2e.py`.
8. Adicionar sentinelas.
9. Escrever `docs/usuario/exportar_compartilhar.md`.
10. Atualizar `CHANGELOG.md`.
11. Smoke local: rodar seed_dashboard, exportar `_seed_concluida`, importar em /tmp, verificar conteúdo idêntico.
12. `make check` ≥ 90%.
13. Atualizar ORDEM.md.

## 6. Testes (resumo)

- 8 unit (`test_exportador_real.py`)
- 3 integração (`test_export_import_e2e.py`)
- 2 sentinelas
- **Total: 13 testes novos** + 360 herdados = 373 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run python scripts/seed_dashboard.py
$ uv run hemiciclo sessao exportar _seed_concluida --destino /tmp/seed.zip
[sessao] exportada: /tmp/seed.zip (XX KB, 6 artefatos)

$ uv run hemiciclo sessao importar /tmp/seed.zip
[sessao] importada: id=_seed_concluida (validacao OK)
```

**Critério de aceite:**

- [ ] `make check` 373 testes verdes, cobertura ≥ 90%
- [ ] Round-trip exportar/importar preserva hashes
- [ ] Adulteração detectada
- [ ] Botão `st.download_button` funcional na página de detalhe
- [ ] Página `importar.py` aceita upload e valida
- [ ] Mypy/ruff zero, CI verde

## 8. Riscos

| Risco | Mitigação |
|---|---|
| zipfile cross-platform diferenças | stdlib `zipfile` + `ZIP_DEFLATED` é cross-OS |
| Manifesto v0 (sem hashes) de sessões antigas | `--sem-validar` flag pula validação |
| ID de sessão colidindo no destino | Sufixo `_<n>` automático |

## 9. Validação multi-agente

Padrão. Validador atenção a I3 (determinismo round-trip), I4 (skill validacao-visual ativada se diff toca dashboard).

## 10. Próximo passo após DONE

S32 (grafos pyvis) ou S33 (histórico).
