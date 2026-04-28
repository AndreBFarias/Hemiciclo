# ADR-006 -- Arquitetura 100% local, sem servidor central

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** infra, soberania, manifesto

## Contexto e problema

Plataformas de inteligência política normalmente operam como SaaS centralizado: o usuário envia consultas, o servidor processa, devolve resultado. Isso implica logs centralizados de quem está investigando o quê -- precisamente o tipo de rastreio que o manifesto do Hemiciclo rejeita explicitamente. Há também opção de operação distribuída (P2P) e operação 100% local. Cada uma tem implicações distintas para soberania, custo e UX.

## Drivers de decisão

- Soberania total dos dados do cidadão investigador
- Zero infraestrutura central (zero custo operacional)
- Resistência a takedown ou pressão jurídica/política
- Reprodutibilidade científica

## Opções consideradas

### Opção A -- SaaS centralizado

- Prós: setup zero para usuário; modelos pesados rodam no servidor.
- Contras: rastreio total das pesquisas; ponto único de falha; custo permanente; viola manifesto.

### Opção B -- P2P distribuído

- Prós: sem servidor central; redundância.
- Contras: complexidade altíssima; vetores de ataque novos; UX pesado para usuário comum.

### Opção C -- 100% local na máquina do usuário

- Prós: zero rastreio; zero custo de infra; resistente a takedown; reprodutível; alinha com manifesto.
- Contras: usuário precisa de hardware razoável; downloads iniciais grandes (modelos); responsabilidade de versionamento dos modelos descentralizada (resolvida em ADR-008).

## Decisão

Escolhida: **Opção C**.

Justificativa: o projeto é cidadão antes de ser tecnológico. A arquitetura é função do manifesto, não o inverso. Custo de hardware é aceitável dado que o público alvo (pesquisadores, jornalistas, ativistas) já tem máquinas capazes; download inicial é one-time; modelos rodam em CPU se necessário.

## Consequências

**Positivas:**

- Zero log de pesquisa em qualquer servidor.
- Custo operacional zero -- projeto sustentável indefinidamente.
- Sessão de Pesquisa (ADR-007) vira artefato exportável e arquivável pelo usuário.
- Conjuga com ADR-008 (modelo base global baixável + ajuste local).

**Negativas / custos assumidos:**

- Documentação de instalação precisa cobrir 3 SOs (Linux, macOS, Windows).
- Modelo base v1 precisa caber em ~2GB (bge-m3 quantizado).
- Sem telemetria -- bugs reportados manualmente.

## Pendências / follow-ups

- [ ] ADR-014 detalha pré-requisitos de instalação.
- [ ] ADR-007 detalha Sessão de Pesquisa como artefato local.
- [ ] ADR-008 detalha distribuição do modelo base.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seções 1.3 e 2)
- Sprints relacionadas: S22 (registro), S23 (shell visível), S29 (sessão runner)
