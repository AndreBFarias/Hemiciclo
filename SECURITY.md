# Política de Segurança -- Hemiciclo

## Versões Suportadas

| Versão | Suportada |
| ------ | --------- |
| 2.0.x  | sim       |
| 1.x    | não       |

## Reportando uma Vulnerabilidade

Se você descobrir uma vulnerabilidade de segurança, por favor:

1. **Não** abra uma issue pública
2. Envie um email para o mantenedor com detalhes da vulnerabilidade
3. Inclua:
   - Descrição da vulnerabilidade
   - Passos para reproduzir
   - Impacto potencial
   - Sugestões de correção (se houver)

## Tempo de Resposta

- Confirmação de recebimento: 48 horas
- Avaliação inicial: 7 dias
- Correção (se confirmada): 30 dias

## Escopo

Esta política cobre:

- Código fonte em `src/`
- Dependências R diretas listadas em `DESCRIPTION`
- Scripts de instalação e configuração (`install.sh`, `uninstall.sh`)
- Workflow de CI (`.github/workflows/ci.yml`)

## Fora do Escopo

- Vulnerabilidades em dependências upstream (tidyverse, httr, rvest etc) -- reporte diretamente aos mantenedores
- Ataques de engenharia social
- Disponibilidade das APIs de Dados Abertos da Câmara e do Senado

## Dados Sensíveis

O Hemiciclo consome apenas dados públicos das APIs de Dados Abertos e não persiste nenhum dado privado. Caso encontre dados privados expostos acidentalmente em saídas, reporte com urgência.

## Reconhecimento

Contribuidores que reportarem vulnerabilidades válidas serão reconhecidos no CHANGELOG (se desejarem).
