# ADR-020 -- Logs estruturados via Loguru, arquivo rotacionado por sessão

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** observabilidade, qualidade

## Contexto e problema

Cada Sessão de Pesquisa (ADR-007) executa um pipeline de coleta + ETL +
classificação + modelagem que pode rodar por minutos a horas em subprocess
detached (ADR-013). Quando algo falha, ou quando o usuário cidadão quer
entender o que aconteceu, precisa de **log estruturado, legível, rotacionado**
por sessão -- não um único `stderr` global misturando 5 sessões.

`print()` é proibido por I4 do BRIEF. `logging.basicConfig` é boilerplate
imenso. Loguru oferece API ergonômica + sinks múltiplos + rotação automática.

## Drivers de decisão

- Log por sessão isolado em `<sessao_dir>/log.txt`.
- Rotação automática por tamanho ou tempo.
- API ergonômica (Loguru: `from loguru import logger`).
- Determinismo de formato (timestamp ISO 8601 UTC).
- Compatibilidade com captura em testes (`caplog`).

## Opções consideradas

### Opção A -- logging stdlib

- Prós: zero dep externa.
- Contras: boilerplate, rotação via `RotatingFileHandler` chato, formato
  fragmentado.

### Opção B -- structlog

- Prós: estruturação rica.
- Contras: configuração extensa, curva de aprendizado.

### Opção C -- Loguru

- Prós: API ergonômica (`logger.info("...")`), sinks múltiplos, rotação
  com keyword args (`rotation="10 MB"`), captura em pytest direta, formato
  consistente.
- Contras: dep externa nova.

## Decisão

Escolhida: **Opção C**.

- Sink stdout em modo `level=INFO` para o terminal do dev.
- Sink `<sessao_dir>/log.txt` com `rotation="10 MB"`, `retention="7 days"`,
  `enqueue=True` (thread-safe), `encoding="utf-8"` (cross-OS).
- Formato: `<green>{time:YYYY-MM-DDTHH:mm:ss!UTC}</green> | {level: <8} | {name}:{function}:{line} - {message}`.
- `logger.add(...)` no início do worker, `logger.remove(...)` no fim.

## Consequências

**Positivas:**

- Cada sessão tem log próprio, auditável, sem mistura.
- Rotação automática evita disco cheio em sessões longas.
- Formato consistente facilita parsing futuro (jq, awk).

**Negativas / custos assumidos:**

- Dependência runtime nova (`loguru>=0.7`).
- Captura em pytest exige fixture específica (documentada).

## Pendências / follow-ups

- [x] S22 estabelece configuração base.
- [x] S29 integra logger por sessão no worker.

## Links

- Sprint relacionada: S22, S29
- Invariante: I4 do `VALIDATOR_BRIEF.md`
- Documentação: https://loguru.readthedocs.io/
