# src/lib/api.R -- Wrappers para APIs de Dados Abertos da Camara e Senado.

library(jsonlite)
library(lubridate)

URL_SENADO_LISTA <- "http://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/%d/%d"
URL_SENADO_DISCURSOS <- "https://legis.senado.leg.br/dadosabertos/senador/%s/discursos"
URL_CAMARA_DISCURSOS <- paste0(
  "https://www.camara.leg.br/sitcamaraws/SessoesReunioes.asmx/",
  "ListarDiscursosPlenario?dataIni=%s&dataFim=%s",
  "&codigoSessao=&parteNomeParlamentar=&siglaPartido=&siglaUF="
)

#' Consulta lista de senadores para um intervalo de legislaturas.
#'
#' @param legislatura_inicio Numero da legislatura inicial (ex: 57).
#' @param legislatura_fim Numero da legislatura final (ex: 57).
#' @return Lista nomeada parseada do JSON retornado pela API.
listar_senadores <- function(legislatura_inicio, legislatura_fim) {
  if (!is.numeric(legislatura_inicio) || !is.numeric(legislatura_fim)) {
    stop("Legislaturas precisam ser numericas.")
  }
  url <- sprintf(URL_SENADO_LISTA, legislatura_inicio, legislatura_fim)
  jsonlite::fromJSON(url)
}

#' Gera URL para listar discursos de um senador.
#'
#' @param codigo Codigo do senador conforme API do Senado.
#' @return URL formatada.
url_discursos_senador <- function(codigo) {
  sprintf(URL_SENADO_DISCURSOS, codigo)
}

#' Gera intervalos mensais entre o inicio de uma legislatura e uma data final.
#'
#' @param inicio_legislatura Data de inicio (classe Date).
#' @param data_fim Data final do intervalo (classe Date). Default: hoje.
#' @return Lista com vetores 'inicio' e 'fim' formatados dd/mm/YYYY.
gerar_intervalos_mensais <- function(inicio_legislatura, data_fim = lubridate::today()) {
  if (!inherits(inicio_legislatura, "Date") || !inherits(data_fim, "Date")) {
    stop("Ambos os argumentos precisam ser objetos Date.")
  }
  meses <- lubridate::time_length(
    lubridate::interval(inicio_legislatura, data_fim), "month"
  )
  meses <- trunc(meses)
  inicios <- inicio_legislatura + months(1:meses)
  fins <- inicios + months(1) - 1
  fins[length(fins)] <- data_fim
  list(
    inicio = format(inicios, "%d/%m/%Y"),
    fim = format(fins, "%d/%m/%Y")
  )
}

#' Gera URL de listagem de discursos da Camara para um intervalo de datas.
#'
#' @param data_inicio String no formato dd/mm/YYYY.
#' @param data_fim String no formato dd/mm/YYYY.
#' @return URL formatada.
url_discursos_camara <- function(data_inicio, data_fim) {
  sprintf(URL_CAMARA_DISCURSOS, data_inicio, data_fim)
}

# "A virtude civica depende do saber exercido em publico." -- Hannah Arendt
