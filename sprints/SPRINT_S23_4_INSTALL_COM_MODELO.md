# Sprint S23.4 -- install.sh / install.bat ganham flag --com-modelo (baixa bge-m3)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Status:** READY
**Esforço:** P (1h)
**Branch:** feature/s23-4-install-com-modelo
**Depende de:** S28 (DONE)

---

## 1. Objetivo

Adicionar flag opcional `--com-modelo` (Linux/macOS) e `--com-modelo` (Windows) aos scripts de instalação que baixam o modelo `BAAI/bge-m3` (~2GB) automaticamente, eliminando a necessidade do usuário baixar manualmente.

## 2. Contexto

Sem o `bge-m3`, a camada C3 (embeddings semânticos) cai em skip silencioso no `pipeline_real`, gerando relatórios incompletos. Hoje o usuário precisa rodar manualmente:
```python
from FlagEmbedding import BGEM3FlagModel
m = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
```
ou aguardar download na primeira sessão real -- experiência ruim.

## 3. Escopo

### 3.1 In-scope

**3.1.1. `install.sh`:**
Reconhecer `--com-modelo` ou `--com-bge`:
```bash
if [[ "${@}" =~ "--com-modelo" ]]; then
    echo "[Hemiciclo] Baixando bge-m3 (~2GB, pode levar 5-15min)..."
    uv run python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)"
fi
```

Mensagem clara sobre tamanho e tempo. Falha graciosa se sem internet.

**3.1.2. `install.bat`:**
Idem com sintaxe CMD compatível.

**3.1.3. `docs/usuario/instalacao.md`:**
Documentar:
- Default: instalação rápida sem modelo (camada C3 skipped silenciosamente)
- `--com-modelo`: instalação completa, cidadão pode rodar pipeline_real ponta-a-ponta
- Como baixar manualmente depois: `uv run python -c "..."`

**3.1.4. README.md:**
Atualizar bloco "Instalação rápida" com nota: "Para análise semântica completa, adicione `--com-modelo` (~2GB extras)."

### 3.2 Out-of-scope
- Download automático em primeira sessão (já é comportamento atual de `FlagEmbedding`)
- Quantização customizada (fica para sprint dedicada)
- Cache compartilhado entre sessões (já é comportamento Hugging Face padrão)

## 4. Proof-of-work

```bash
# Smoke real:
./install.sh --com-modelo
ls -la ~/.cache/huggingface/hub/models--BAAI--bge-m3/
uv run python -c "from FlagEmbedding import BGEM3FlagModel; m = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); print('OK')"
```

Critério de aceite:
- [ ] `install.sh --com-modelo` baixa bge-m3 sem erro
- [ ] `install.bat --com-modelo` análogo
- [ ] Sem flag, comportamento atual preservado (sem regressão)
- [ ] Documentação clara do trade-off

## 5. Riscos

- 2GB de download em redes lentas: mostrar barra de progresso (FlagEmbedding já faz via tqdm).
- Hugging Face Hub fora do ar: try/except com mensagem amigável.

## 6. Próximo passo após DONE

S38.4 (iniciar pesquisa real) torna pipeline_real plenamente funcional para usuários que rodaram `--com-modelo`.
