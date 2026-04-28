# src/lib/rtf.R -- Decodificacao de discursos em formato RTF Base64.

library(RCurl)
library(stringr)

#' Decodifica uma string RTF em Base64 para texto legivel em PT-BR.
#'
#' @param txt String RTF codificada em Base64.
#' @return Texto limpo, com acentuacao restaurada e controle RTF removido.
decode_rtf <- function(txt) {
  if (is.null(txt) || length(txt) == 0 || !nzchar(txt)) {
    return("")
  }
  txt %>%
    RCurl::base64Decode() %>%
    stringr::str_replace_all("\\\\'e3", "\u00e3") %>%
    stringr::str_replace_all("\\\\'e1", "\u00e1") %>%
    stringr::str_replace_all("\\\\'e9", "\u00e9") %>%
    stringr::str_replace_all("\\\\'e7", "\u00e7") %>%
    stringr::str_replace_all("\\\\'ed", "\u00ed") %>%
    stringr::str_replace_all("\\\\'f3", "\u00f3") %>%
    stringr::str_replace_all("\\\\'ea", "\u00ea") %>%
    stringr::str_replace_all("\\\\'e0", "\u00e0") %>%
    stringr::str_replace_all("(\\\\[[:alnum:]']+|[\\r\\n]|^\\{|\\}$)", "") %>%
    stringr::str_replace_all("\\{\\{[[:alnum:]; ]+\\}\\}", "") %>%
    stringr::str_trim()
}

# "O conhecimento e uma forma de liberdade." -- Hannah Arendt
