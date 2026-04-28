# src/lib/ranking.R -- Normalizacao e calculo de score de ranking parlamentar.

library(dplyr)

#' Normaliza um vetor numerico para o intervalo [0, 1] via min-max scaling.
#'
#' @param x Vetor numerico.
#' @return Vetor numerico no intervalo [0, 1]. Retorna zeros se amplitude for nula.
normalizar_minmax <- function(x) {
  if (length(x) == 0) {
    return(numeric(0))
  }
  minimo <- min(x, na.rm = TRUE)
  maximo <- max(x, na.rm = TRUE)
  if (maximo == minimo) {
    return(rep(0, length(x)))
  }
  (x - minimo) / (maximo - minimo)
}

#' Calcula score de conversao como media simples de dois vetores normalizados.
#'
#' @param projetos_norm Vetor numerico normalizado.
#' @param discursos_norm Vetor numerico normalizado.
#' @return Vetor numerico com a media aritmetica posicional.
calcular_score_conversao <- function(projetos_norm, discursos_norm) {
  if (length(projetos_norm) != length(discursos_norm)) {
    stop("Vetores precisam ter o mesmo tamanho.")
  }
  (projetos_norm + discursos_norm) / 2
}

#' Junta contagens de projetos e discursos em um dataframe unico e preenche NAs.
#'
#' @param parlamentares Vetor de nomes unicos.
#' @param projetos Dataframe com colunas (parlamentar, total_projetos).
#' @param discursos Dataframe com colunas (parlamentar, total_discursos).
#' @return Dataframe com colunas (parlamentar, total_projetos, total_discursos).
juntar_ranking <- function(parlamentares, projetos, discursos) {
  base <- data.frame(parlamentar = parlamentares, stringsAsFactors = FALSE)
  base <- dplyr::left_join(base, projetos, by = "parlamentar")
  base <- dplyr::left_join(base, discursos, by = "parlamentar")
  base[is.na(base)] <- 0
  base
}

# "Toda norma e um instrumento de poder." -- Michel Foucault
