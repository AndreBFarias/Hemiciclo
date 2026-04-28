source(file.path(raiz_projeto(), "src", "lib", "api.R"))

test_that("url_discursos_senador insere o codigo na URL", {
  url <- url_discursos_senador("1234")
  expect_true(grepl("1234", url))
  expect_true(grepl("^https://legis\\.senado\\.leg\\.br", url))
})

test_that("url_discursos_camara insere datas no formato dd/mm/yyyy", {
  url <- url_discursos_camara("01/02/2023", "28/02/2023")
  expect_true(grepl("dataIni=01/02/2023", url, fixed = TRUE))
  expect_true(grepl("dataFim=28/02/2023", url, fixed = TRUE))
})

test_that("gerar_intervalos_mensais produz inicio e fim sincronizados", {
  library(lubridate)
  inicio <- dmy("01/02/2023")
  fim <- dmy("15/04/2023")
  resultado <- gerar_intervalos_mensais(inicio, fim)
  expect_length(resultado$inicio, length(resultado$fim))
  expect_true(all(grepl("^\\d{2}/\\d{2}/\\d{4}$", resultado$inicio)))
  expect_true(all(grepl("^\\d{2}/\\d{2}/\\d{4}$", resultado$fim)))
})

test_that("gerar_intervalos_mensais recusa argumentos nao-Date", {
  expect_error(gerar_intervalos_mensais("2023-02-01", Sys.Date()))
})

test_that("listar_senadores recusa argumentos nao-numericos", {
  expect_error(listar_senadores("57", 57))
  expect_error(listar_senadores(57, "57"))
})
