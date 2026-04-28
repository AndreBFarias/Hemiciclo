# Guia de Contribuição -- Hemiciclo

## Como Contribuir

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/minha-feature`)
3. Faça commits seguindo Conventional Commits
4. Envie um Pull Request

## Padrão de Commits

```
tipo: descrição imperativa em português

Tipos: feat, fix, refactor, docs, test, perf, chore, style, ci, build
```

### Regras

- Idioma: português (PT-BR) com acentuação correta
- Zero emojis em commits, código e documentação
- Zero menções a ferramentas de IA
- Descrição imperativa e concisa

## Padrão de Código R

- Seguir convenções do [tidyverse style guide](https://style.tidyverse.org/)
- `snake_case` para nomes de funções e variáveis
- Separar lógica em funções puras sempre que possível (para permitir testes)
- Paths relativos via `file.path()` (nunca hardcoded absolutos)
- Error handling explícito com `tryCatch()`
- Limite de 500 linhas por arquivo `.R`

## Estrutura do Projeto

```
src/
  lib/           # Funções reutilizáveis (testáveis)
  coleta/        # Scripts de coleta via APIs
  ranking/       # Scripts de cálculo de ranking
tests/
  testthat/      # Testes unitários
```

## Testes

Instale o `testthat` e rode:

```bash
R -e "install.packages('testthat', repos='https://cloud.r-project.org')"
Rscript tests/testthat.R
```

Ou diretamente:

```r
testthat::test_dir("tests/testthat")
```

## Configuração do Ambiente

```bash
git clone https://github.com/AndreBFarias/Hemiciclo.git
cd Hemiciclo
# Instalar dependencias R:
R -e "install.packages(c('tidyverse', 'rvest', 'RCurl', 'glue', 'lubridate', 'jsonlite', 'httr', 'textreadr', 'doMC', 'readxl', 'writexl', 'stringr', 'testthat'), repos='https://cloud.r-project.org')"
```

Ou use o `install.sh`:

```bash
./install.sh
```

## Processo de Review

1. Abra um PR contra a branch `main`
2. Aguarde a revisão do mantenedor
3. Faça as correções solicitadas
4. Merge após aprovação
