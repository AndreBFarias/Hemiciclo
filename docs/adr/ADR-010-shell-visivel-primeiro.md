# ADR-010 -- Shell visível antes de ETL real (UX-first)

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** ux, infra

## Contexto e problema

Projetos com pipelines pesados costumam adiar a UI até o backend estar maduro. Resultado típico: o usuário vê apenas a tela final, depois de meses sem feedback visual; UX vira afterthought; e o time perde a janela de iterar interface enquanto a complexidade ainda é gerenciável. O Hemiciclo, por ser um projeto cidadão, precisa fazer o caminho inverso: a interface deve estar minimamente navegável desde o primeiro dia, com estados vazios honestos, mesmo antes de existir um único byte de dado real coletado.

## Drivers de decisão

- Iterar UX cedo, com pouco custo de mudança
- Dar tração visual ao projeto desde o sprint 1 da migração
- Permitir que cidadãos não-técnicos vejam para onde o projeto vai
- Forçar contratos claros entre frontend e backend

## Opções consideradas

### Opção A -- Backend primeiro, UI no fim

- Prós: arquitetura consolidada antes da UI.
- Contras: contrato de UI vira refatoração tarde; usuário não vê evolução; risco de UI "engenheirada" ao invés de "experiencial".

### Opção B -- Shell visível primeiro (Streamlit com placeholders)

- Prós: jornada do usuário (J1, J2 do plano) testável desde S23; estados vazios documentados; contratos forçados cedo.
- Contras: trabalho aparente é maior no início; placeholders precisam ser claros para não enganar.

## Decisão

Escolhida: **Opção B**.

Justificativa: o manifesto do projeto é cidadão -- o produto é a UX, não a stack. Shell visível é o gancho: telas mostram estado vazio honesto ("nenhuma sessão ainda"), botão de criar, intro narrativo. À medida que sprints subsequentes implementam coleta, ETL e modelagem, a UI ganha conteúdo real sem reescrita estrutural.

## Consequências

**Positivas:**

- S23 já entrega valor visível ao usuário.
- Iteração de UX paralela à do backend.
- Estados vazios viram primeira ordem (ADR de UX -- seção 10.4 do plano).

**Negativas / custos assumidos:**

- Risco de placeholder virar permanente -- mitigado por `# TODO(SXX)` rastreável (I5 do BRIEF).
- Cuidado para placeholders não passarem ilusão de funcionalidade que não existe.

## Pendências / follow-ups

- [ ] S23 implementa shell visível.
- [ ] S36 garante paridade Windows.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seções 10.1 e 10.4)
- Sprints relacionadas: S22 (registro), S23, S36
