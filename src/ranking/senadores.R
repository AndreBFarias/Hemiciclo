# src/ranking/senadores.R -- Ranking de senadores por projetos e discursos.
#
# Uso:
#   Rscript src/ranking/senadores.R [diretorio_dados]

library(readr)
library(readxl)
library(writexl)
library(stringr)
library(tidyverse)

args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("--file=", "", args[grep("--file=", args)])
if (length(script_arg) == 0) script_arg <- "src/ranking/senadores.R"
raiz <- normalizePath(file.path(dirname(script_arg), "..", ".."), mustWork = FALSE)

source(file.path(raiz, "src", "lib", "ranking.R"))

args_cli <- commandArgs(trailingOnly = TRUE)
dir_dados <- if (length(args_cli) >= 1) args_cli[1] else file.path(raiz, "data")
if (!dir.exists(dir_dados)) {
  stop(sprintf("Diretorio de dados nao encontrado: %s", dir_dados))
}

# Le bases previamente coletadas
discursos_senado <- readRDS(file.path(dir_dados, "base_discursos_senado.rds"))
projetos_senado <- read_xlsx(file.path(dir_dados, "base_projetos_senado.xlsx"))

# Extrai nome do senador do titulo do pronunciamento
discursos_senado$senador <- str_extract(discursos_senado$titulo, "(?<=Pronunciamento de ).*(?= em)")

# Agrupa discursos por senador
discursos_por_senador <- discursos_senado %>%
  group_by(senador) %>%
  summarise(total_discursos = n())
colnames(discursos_por_senador)[1] <- "parlamentar"

# Agrupa projetos por senador
projetos_por_senador <- projetos_senado %>%
  group_by(AutorPrincipal.IdentificacaoParlamentar.NomeParlamentar) %>%
  summarise(total_projetos = n())
colnames(projetos_por_senador)[1] <- "parlamentar"

# Lista unica de senadores
lista_senadores <- unique(c(
  discursos_por_senador$parlamentar,
  projetos_por_senador$parlamentar
))
lista_senadores <- lista_senadores[!is.na(lista_senadores)]

# Junta, normaliza e calcula score
ranking_senadores <- juntar_ranking(
  lista_senadores, projetos_por_senador, discursos_por_senador
)
ranking_senadores$projetos_norm <- normalizar_minmax(ranking_senadores$total_projetos)
ranking_senadores$discursos_norm <- normalizar_minmax(ranking_senadores$total_discursos)
ranking_senadores$score_conversao <- calcular_score_conversao(
  ranking_senadores$projetos_norm,
  ranking_senadores$discursos_norm
)

ranking_senadores <- ranking_senadores %>% arrange(desc(score_conversao))
colnames(ranking_senadores)[1] <- "senador"

arquivo_saida <- file.path(dir_dados, "ranking_senadores.xlsx")
write_xlsx(ranking_senadores, arquivo_saida)
message(sprintf("[Hemiciclo] ranking salvo em %s (%d senadores)", arquivo_saida, nrow(ranking_senadores)))

# "Quem se cala tambem governa." -- proverbio popular
