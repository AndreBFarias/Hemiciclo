# Fontes auto-hospedadas (Inter + JetBrains Mono)

Diretório com TTFs versionados do projeto. **Nunca consulta CDN externa em runtime.**

## Conteúdo (6 TTFs, ~2.2 MB total)

| Arquivo | Família | Peso | Tamanho |
|---|---|---|---|
| `Inter-Regular.ttf` | Inter | 400 | 397 KiB |
| `Inter-Medium.ttf` | Inter | 500 | 402 KiB |
| `Inter-SemiBold.ttf` | Inter | 600 | 404 KiB |
| `Inter-Bold.ttf` | Inter | 700 | 405 KiB |
| `JetBrainsMono-Regular.ttf` | JetBrains Mono | 400 | 267 KiB |
| `JetBrainsMono-Bold.ttf` | JetBrains Mono | 700 | 271 KiB |

## Origens oficiais

- **Inter v4.0** -- https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip (extraído de `extras/ttf/`)
- **JetBrains Mono v2.304** -- https://www.jetbrains.com/lp/mono/

## Licença

Ambas as fontes são distribuídas sob **SIL Open Font License Version 1.1** -- compatível com GPL v3 do Hemiciclo, permite redistribuição + modificação + uso comercial. Texto completo em `./LICENSE`.

## Por que auto-hospedar

Decisão registrada em [ADR-021](../../../../docs/adr/ADR-021-fontes-auto-hospedadas.md):

1. **I1 do projeto** ("tudo local") proíbe `@import url('https://fonts.googleapis.com/...')` -- isso sangraria IP do usuário pra Google a cada visita.
2. **Estética consistente** entre máquinas (Linux Ubuntu, macOS, Windows) sem depender de fonte do sistema.
3. **Manifesto político**: produto cidadão sem rastreio de terceiros.

## Como atualizar

```bash
uv run python scripts/baixar_fontes.py
```

O script baixa de origem oficial, verifica SHA256 contra hashes embedados e substitui apenas se íntegro.

## SHA256 das fontes atuais

Ver `scripts/baixar_fontes.py:HASHES_ESPERADOS`.
