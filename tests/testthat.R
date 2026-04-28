library(testthat)

# Descobre raiz do projeto (pai do diretorio tests/)
args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("--file=", "", args[grep("--file=", args)])
if (length(script_arg) > 0 && nzchar(script_arg)) {
  raiz <- normalizePath(file.path(dirname(script_arg), ".."), mustWork = FALSE)
} else {
  raiz <- normalizePath("..", mustWork = FALSE)
}
Sys.setenv(HEMICICLO_RAIZ = raiz)

test_dir(file.path(raiz, "tests", "testthat"))
