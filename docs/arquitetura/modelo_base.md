# Modelo base v1 (S28)

> Camada 3 do classificador multicamada (D11/ADR-011): embeddings semânticos
> via BAAI/bge-m3 + redução dimensional via PCA. Treinado uma única vez sobre
> amostra estratificada do DuckDB unificado e persistido com validação de
> integridade SHA256.

## Por que bge-m3 (D9 / ADR-009)

`BAAI/bge-m3` é estado-da-arte multilíngue 2024-25 para embeddings de texto.
Três motivos para escolha:

1. **Multilíngue forte em PT-BR** -- treinado em 100+ idiomas com performance
   competitiva no português.
2. **Multi-funcional numa única call** -- entrega vetor dense (1024 dim),
   sparse e ColBERT na mesma chamada `encode`. Em S28 usamos só o dense; sparse
   fica disponível para S30+.
3. **Tudo local (I1)** -- modelo baixa via huggingface_hub para
   `~/hemiciclo/modelos/bge-m3/` e roda offline depois.

Preço: ~2GB de pesos. Mitigamos isso com **lazy import** -- o boot do CLI não
carrega o modelo (~200ms vs ~5s).

## Por que PCA com random_state fixo (D8 + I3)

D8 do plano R2 estabelece **modelo base global + ajuste fino local**. Treinamos
uma vez sobre amostra ampla; cada Sessão de Pesquisa pode `transform` o seu
recorte nos eixos induzidos pelo base (nunca `fit_transform`). Garante que
"Joaquim no eixo 1" significa a mesma coisa em qualquer pesquisa.

Determinismo (I3 do BRIEF) é triplicado:

1. **Amostragem DuckDB** com `USING SAMPLE reservoir(N ROWS) REPEATABLE (42)`
   -- sintaxe DuckDB 1.x para reservoir sampling determinístico.
2. **PCA** com `random_state=Configuracao().random_state` (default 42).
3. **`hash_amostra`** registra SHA256 dos `hash_conteudo` que entraram na
   amostra; permite auditar reprodutibilidade pós-treino.

## Arquivos persistidos

```
~/hemiciclo/modelos/
  base_v1.joblib        # binário serializado via joblib (PCA + metadados)
  base_v1.meta.json     # manifesto JSON auditável
  bge-m3/               # cache do FlagEmbedding (~2GB)
```

`base_v1.meta.json` contém:

```json
{
  "versao": "1",
  "treinado_em": "2026-04-28T12:00:00+00:00",
  "hash_sha256": "<64 chars hex do .joblib>",
  "hash_amostra": "<64 chars hex auditável>",
  "n_componentes": 50,
  "feature_names": ["pc_0", "pc_1", ..., "pc_49"],
  "salvo_em": "2026-04-28T12:00:01+00:00"
}
```

## Validação de integridade SHA256

Toda chamada de `carregar_modelo_base(dir)` calcula o SHA256 do `.joblib` e
compara com `meta.json:hash_sha256`. Divergência -> `IntegridadeViolada`.
Versão diferente de "1" -> `IntegridadeViolada`. Nunca carregamos artefato
corrompido silenciosamente.

Cobertura testada: `test_carregar_arquivo_corrompido_falha_integridade` injeta
1 byte adicional no `.joblib` após salvar e verifica que o erro é levantado.

## Por que mock em CI (artefato 2GB, indeterminismo de download)

**Zero teste em CI ou make check pode baixar bge-m3.** Razões:

- 2GB de download lenta/falha em runners CI (timeout, rede do GitHub).
- Indeterminismo: huggingface pode atualizar artefato; testes ficariam frágeis.
- Boot lento: cada teste com modelo real demoraria ~5s só para carregar.

Estratégia: todos os testes mockam `FlagEmbedding.BGEM3FlagModel` via
`unittest.mock.patch`. Os 26 testes da S28 rodam em ~5s no laptop e na CI.

## Como rodar smoke local (download manual + treino)

Requer ~2GB livres em disco e ~10min de download na primeira vez.

```bash
# 1) Pré-baixa bge-m3 (uma vez):
hemiciclo modelo base baixar

# 2) Garante DuckDB com discursos:
hemiciclo db init
hemiciclo coletar camara --legislatura 57 --tipos discursos --max-itens 1000
hemiciclo db consolidar --parquets ~/hemiciclo/cache/camara

# 3) Treina o modelo base (smoke pequeno):
hemiciclo modelo base treinar --n-amostra 500 --n-componentes 20

# 4) Verifica integridade:
hemiciclo modelo base carregar
hemiciclo modelo base info
```

Em produção, `--n-amostra 30000` e `--n-componentes 50` (defaults) demoram
~30min em CPU comum.

## Arquitetura modular

```
src/hemiciclo/modelos/
  embeddings.py             # WrapperEmbeddings + embeddings_disponivel
  base.py                   # ModeloBaseV1 + amostragem + treinar_base_v1
  persistencia_modelo.py    # salvar/carregar + IntegridadeViolada + SHA256
  projecao.py               # projetar_em_base (transform; ajuste fino em S30)
  topicos_induzidos.py      # WrapperBERTopic stub (treino real em S30/S31)
```

## Próximos passos

- **S30**: pipeline integrado coleta → ETL → C1+C2+C3 → projeção do recorte da
  sessão no espaço induzido + ajuste local (`fit_partial` sobre o recorte) +
  persistência da sessão.
- **S31**: dashboard mostrando assinatura multidimensional (7 eixos induzidos)
  + word clouds por cluster retórico (BERTopic real).
- **S34b**: camada 4 LLM opcional (ollama + cache por hash + flag de sessão).
