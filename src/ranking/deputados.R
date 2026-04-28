# src/ranking/deputados.R -- Ranking de deputados por projetos e discursos.
#
# Uso:
#   Rscript src/ranking/deputados.R [diretorio_dados]

library(readr)
library(readxl)
library(stringr)
library(tidyverse)

args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("--file=", "", args[grep("--file=", args)])
if (length(script_arg) == 0) script_arg <- "src/ranking/deputados.R"
raiz <- normalizePath(file.path(dirname(script_arg), "..", ".."), mustWork = FALSE)

source(file.path(raiz, "src", "lib", "ranking.R"))

args_cli <- commandArgs(trailingOnly = TRUE)
dir_dados <- if (length(args_cli) >= 1) args_cli[1] else file.path(raiz, "data")
if (!dir.exists(dir_dados)) {
  stop(sprintf("Diretorio de dados nao encontrado: %s", dir_dados))
}

# Le bases previamente coletadas
discursos_camara <- readRDS(file.path(dir_dados, "base_discursos_camara.rds"))
projetos_camara <- read_csv(file.path(dir_dados, "base_projetos_camara.csv"), show_col_types = FALSE)

# Filtra autores do tipo deputado
projetos_camara <- projetos_camara[grepl("Deputado", projetos_camara$Autor_Tipo), ]

# Seleciona colunas e normaliza nomes
projetos_camara <- projetos_camara[, c(16, 18:103)]
colnames(projetos_camara)[1] <- "deputado"
projetos_camara$deputado <- toupper(projetos_camara$deputado)
projetos_camara <- projetos_camara[!grepl("SENADO", projetos_camara$deputado), ]

# Desagrega autores multiplos
projetos_camara <- projetos_camara %>%
  mutate(deputado = strsplit(as.character(deputado), ", ")) %>%
  unnest(deputado)

projetos_camara$deputado <- trimws(projetos_camara$deputado)

# Agrupa e soma projetos por deputado
projetos_por_deputado <- projetos_camara %>%
  group_by(deputado) %>%
  summarise(across(everything(), list(sum)))

projetos_por_deputado$total_projetos <- rowSums(
  projetos_por_deputado[, c(2:ncol(projetos_por_deputado))]
)
projetos_por_deputado <- projetos_por_deputado[, c("deputado", "total_projetos")]
colnames(projetos_por_deputado)[1] <- "parlamentar"

# Agrupa discursos por orador
discursos_por_deputado <- discursos_camara %>%
  group_by(orador) %>%
  summarise(total_discursos = n())
colnames(discursos_por_deputado)[1] <- "parlamentar"

# Lista unica de deputados
lista_deputados <- unique(c(
  projetos_por_deputado$parlamentar,
  discursos_por_deputado$parlamentar
))
lista_deputados <- lista_deputados[!is.na(lista_deputados)]

# Junta, normaliza e calcula score
ranking_deputados <- juntar_ranking(
  lista_deputados, projetos_por_deputado, discursos_por_deputado
)
ranking_deputados$projetos_norm <- normalizar_minmax(ranking_deputados$total_projetos)
ranking_deputados$discursos_norm <- normalizar_minmax(ranking_deputados$total_discursos)
ranking_deputados$score_conversao <- calcular_score_conversao(
  ranking_deputados$projetos_norm,
  ranking_deputados$discursos_norm
)

ranking_deputados <- ranking_deputados %>% arrange(desc(score_conversao))
colnames(ranking_deputados)[1] <- "deputado"

arquivo_saida <- file.path(dir_dados, "ranking_deputados.csv")
write_csv(ranking_deputados, arquivo_saida)
message(sprintf("[Hemiciclo] ranking salvo em %s (%d deputados)", arquivo_saida, nrow(ranking_deputados)))

# "A medida do homem publico e o que ele faz quando ninguem esta olhando." -- Ralph Waldo Emerson
