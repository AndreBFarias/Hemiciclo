source(file.path(raiz_projeto(), "src", "lib", "rtf.R"))

test_that("decode_rtf retorna string vazia para entrada nula ou vazia", {
  expect_equal(decode_rtf(NULL), "")
  expect_equal(decode_rtf(""), "")
})

test_that("decode_rtf remove marcadores de controle RTF", {
  library(RCurl)
  rtf_sample <- base64Encode(charToRaw("{\\rtf1\\ansi Ola\\par}"))[[1]]
  resultado <- decode_rtf(rtf_sample)
  expect_false(grepl("\\\\rtf1", resultado))
  expect_false(grepl("\\\\ansi", resultado))
  expect_true(grepl("Ola", resultado))
})

test_that("decode_rtf restaura acentuacao PT-BR a partir dos codigos escapados", {
  library(RCurl)
  entrada_raw <- "{\\rtf1 informa\\'e7\\'e3o}"
  encoded <- base64Encode(charToRaw(entrada_raw))[[1]]
  resultado <- decode_rtf(encoded)
  expect_true(grepl("informa\u00e7\u00e3o", resultado))
})
