# ADR-002 -- Voto nominal como fonte primária de posição parlamentar

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** etl, metodologia

## Contexto e problema

Discursos e proposições, isoladamente, sofrem de ruído alto: parlamentares fazem performance retórica que diverge do voto efetivo, propõem PLs como sinalização sem militância real e omitem-se em pautas adversas. Para construir uma assinatura honesta de posicionamento, é necessário ancorar o sinal em um ato verificável e binário: o voto nominal em plenário e comissões.

## Drivers de decisão

- Necessidade de sinal robusto a performances retóricas
- Disponibilidade de voto nominal nas APIs oficiais (Câmara e Senado)
- Granularidade temporal (votação por proposição em data específica)
- Auditabilidade pública

## Opções consideradas

### Opção A -- Discurso como sinal primário, voto como complemento

- Prós: volume textual muito maior; cobre temas que não chegam à votação.
- Contras: alta variância semântica; performance política distorce; depende fortemente de NLP para extrair posição.

### Opção B -- Voto nominal como espinha dorsal, discurso/PL como amplificadores

- Prós: sinal verificável e auditável; reduz dependência de NLP; força a metodologia a privilegiar atos sobre palavras.
- Contras: alguns temas nunca chegam à votação; presidências e ausências introduzem viés; a granularidade temática depende do mapeamento PL→tópico (ADR-003).

## Decisão

Escolhida: **Opção B**.

Justificativa: alinha-se ao manifesto político do projeto -- privilegiar fato sobre narrativa. O voto é o ato político mais comprometido publicamente; a assinatura indutiva (ADR-004) usa discurso e PL como camadas que amplificam ou contradizem o sinal de voto, não como sinal primário. Casos de ausência ou abstenção são tratados como dado próprio (eixo de hipocrisia/volatilidade), não como falta de informação.

## Consequências

**Positivas:**

- Reduz dramaticamente a dependência de modelos de linguagem para inferir posição.
- Permite cálculo de eixos de coerência discurso-voto e PL-voto.
- Cria um chão duro de verificação que o usuário pode auditar manualmente.

**Negativas / custos assumidos:**

- Coleta de votos é mais complexa (S24, S25) do que coleta de discursos.
- Temas pouco votados terão sinal mais fraco -- compensado por C2 (TF-IDF) e C3 (embeddings).

## Pendências / follow-ups

- [ ] ADR-003 trata como mapear PL ao tópico (necessário para casar voto e tema).
- [ ] ADR-011 trata como combinar voto com camadas semânticas.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 2)
- Sprints relacionadas: S22 (registro), S24, S25 (coleta)
