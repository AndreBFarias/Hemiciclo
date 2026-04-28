source(file.path(raiz_projeto(), "src", "lib", "ranking.R"))

test_that("normalizar_minmax mapeia para [0, 1] com min=0 e max=1", {
  resultado <- normalizar_minmax(c(1, 5, 10))
  expect_equal(resultado[1], 0)
  expect_equal(resultado[3], 1)
  expect_true(all(resultado >= 0 & resultado <= 1))
})

test_that("normalizar_minmax retorna zeros quando amplitude e nula", {
  resultado <- normalizar_minmax(c(5, 5, 5))
  expect_true(all(resultado == 0))
})

test_that("normalizar_minmax lida com vetor vazio", {
  expect_equal(length(normalizar_minmax(numeric(0))), 0)
})

test_that("calcular_score_conversao e media aritmetica simples", {
  resultado <- calcular_score_conversao(c(0, 0.5, 1), c(1, 0.5, 0))
  expect_equal(resultado, c(0.5, 0.5, 0.5))
})

test_that("calcular_score_conversao falha se vetores tiverem tamanhos diferentes", {
  expect_error(calcular_score_conversao(c(1, 2), c(1, 2, 3)))
})

test_that("juntar_ranking preenche NAs com zero e mantem todos os parlamentares", {
  projetos <- data.frame(parlamentar = c("Alice", "Bob"), total_projetos = c(3, 1), stringsAsFactors = FALSE)
  discursos <- data.frame(parlamentar = c("Bob", "Carol"), total_discursos = c(2, 5), stringsAsFactors = FALSE)
  lista <- c("Alice", "Bob", "Carol")
  resultado <- juntar_ranking(lista, projetos, discursos)
  expect_equal(nrow(resultado), 3)
  expect_equal(resultado$total_projetos[resultado$parlamentar == "Carol"], 0)
  expect_equal(resultado$total_discursos[resultado$parlamentar == "Alice"], 0)
})
