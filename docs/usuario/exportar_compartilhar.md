# Exportar e compartilhar uma sessão

A Sessão de Pesquisa do Hemiciclo é o cidadão de primeira classe do produto
(D7 / ADR-007): tudo que importa de uma análise -- parâmetros, status, dados
processados, relatório, manifesto de integridade -- vive em
`~/hemiciclo/sessoes/<id>/`. A partir da S35 essa pasta é portável: você
pode embrulhá-la em um zip, enviar pra outro pesquisador e ele abre a
mesma análise no dashboard dele, com verificação de integridade automática.

## Jornada típica

A pesquisadora roda uma busca completa sobre `aborto` na 57ª
legislatura. O pipeline real (S30) coleta Câmara e Senado, consolida em
DuckDB, classifica nas camadas C1+C2 e produz um relatório. A pasta da
sessão fica em `~/hemiciclo/sessoes/aborto_57_abc123/`.

Ela quer enviar a análise para um colega B. Dois caminhos:

### Pelo dashboard

1. Abre a página de detalhe da sessão.
2. Clica em **Exportar zip** (botão no topo direito).
3. O navegador baixa `aborto_57_abc123.zip`.
4. Envia o zip por email, USB, drive compartilhado, etc.

### Pelo CLI

```bash
hemiciclo sessao exportar aborto_57_abc123 --destino ~/Documentos/aborto.zip
```

Saída esperada:

```
sessao exportar: zip=/home/.../aborto.zip tamanho=87.3KB artefatos=7
```

## O que vai e o que não vai no zip

**Vai:**

- `params.json`, `status.json`, `manifesto.json`
- `relatorio_state.json`, `classificacao_c1_c2.json`, `c3_status.json`
- Parquets de coleta (`raw/proposicoes.parquet`, `raw/votos.parquet`, etc.)

**Não vai (são reconstruídos no destino):**

- `dados.duckdb` (regenerado por `hemiciclo db consolidar`)
- `modelos_locais/` (regenerado por re-projeção C3)
- `pid.lock` (efêmero do subprocess)
- `log.txt` (efêmero do subprocess)

Resultado: um zip típico tem 50-200 KB em vez dos centenas de MB da pasta
completa.

## Importar do outro lado

O colega B recebe o zip e tem duas opções equivalentes:

### Pelo dashboard

1. Abre a página `Importar sessão` (rota interna; pode ser linkada em
   `Pesquisas`).
2. Faz upload do `.zip` pelo `st.file_uploader`.
3. Clica em **Importar**.
4. O dashboard valida hashes via `manifesto.json`, extrai a sessão pra
   `~/hemiciclo/sessoes/<id>/` e oferece um botão `Abrir relatório`.

### Pelo CLI

```bash
hemiciclo sessao importar ~/Downloads/aborto.zip
```

Saída em sucesso:

```
sessao importar: sessao=aborto_57_abc123 validacao=OK
```

## Verificação de integridade

Toda exportação carrega um `manifesto.json` com SHA256 truncado em 16
chars de cada artefato (precedente S24/S25/S26/S30). Na importação o
Hemiciclo recalcula esses hashes e compara. Se algum byte foi alterado
no caminho, a importação falha com mensagem clara:

```
integridade violada: Hash divergente em raw/proposicoes.parquet:
  calculado=a3f9... esperado=d18b...
```

Para pular essa verificação (sessões anteriores ao manifesto, ou
debug), use:

```bash
hemiciclo sessao importar arquivo.zip --sem-validar
```

No dashboard há um checkbox equivalente.

## Conflito de id

Se o id da sessão importada já existe em `~/hemiciclo/sessoes/`, o
Hemiciclo **nunca sobrescreve**. Sufixa automaticamente:

- Primeira importação: `aborto_57_abc123`
- Segunda: `aborto_57_abc123_2`
- Terceira: `aborto_57_abc123_3`

Sem limite teórico, sem precisar deletar nada.

## Filosofia

Esta é uma ferramenta de jornalista, ativista e pesquisador
independente. O zip é o seu samizdat de dados públicos -- portável,
auditável, soberano. Você não depende de nenhum servidor central nem
de nenhuma rede social pra circular sua análise: copia o arquivo,
manda pra quem importar.
