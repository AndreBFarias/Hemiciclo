# Sprint S38.8 -- Word cloud de palavras-chave (Opção A) + acentuação

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Status:** READY
**Esforço:** M (3-4h -- subiu de P por causa da Opção A consolidada)
**Branch:** feature/s38-8-nomes-e-labels
**Depende de:** S38.5 (tema; CSS de labels já mergeado em `6dbdc34`)

---

## 1. Objetivo

Tratar duas pendências de UX/proteção reveladas no smoke real:

1. **Word cloud com nomes próprios de parlamentares** -- usuário reportou que "nome dos caras não deveriam estar aqui". Substituir nuvem-de-nomes por nuvem-de-palavras-chave-de-ementas das proposições associadas (Opção A, decidida).
2. **Acentuação periférica** -- varrer `dashboard/` em busca de strings sem acento em texto visível.

Labels do form (`stForm`) **já estão tratados** pela S38.5 (`style.css` linhas 226-246). Esta sprint apenas **confirma** e adiciona regressão.

## 2. Contexto

### 2.1. Estado atual da word cloud (confirmado via leitura)

**Arquivo:** `src/hemiciclo/dashboard/widgets/word_cloud.py` (131L)
- Já usa `wordcloud.WordCloud` com `STOP_PT_BR` curado, `random_state=42` (I3), paleta institucional.
- Função pública: `renderizar_word_cloud(textos: list[str], titulo: str, max_palavras: int = 100, cor_dominante: str | None = None)`.
- Recebe **lista de strings genérica** -- a função em si está agnóstica. O problema é o **call site**.

**Call site:** `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` linhas 158-173:
```python
textos_a = [str(p.get("nome", "")) for p in top_a_favor]
word_cloud.renderizar_word_cloud(textos_a, titulo="Nuvem de quem vota a favor", ...)
textos_c = [str(p.get("nome", "")) for p in top_contra]
word_cloud.renderizar_word_cloud(textos_c, titulo="Nuvem de quem vota contra", ...)
```

Está passando **nome do parlamentar** como corpus. É a fonte do bug ético.

### 2.2. Origem das ementas (confirmado)

- **`relatorio_state.json`** tem `top_a_favor` e `top_contra` (listas de dicts com `nome`, `partido`, `uf`, `proporcao_sim`, etc), mas **NÃO** ementas das proposições.
- **`cache_parquet`** (path em `classificacao_c1_c2.json -> cache_parquet`) tem `id, casa, sigla, numero, ano, ementa, tema_oficial, ...` -- saída de `proposicoes_relevantes` em `modelos/classificador_c1.py`.
- O parquet contém **ementas de todas as proposições do tópico**, sem distinção por parlamentar.

**Decisão de design:** a Opção A vai usar ementas do `cache_parquet` agregadas. Não há mapeamento parlamentar→ementas-que-ele-votou-sim na sessão atual. Portanto:

- **Nuvem "a-favor"**: TF-IDF (ou contagem) sobre **todas as ementas do `cache_parquet`** (vocabulário do tópico inteiro). Cor verde-folha. Caption: "Vocabulário das proposições do tópico".
- **Nuvem "contra"**: idem, **mesmo corpus**. Diferenciar só pela cor/caption parece redundante. Alternativa: dropar uma das duas e renomear seção para "Vocabulário do tópico" (uma nuvem só).

**Recomendação:** **uma única word cloud** com vocabulário do `cache_parquet`, cor azul institucional, caption "Vocabulário das proposições analisadas". Remover o `st.columns(2)` em `sessao_detalhe.py` linhas 159-173. Decisão final: executor confirma com usuário se ambígua.

### 2.3. Estado dos seeds (confirmado)

- `_seed_concluida` é gerado por `scripts/seed_dashboard.py:_criar_sessao_concluida`.
- `cache_parquet` referenciado em `classificacao_c1_c2.json` aponta para `cache_seed.parquet` -- **mas o arquivo não é criado** pelo seed. Linhas 141-142:
  ```python
  "cache_parquet": str(pasta / "cache_seed.parquet"),
  ```
  Path string sem write_parquet.
- **Implicação:** Opção A precisa que o seed **escreva um parquet com ementas plausíveis** (~10-20 ementas reais sobre aborto). Caso contrário, a página demo mostra `st.info("Sem dados para a nuvem...")`.

### 2.4. CSS de labels do form (confirmado já mergeado)

`src/hemiciclo/dashboard/style.css` linhas 226-246:
```css
[data-testid="stForm"] label,
[data-testid="stForm"] label p,
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stMultiSelect label,
.stDateInput label,
.stNumberInput label,
.stRadio label,
.stCheckbox label {
    color: var(--azul-hemiciclo) !important;
    font-weight: 600 !important;
}
```

Já cobre todos os widgets do form de `nova_pesquisa.py`. **S38.8 não precisa modificar CSS** -- só **confirmar via smoke real** que está pintado e adicionar nota de regressão se desejado.

### 2.5. TF-IDF library (confirmado)

`pyproject.toml:36`: `"scikit-learn>=1.4"`. `TfidfVectorizer` já é usado em `modelos/classificador_c2.py:tfidf_relevancia`. Pode ser reusado.

## 3. Escopo

### 3.1 In-scope

#### 3.1.1. Word cloud -- Opção A (decidida)

**Arquivos a modificar:**
- `src/hemiciclo/dashboard/widgets/word_cloud.py` -- adicionar função `extrair_palavras_chave_de_ementas(ementas: list[str], top_n: int = 50, min_df: int = 2) -> list[tuple[str, float]]` que aplica `TfidfVectorizer` (com `STOP_PT_BR` + stopwords adicionais sklearn) e retorna `[(termo, peso), ...]` ordenado.
- `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` (linhas 158-173) -- ler `cache_parquet` da sessão (via `relatorio.get("cache_parquet")` ou `manifesto`), extrair coluna `ementa`, gerar palavras-chave, renderizar **uma única** word cloud azul. Manter linha `st.markdown("### Vocabulário dos posicionamentos")` mas atualizar texto para "### Vocabulário das proposições analisadas".
- `scripts/seed_dashboard.py` -- escrever `cache_seed.parquet` com ~15 ementas plausíveis sobre aborto (texto curto, real-like). Schema mínimo: `id, casa, sigla, numero, ano, ementa, tema_oficial`. Determinismo via lista hard-coded.

**Arquivos a criar:**
- `tests/unit/test_word_cloud_palavras_chave.py` -- testar que `extrair_palavras_chave_de_ementas`:
  - Retorna lista vazia para input vazio.
  - Filtra stopwords PT-BR (sem "para", "que", "não").
  - Não retorna nomes próprios capitalizados quando ausentes do corpus.
  - É determinística (duas chamadas com mesma entrada → mesma saída ordenada).

**Não tocar:**
- `widgets/word_cloud.py:renderizar_word_cloud` -- API pública estável; nova função adiciona, não substitui.
- `modelos/classificador.py` ou `etl/consolidador.py` -- caminho de dados intacto.

#### 3.1.2. Acentuação periférica

Varrer com:
```bash
~/.config/zsh/scripts/validar-acentuacao.py --paths src/hemiciclo/dashboard/
```

Confirmado existe em `/home/andrefarias/.config/zsh/scripts/validar-acentuacao.py`.

Corrigir todas as strings visíveis em `st.write`, `st.markdown`, `st.button`, label, caption, info, error, warning. **Não corrigir** identificadores Python (`def topico`, var `posicao`, etc), apenas valores de string.

Termos comuns a auditar: `nao`, `topico`, `sessao`, `proposicao`, `posicao`, `dependencia`, `analise`, `pesquisa`, `area`, `parametros`, `criterios`, `historico`.

#### 3.1.3. Confirmação do CSS de labels

Adicionar à seção §6 Proof-of-work: screenshot da página `Nova pesquisa` mostrando todos os labels (Casas, UFs, Período, Camadas, Legislaturas, Partidos, etc) em `var(--azul-hemiciclo)` semibold. Sem mudança de código.

### 3.2 Out-of-scope

- Anonimização das tabelas Top a-favor/contra (são listas de pessoas públicas com voto público; não é word cloud).
- Mapeamento ementa→parlamentar (exigiria join `votos × proposicoes` por parlamentar, fora do esforço P/M).
- Toggle "ver nomes / ver palavras-chave" (Opção B descartada).
- BERTopic (incremento futuro -- TF-IDF já é suficiente para o sinal visual).

## 4. Acceptance criteria

1. `widgets/word_cloud.py` ganhou `extrair_palavras_chave_de_ementas` testada e determinística.
2. `paginas/sessao_detalhe.py` deixou de passar `nome` ao word cloud; lê `cache_parquet` e extrai ementas.
3. `scripts/seed_dashboard.py` escreve `cache_seed.parquet` com ementas reais-like sobre aborto. Suite `test_dashboard_sessao_e2e.py` continua passando.
4. Smoke real: página de `_seed_concluida` mostra word cloud com termos como "interrupção", "gestação", "feto", "aborto" -- **zero nomes próprios**.
5. `validar-acentuacao.py --paths src/hemiciclo/dashboard/` retorna **zero violações em strings visíveis**.
6. Smoke real: página `Nova pesquisa` mostra labels em azul semibold (regressão visual da S38.5).
7. Suite passa: `uv run pytest -q` (FAIL_AFTER ≤ FAIL_BEFORE; cobertura ≥ 90%).

## 5. Invariantes a preservar

- **I3 (determinismo):** TF-IDF precisa ordenação estável. Usar `vocabulary` ordenado lexicograficamente ou `random_state` quando aplicável.
- **Boot do dashboard:** import lazy do `wordcloud` (já feito) e do `sklearn` (já lazy via `from sklearn... import` dentro da função). Não importar topo do módulo.
- **API pública estável:** `renderizar_word_cloud(textos, titulo, ...)` continua aceitando `list[str]`. A migração é no call site, não na assinatura.
- **D11 (decisão fundadora):** word cloud é **complemento visual**, não fonte primária. Caption explícita "vocabulário derivado de TF-IDF das ementas" remove pretensão de neutralidade absoluta.
- **Sessão como cidadão de primeira classe:** `cache_parquet` é parte da sessão; ler via `relatorio.get("cache_parquet")` mantém o contrato.

## 6. Plano de implementação

1. **Branch:** `git checkout -b feature/s38-8-nomes-e-labels` a partir de `feature/v2-1-1-planning-revisao-ui-ux`.
2. **Função pura primeiro:** implementar `extrair_palavras_chave_de_ementas` em `word_cloud.py`. Testes unitários antes da integração.
3. **Atualizar seed:** escrever `cache_seed.parquet` em `scripts/seed_dashboard.py:_criar_sessao_concluida`. Usar `polars.DataFrame(...).write_parquet(...)`. Lista de 15 ementas hard-coded.
4. **Atualizar call site:** `paginas/sessao_detalhe.py:_renderizar_concluida` -- ler parquet, extrair ementas, gerar palavras-chave, chamar `renderizar_word_cloud` com **uma única** nuvem azul (decisão recomendada). Se executor preferir manter duas, justificar via cor/legenda mas mesmo corpus.
5. **Acentuação:** rodar varredor; corrigir cada string visível; commit separado para auditoria.
6. **Confirmação CSS:** apenas smoke + screenshot, sem mudança.
7. **PR:** branch → `feature/v2-1-1-planning-revisao-ui-ux` (não main).

## 7. Proof-of-work

```bash
# Acentuação
~/.config/zsh/scripts/validar-acentuacao.py --paths src/hemiciclo/dashboard/

# Unit
uv run pytest tests/unit/test_word_cloud_palavras_chave.py -v
uv run pytest tests/unit/test_dashboard_widgets.py -v

# Integração
uv run pytest tests/integracao/test_dashboard_sessao_e2e.py -v

# Suite completa
uv run pytest -q

# Smoke real (skill validacao-visual)
# 1. python -m hemiciclo.scripts.seed_dashboard
# 2. uv run streamlit run src/hemiciclo/dashboard/app.py
# 3. Navegar para "Histórico" -> "_seed_concluida" -> seção "Vocabulário"
# 4. Capturar PNG, sha256, anexar ao PR
# 5. Navegar para "Nova pesquisa", capturar labels em azul, anexar PNG
```

Critério de aceite executável:
- [ ] `extrair_palavras_chave_de_ementas` existe, é determinística, testada
- [ ] `_seed_concluida` mostra nuvem com palavras-chave (não nomes) em smoke real
- [ ] `cache_seed.parquet` é gravado pelo `scripts/seed_dashboard.py`
- [ ] Labels do form em `Nova pesquisa` visíveis em azul semibold (smoke real PNG)
- [ ] `validar-acentuacao.py` retorna zero violações em strings visíveis
- [ ] Suite passa, cobertura ≥ 90%

## 8. Riscos e não-objetivos

- **Risco 1: TF-IDF gera tokens sem sentido em corpus pequeno (15 ementas).** Mitigação: `min_df=2`, `max_features=50`, `ngram_range=(1, 2)` para capturar bigramas como "interrupção gestação".
- **Risco 2: parquet vazio em sessões reais sem proposições.** Mitigação: fallback para `st.info("Sem ementas suficientes para vocabulário")`.
- **Risco 3: ementas em maiúsculas viram tokens próprios.** Mitigação: `lowercase=True` no `TfidfVectorizer` (default).
- **Não-objetivo:** mapeamento ementa→parlamentar específico. Se virar requisito, abrir sprint nova.

## 9. Referências

- Spec original (este arquivo, versão pré-revisão) -- mantido em git
- S38.5 (CSS labels): commit `6dbdc34`
- S38.7 (top a-favor/contra): test_dashboard_widgets.py:272
- `modelos/classificador_c2.py` -- precedente de uso de `TfidfVectorizer` no projeto
- `scripts/seed_dashboard.py` -- estrutura de `_seed_concluida`

## 10. Próximo passo após DONE

S23.4 (install --com-modelo).
