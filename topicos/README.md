# Tópicos do Hemiciclo

Cada arquivo `<slug>.yaml` neste diretório descreve uma **pauta política** classificável pelo motor multicamada (C1+C2 nesta versão; C3+C4 nas próximas).

## Formato

A estrutura é validada pelo JSON Schema em `_schema.yaml` e por `scripts/validar_topicos.py`. Os campos:

- `nome` (obrigatório, ASCII snake_case): identificador. Bate com o nome do arquivo.
- `versao` (obrigatório, inteiro >= 1): versão do YAML. Incrementa a cada edição.
- `mantenedor` (opcional): quem cura este tópico.
- `descricao_curta` (obrigatório, 10-280 chars): resumo PT-BR.
- `keywords` (obrigatório, >= 1, único): termos literais para match em ementa/discurso (case-insensitive).
- `regex` (obrigatório, >= 1): padrões regex Python. Use prefixo `(?i)` para ignorar caixa.
- `categorias_oficiais_camara` (opcional): temas oficiais da Câmara (campo `tema_oficial`).
- `categorias_oficiais_senado` (opcional): temas oficiais do Senado.
- `proposicoes_seed` (opcional): proposições conhecidas como exemplos canônicos. Cada item exige `sigla`, `numero`, `ano`, `casa` (`camara`|`senado`) e aceita `posicao_implicita` (`a_favor`|`contra`|`neutro`).
- `exclusoes` (opcional): regex que **desclassificam** falsos positivos. Cada item exige `regex` e aceita `motivo`.
- `embeddings_seed` (opcional, S28+): frases-âncora para C3.
- `limiar_similaridade` (opcional, 0.0-1.0, S28+): limiar de cosseno para C3.

## Como contribuir um tópico novo

1. Fork do repositório.
2. Crie `topicos/<slug>.yaml` baseado em algum dos seeds (`aborto.yaml`, `porte_armas.yaml`, `marco_temporal.yaml`).
3. Rode `python scripts/validar_topicos.py` localmente -- precisa imprimir `Zero erros.`.
4. Pre-commit hook `validar-topicos` roda automaticamente em `git commit`.
5. Abra um PR descrevendo o tópico, fontes consultadas e proposições-âncora.

## Boas práticas

- **Keywords sem acento** quando possível (a comparação `ILIKE` em DuckDB é case-insensitive mas não faz fold de acento). Para matches acentuados, use `regex` com `[áa]`, `[éê]`, etc.
- **Regex Python** -- o validador chama `re.compile`; padrão inválido quebra antes de aceitar o YAML.
- **Exclusões são essenciais** para evitar falsos positivos óbvios (ex: "aborto espontâneo" não é pauta política; "Marco Civil" não é marco temporal indígena).
- **`proposicoes_seed`** ajuda a auditar a recall do classificador: rode `hemiciclo classificar --topico <slug>.yaml` e verifique se as proposições-âncora aparecem entre as relevantes.

## Referência

- Plano R2 §3.6 -- formato canônico do tópico.
- ADR-003 -- decisão D3, mapeamento tópico -> PL híbrido.
- ADR-011 -- decisão D11, classificação multicamada em cascata.
