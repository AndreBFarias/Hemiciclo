# Helper: determina raiz do projeto para os testes localizarem src/lib/*.R.
raiz_projeto <- function() {
  env <- Sys.getenv("HEMICICLO_RAIZ", unset = "")
  if (nzchar(env)) return(normalizePath(env, mustWork = FALSE))
  # Fallback: dois niveis acima do arquivo helper (tests/testthat -> projeto)
  normalizePath(file.path(getwd(), "..", ".."), mustWork = FALSE)
}
