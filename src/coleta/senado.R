# src/coleta/senado.R -- Coleta de discursos do Senado Federal via API Dados Abertos.
#
# Uso:
#   Rscript src/coleta/senado.R [diretorio_saida]
#
# Se diretorio_saida nao for passado, usa data/ na raiz do projeto.

library(tidyverse)
library(purrr)
library(dplyr)
library(jsonlite)
library(httr)
library(rvest)

args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("--file=", "", args[grep("--file=", args)])
if (length(script_arg) == 0) script_arg <- "src/coleta/senado.R"
raiz <- normalizePath(file.path(dirname(script_arg), "..", ".."), mustWork = FALSE)

source(file.path(raiz, "src", "lib", "api.R"))

args_cli <- commandArgs(trailingOnly = TRUE)
dir_saida <- if (length(args_cli) >= 1) args_cli[1] else file.path(raiz, "data")
dir.create(dir_saida, showWarnings = FALSE, recursive = TRUE)

# Busca senadores da 57a legislatura
leg_57 <- listar_senadores(57, 57)

codigo_discurso <- leg_57 %>%
  purrr::pluck(1) %>%
  purrr::pluck(4) %>%
  purrr::pluck(1) %>%
  purrr::pluck(1) %>%
  dplyr::pull(1)

# Gera URLs para discursos de cada senador
url_discurso <- purrr::map_chr(codigo_discurso, url_discursos_senador)

base <- url_discurso %>% map(fromJSON)

# Navega na estrutura aninhada do JSON
b <- base %>% modify_depth(3, ~ purrr::pluck(.x, 2))
b1 <- b %>% map(~ purrr::pluck(.x, 1))
b2 <- b1 %>% map(~ purrr::pluck(.x, 4) %>% purrr::pluck(1) %>% purrr::pluck(9))

b3 <- map2_dfr(codigo_discurso, b2, function(codigo, urls) {
  if (is.null(urls) || length(urls) == 0) return(NULL)
  tibble(codigo = codigo, url = urls)
})

# Persiste URLs coletadas
arquivo_urls <- file.path(dir_saida, "urls_discursos_senado.rds")
saveRDS(b3, arquivo_urls)

# Extrai texto HTML de uma pagina de pronunciamento
extrair_texto_html <- function(url_texto) {
  read_html(url_texto) %>%
    html_nodes(xpath = "//div[@id='content']") %>%
    html_text()
}

# Itera sobre URLs coletando texto
d <- NULL
for (i in seq_len(nrow(b3))) {
  tryCatch({
    texto <- extrair_texto_html(b3$url[[i]]) %>%
      tibble::tibble(discurso = .) %>%
      dplyr::mutate(
        codigo = b3$codigo[[i]],
        url_texto = b3$url[[i]]
      )
    d <- rbind(d, texto)
  }, error = function(e) {
    message(sprintf("[Hemiciclo] erro ao coletar %s: %s", b3$url[[i]], conditionMessage(e)))
  })
}

# Reordena colunas
if (!is.null(d)) {
  d <- d[, c("codigo", "url_texto", "discurso")]
}

arquivo_base <- file.path(dir_saida, "base_discursos_senado.rds")
saveRDS(d, arquivo_base)
message(sprintf("[Hemiciclo] %d discursos salvos em %s", ifelse(is.null(d), 0, nrow(d)), arquivo_base))

# "A palavra publica e o solo onde a liberdade se enraiza." -- Hannah Arendt
