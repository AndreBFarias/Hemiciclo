# src/coleta/camara.R -- Coleta de discursos da Camara dos Deputados via API Dados Abertos.
#
# Uso:
#   Rscript src/coleta/camara.R [diretorio_saida]
#
# Se diretorio_saida nao for passado, usa data/ na raiz do projeto.

library(tidyverse)
library(rvest)
library(RCurl)
library(glue)
library(lubridate)
library(doMC)

# Localiza raiz do projeto e carrega bibliotecas internas
args <- commandArgs(trailingOnly = FALSE)
script_arg <- sub("--file=", "", args[grep("--file=", args)])
if (length(script_arg) == 0) script_arg <- "src/coleta/camara.R"
raiz <- normalizePath(file.path(dirname(script_arg), "..", ".."), mustWork = FALSE)

source(file.path(raiz, "src", "lib", "rtf.R"))
source(file.path(raiz, "src", "lib", "api.R"))

# Diretorio de saida (argumento CLI ou padrao: <raiz>/data)
args_cli <- commandArgs(trailingOnly = TRUE)
dir_saida <- if (length(args_cli) >= 1) args_cli[1] else file.path(raiz, "data")
dir.create(dir_saida, showWarnings = FALSE, recursive = TRUE)

# Define inicio da 57a legislatura e gera intervalos mensais ate hoje
inicio_legislatura <- dmy("01/02/2023")
intervalos <- gerar_intervalos_mensais(inicio_legislatura)

# Monta URLs de listagem de discursos por mes
c_url2 <- purrr::map2_chr(
  intervalos$inicio,
  intervalos$fim,
  url_discursos_camara
)

# Le XML de cada URL
lista_discurso <- c_url2 %>% map(read_xml)

# Conta sessoes por XML
lista_sessoes <- lista_discurso %>%
  map_int(~ length(xml_name(xml_children(.x))))

# Extrai detalhes de cada sessao e discurso
extracao <- map2(lista_discurso, lista_sessoes, function(s, n) {
  map(seq_len(n), function(i) {
    tibble(
      codSessao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/codigo", i)), trim = TRUE),
      data = xml_text(xml_find_all(s, sprintf("//sessao[%d]/data", i)), trim = TRUE),
      numero_sessao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/numero", i)), trim = TRUE),
      tipo_sessao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/tipo", i)), trim = TRUE),
      codigo_faseSessao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/codigo", i)), trim = TRUE),
      descricao_faseSessao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/descricao", i)), trim = TRUE),
      hora_discurso = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/horaInicioDiscurso", i)), trim = TRUE),
      txtIndexacao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/txtIndexacao", i)), trim = TRUE),
      numeroQuarto = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/numeroQuarto", i)), trim = TRUE),
      numeroInsercao = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/numeroInsercao", i)), trim = TRUE),
      sumario = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/sumario", i)), trim = TRUE),
      numero_orador = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/orador/numero", i)), trim = TRUE),
      nome_orador = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/orador/nome", i)), trim = TRUE),
      partido_orador = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/orador/partido", i)), trim = TRUE),
      uf_orador = xml_text(xml_find_all(s, sprintf("//sessao[%d]/fasesSessao/faseSessao/discursos/discurso/orador/uf", i)), trim = TRUE)
    )
  })
})

df <- map_dfr(extracao, ~ map_dfr(.x, identity))

# Gera URLs do teor completo dos discursos
discursos_url <- glue(
  "https://www.camara.leg.br/SitCamaraWS/SessoesReunioes.asmx/",
  "obterInteiroTeorDiscursosPlenario?codSessao={df$codSessao}",
  "&numOrador={df$numero_orador}&numQuarto={df$numeroQuarto}",
  "&numInsercao={df$numeroInsercao}"
)

# Paralelismo configuravel via env var HEMICICLO_CORES (padrao 4)
nr_cores <- as.integer(Sys.getenv("HEMICICLO_CORES", unset = "4"))
registerDoMC(nr_cores)

# Baixa conteudo em paralelo com retries
res_ds_url <- foreach(ds_url = discursos_url) %dopar% {
  tryCatch({
    curlhand <- getCurlHandle()
    curlSetOpt(.opts = list(forbid.reuse = 1), curl = curlhand)
    retry(getURL(ds_url, curl = curlhand), max = 10, init = 0)
  }, error = function(e) {
    paste0(ds_url, " ## ERROR")
  })
}

# Identifica e reprocessa erros
saida <- unlist(res_ds_url)
erro <- which(!grepl('<?xml version=\"1.0\"', saida))
urls_com_erro <- as.list(discursos_url[erro])
res_ds_url__erro <- lapply(urls_com_erro, function(u) tryCatch(read_xml(u), error = function(e) NULL))
res_ds_url__erro <- Filter(Negate(is.null), res_ds_url__erro)
res_ds_url_final <- c(res_ds_url[-erro], res_ds_url__erro)
res_ds_url_final <- res_ds_url_final[grepl('<?xml version=\"1.0\"', res_ds_url_final)]

# Parseia XML e extrai teor completo
res_ds_url_xml_final <- lapply(res_ds_url_final, read_xml, options = "HUGE")

inteiro_teor <- map_dfr(res_ds_url_xml_final, function(l) {
  tibble(
    orador = xml_text(xml_find_first(l, "//nome")),
    partido = xml_text(xml_find_first(l, "//partido")),
    uf = xml_text(xml_find_first(l, "//uf")),
    horaInicioDiscurso = xml_text(xml_find_all(l, "//horaInicioDiscurso")),
    inteiro = decode_rtf(xml_text(xml_find_all(l, "//discursoRTFBase64")))
  )
})

# Persiste resultado
arquivo_saida <- file.path(dir_saida, "base_discursos_camara.rds")
saveRDS(inteiro_teor, arquivo_saida)
message(sprintf("[Hemiciclo] %d discursos salvos em %s", nrow(inteiro_teor), arquivo_saida))

# "O poder nao precisa ser tomado a forca, basta ser desmistificado." -- Simone Weil
