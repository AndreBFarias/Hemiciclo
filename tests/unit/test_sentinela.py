"""Testes sentinela do bootstrap (S22).

Garantem que o CLI, a versão e a configuração básica funcionam antes de
qualquer feature posterior. Se este arquivo quebrar, tudo a jusante quebra.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hemiciclo import __version__
from hemiciclo.cli import app
from hemiciclo.config import Configuracao


@pytest.fixture
def runner() -> CliRunner:
    """Runner Typer reutilizável."""
    return CliRunner()


def test_versao(runner: CliRunner) -> None:
    """``hemiciclo --version`` imprime a versão e sai com código 0."""
    resultado = runner.invoke(app, ["--version"])
    assert resultado.exit_code == 0
    assert f"hemiciclo {__version__}" in resultado.stdout


def test_versao_constante() -> None:
    """A versão do pacote é exatamente ``2.1.1`` (release v2.1.1, S38.9)."""
    assert __version__ == "2.1.1"


def test_help(runner: CliRunner) -> None:
    """``hemiciclo --help`` exibe o uso e sai com código 0."""
    resultado = runner.invoke(app, ["--help"])
    assert resultado.exit_code == 0
    assert "Usage" in resultado.stdout


def test_info_cria_diretorios(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo info`` cria todos os diretórios da home se ausentes."""
    resultado = runner.invoke(app, ["info"])
    assert resultado.exit_code == 0
    assert tmp_hemiciclo_home.is_dir()
    for sub in ("modelos", "sessoes", "cache", "logs", "topicos"):
        assert (tmp_hemiciclo_home / sub).is_dir(), f"diretório ausente: {sub}"


def test_info_lista_paths(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo info`` imprime os paths principais e o random_state."""
    resultado = runner.invoke(app, ["info"])
    assert resultado.exit_code == 0
    assert str(tmp_hemiciclo_home) in resultado.stdout
    assert "Random state" in resultado.stdout
    assert "Modelo base" in resultado.stdout


def test_info_modelo_nenhum(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """Sem modelo base instalado, info reporta 'nenhum'."""
    resultado = runner.invoke(app, ["info"])
    assert resultado.exit_code == 0
    assert "nenhum" in resultado.stdout


def test_info_modelo_detectado(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """Com ``base_v1.pkl`` presente, info reporta o nome do arquivo."""
    tmp_hemiciclo_home.mkdir(parents=True, exist_ok=True)
    modelos = tmp_hemiciclo_home / "modelos"
    modelos.mkdir(parents=True, exist_ok=True)
    (modelos / "base_v1.pkl").write_bytes(b"fake")

    resultado = runner.invoke(app, ["info"])
    assert resultado.exit_code == 0
    assert "base_v1.pkl" in resultado.stdout


def test_config_random_state_default(tmp_hemiciclo_home: Path) -> None:
    """O random_state default é 42 (I3 do BRIEF)."""
    cfg = Configuracao()
    assert cfg.random_state == 42


def test_config_env_override(tmp_hemiciclo_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Variável HEMICICLO_RANDOM_STATE sobrescreve o default."""
    monkeypatch.setenv("HEMICICLO_RANDOM_STATE", "99")
    cfg = Configuracao()
    assert cfg.random_state == 99


def test_config_paths_derivados(tmp_hemiciclo_home: Path) -> None:
    """Os paths derivados são filhos da home configurada."""
    cfg = Configuracao()
    assert cfg.modelos_dir == cfg.home / "modelos"
    assert cfg.sessoes_dir == cfg.home / "sessoes"
    assert cfg.cache_dir == cfg.home / "cache"
    assert cfg.logs_dir == cfg.home / "logs"
    assert cfg.topicos_dir == cfg.home / "topicos"


def test_config_garantir_diretorios_idempotente(tmp_hemiciclo_home: Path) -> None:
    """Chamar garantir_diretorios duas vezes não quebra nada."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    cfg.garantir_diretorios()
    assert cfg.home.is_dir()


def test_main_module_importavel() -> None:
    """O módulo ``hemiciclo.__main__`` é importável e expõe ``main``."""
    from hemiciclo import __main__ as runner_module

    assert callable(runner_module.main)


def test_dashboard_falha_quando_streamlit_ausente(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_hemiciclo_home: Path,
) -> None:
    """Sem streamlit no PATH, ``hemiciclo dashboard`` aborta com exit 1."""
    monkeypatch.setattr("hemiciclo.cli.shutil.which", lambda _bin: None)
    resultado = runner.invoke(app, ["dashboard"])
    assert resultado.exit_code == 1
    assert "streamlit" in resultado.stdout


def test_coletar_camara_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo coletar camara --help`` documenta as opções principais."""
    import os

    resultado = runner.invoke(
        app,
        ["coletar", "camara", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--legislatura" in saida
    assert "--tipos" in saida
    assert "--max-itens" in saida


def test_coletar_camara_tipo_invalido(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """Tipo desconhecido aborta com exit 2 e mensagem clara."""
    resultado = runner.invoke(
        app,
        ["coletar", "camara", "--legislatura", "57", "--tipos", "abacaxi"],
    )
    assert resultado.exit_code == 2
    assert "inválido" in resultado.stdout.lower() or "abacaxi" in resultado.stdout


def test_coletar_senado_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo coletar senado --help`` documenta as opções principais."""
    import os

    resultado = runner.invoke(
        app,
        ["coletar", "senado", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--ano" in saida
    assert "--tipos" in saida
    assert "--max-itens" in saida


def test_coletar_senado_tipo_invalido(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """Tipo desconhecido no Senado aborta com exit 2 e mensagem clara."""
    resultado = runner.invoke(
        app,
        ["coletar", "senado", "--ano", "2024", "--tipos", "abacaxi"],
    )
    assert resultado.exit_code == 2
    assert "inválido" in resultado.stdout.lower() or "abacaxi" in resultado.stdout


def test_db_init_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo db init --help`` documenta a flag --db-path."""
    import os

    resultado = runner.invoke(
        app,
        ["db", "init", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--db-path" in resultado.stdout


def test_db_consolidar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo db consolidar --help`` documenta as flags --parquets e --db-path."""
    import os

    resultado = runner.invoke(
        app,
        ["db", "consolidar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--parquets" in resultado.stdout
    assert "--db-path" in resultado.stdout


def test_db_info_em_db_vazio(runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path) -> None:
    """``hemiciclo db info`` em DB recém-criado mostra a versão do schema e zero linhas."""
    db = tmp_path / "vazio.duckdb"
    resultado = runner.invoke(app, ["db", "info", "--db-path", str(db)])
    assert resultado.exit_code == 0
    # Pós-S27.1: schema v2. Tolerante a evoluções futuras.
    assert "schema v" in resultado.stdout
    assert "proposicoes: 0" in resultado.stdout
    assert "discursos: 0" in resultado.stdout


def test_db_consolidar_dir_inexistente(
    runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path
) -> None:
    """``hemiciclo db consolidar`` com diretório inexistente sai com exit 2."""
    inexistente = tmp_path / "nao_existe"
    db = tmp_path / "x.duckdb"
    resultado = runner.invoke(
        app,
        ["db", "consolidar", "--parquets", str(inexistente), "--db-path", str(db)],
    )
    assert resultado.exit_code == 2
    assert "inexistente" in resultado.stdout.lower()


def test_classificar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo classificar --help`` documenta as flags principais (S27)."""
    import os

    resultado = runner.invoke(
        app,
        ["classificar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--topico" in saida
    assert "--db-path" in saida
    assert "--camadas" in saida
    assert "--top-n" in saida
    assert "--output" in saida


def test_classificar_topico_inexistente(
    runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path
) -> None:
    """``hemiciclo classificar`` com tópico ausente sai com exit 2."""
    db = tmp_path / "x.duckdb"
    resultado = runner.invoke(
        app,
        [
            "classificar",
            "--topico",
            str(tmp_path / "nao_existe.yaml"),
            "--db-path",
            str(db),
        ],
    )
    assert resultado.exit_code == 2


def test_classificar_camadas_invalidas(
    runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path
) -> None:
    """Camadas fora de {regex,votos,tfidf} resultam em exit 2."""
    import duckdb

    from hemiciclo.etl.migrations import aplicar_migrations

    raiz = Path(__file__).resolve().parents[2]
    topico_path = raiz / "topicos" / "aborto.yaml"
    db = tmp_path / "x.duckdb"
    conn = duckdb.connect(str(db))
    aplicar_migrations(conn)
    conn.close()

    resultado = runner.invoke(
        app,
        [
            "classificar",
            "--topico",
            str(topico_path),
            "--db-path",
            str(db),
            "--camadas",
            "embeddings",
        ],
    )
    assert resultado.exit_code == 2
    assert "inv" in resultado.stdout.lower()


def test_sessao_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo sessao --help`` documenta os 8 subcomandos (S29 + S35)."""
    import os

    resultado = runner.invoke(
        app,
        ["sessao", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    for sub in (
        "iniciar",
        "listar",
        "status",
        "retomar",
        "pausar",
        "cancelar",
        "exportar",
        "importar",
    ):
        assert sub in saida, f"subcomando ausente em --help: {sub}"


def test_sessao_exportar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo sessao exportar --help`` documenta a flag --destino (S35)."""
    import os

    resultado = runner.invoke(
        app,
        ["sessao", "exportar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--destino" in resultado.stdout


def test_sessao_importar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo sessao importar --help`` documenta a flag --sem-validar (S35)."""
    import os

    resultado = runner.invoke(
        app,
        ["sessao", "importar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--sem-validar" in resultado.stdout


def test_sessao_listar_vazio(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo sessao listar`` em home vazia mostra 'nenhuma sessão'."""
    resultado = runner.invoke(app, ["sessao", "listar"])
    assert resultado.exit_code == 0
    assert "nenhuma" in resultado.stdout.lower()


def test_sessao_status_inexistente(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo sessao status <id>`` para id inexistente sai com exit 2."""
    resultado = runner.invoke(app, ["sessao", "status", "fantasma_xxx"])
    assert resultado.exit_code == 2
    assert "fantasma_xxx" in resultado.stdout or "não encontrada" in resultado.stdout


def test_sessao_iniciar_default_pipeline_real(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``sessao iniciar --help`` documenta a flag ``--dummy`` (S30).

    O default do comando é o pipeline REAL (S30); a flag ``--dummy``
    permanece opcional para compat com S29 e testes locais sem rede.
    """
    import os

    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--dummy" in saida
    assert "--topico" in saida


def test_sessao_iniciar_dummy_explicito_funciona(
    runner: CliRunner, tmp_hemiciclo_home: Path
) -> None:
    """``sessao iniciar ... --dummy`` deve criar sessão sem erro.

    Apenas valida que o comando aceita a flag e produz a saída esperada
    contendo ``pipeline=dummy``. O subprocess detached completa em
    background; este teste não espera o término.
    """
    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--dummy"],
    )
    assert resultado.exit_code == 0, resultado.stdout
    assert "pipeline=dummy" in resultado.stdout
    assert "sessao=" in resultado.stdout


def test_sessao_iniciar_aceita_max_itens_smoke(
    runner: CliRunner, tmp_hemiciclo_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``sessao iniciar --max-itens 5`` passa pela CLI sem erro (S30.1).

    Mocka ``SessaoRunner.iniciar`` para evitar spawn de subprocess real;
    valida apenas que o flag deixou de ser placeholder e atravessa a
    construção de ``ParametrosBusca``.
    """
    from hemiciclo.sessao import runner as runner_module

    chamadas: list[object] = []
    original_init = runner_module.SessaoRunner.__init__

    def _fake_init(self: object, home: Path, params: object, **_: object) -> None:
        chamadas.append(params)
        original_init(self, home, params)  # type: ignore[arg-type]

    monkeypatch.setattr(runner_module.SessaoRunner, "__init__", _fake_init)
    monkeypatch.setattr(
        runner_module.SessaoRunner,
        "iniciar",
        lambda self, _path: 99999,
    )

    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--max-itens", "5", "--dummy"],
    )
    assert resultado.exit_code == 0, resultado.stdout
    assert "pipeline=dummy" in resultado.stdout
    assert "pid=99999" in resultado.stdout
    assert chamadas, "SessaoRunner não foi instanciado"
    params_capturados = chamadas[0]
    assert getattr(params_capturados, "max_itens") == 5  # noqa: B009


def test_sessao_iniciar_max_itens_zero_falha_com_mensagem_amigavel(
    runner: CliRunner, tmp_hemiciclo_home: Path
) -> None:
    """``sessao iniciar --max-itens 0`` é rejeitado com mensagem amigável.

    Pós S30.2 a CLI captura ``pydantic.ValidationError`` e converte em
    ``typer.Exit(2)`` com mensagem em vermelho ("Parâmetros inválidos").
    O sentinela continua garantindo que a validação não escapa
    silenciosamente, mas agora o usuário vê texto humano em vez do
    traceback bruto do Pydantic.
    """
    resultado = runner.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--max-itens", "0", "--dummy"],
    )
    assert resultado.exit_code == 2
    saida = resultado.stdout.lower()
    assert "parâmetros inválidos" in saida
    assert "max_itens" in saida


def test_modelo_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo modelo base --help`` cobre os 4 subcomandos da S28."""
    import os

    resultado = runner.invoke(
        app,
        ["modelo", "base", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    for sub in ("baixar", "treinar", "carregar", "info"):
        assert sub in saida, f"subcomando ausente em --help: {sub}"


def test_modelo_base_treinar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo modelo base treinar --help`` documenta as flags do treino."""
    import os

    resultado = runner.invoke(
        app,
        ["modelo", "base", "treinar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--n-amostra" in saida
    assert "--n-componentes" in saida
    assert "--db-path" in saida


def test_modelo_base_info_sem_modelo(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo modelo base info`` em home limpa reporta estado coerente."""
    resultado = runner.invoke(app, ["modelo", "base", "info"])
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "modelo base v1" in saida
    assert "ainda não treinado" in saida
    assert "bge-m3" in saida


def test_rede_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo rede --help`` documenta o subcomando ``analisar`` (S32)."""
    import os

    resultado = runner.invoke(
        app,
        ["rede", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "analisar" in resultado.stdout


def test_rede_analisar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo rede analisar --help`` documenta a flag --tipo."""
    import os

    resultado = runner.invoke(
        app,
        ["rede", "analisar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--tipo" in resultado.stdout


def test_rede_analisar_sessao_inexistente(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo rede analisar`` com id inexistente sai com exit 2."""
    resultado = runner.invoke(app, ["rede", "analisar", "fantasma_xxx"])
    assert resultado.exit_code == 2


def test_rede_analisar_tipo_invalido(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """Tipo fora de {coautoria, voto, ambos} gera exit 2."""
    resultado = runner.invoke(app, ["rede", "analisar", "qualquer", "--tipo", "abacaxi"])
    assert resultado.exit_code == 2
    assert "inv" in resultado.stdout.lower()


def test_historico_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo historico --help`` documenta o subcomando ``calcular`` (S33)."""
    import os

    resultado = runner.invoke(
        app,
        ["historico", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "calcular" in resultado.stdout


def test_historico_calcular_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo historico calcular --help`` documenta as flags principais."""
    import os

    resultado = runner.invoke(
        app,
        ["historico", "calcular", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "--granularidade" in saida
    assert "--threshold-pp" in saida
    assert "--top-n" in saida


def test_historico_calcular_sessao_inexistente(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``historico calcular`` com id inexistente sai com exit 2."""
    resultado = runner.invoke(app, ["historico", "calcular", "fantasma_xxx"])
    assert resultado.exit_code == 2


def test_historico_calcular_granularidade_invalida(
    runner: CliRunner, tmp_hemiciclo_home: Path
) -> None:
    """Granularidade fora de {ano, legislatura} -> exit 2."""
    sessao_dir = tmp_hemiciclo_home / "sessoes" / "x"
    sessao_dir.mkdir(parents=True)
    resultado = runner.invoke(
        app,
        ["historico", "calcular", "x", "--granularidade", "mes"],
    )
    assert resultado.exit_code == 2
    assert "inv" in resultado.stdout.lower()


def test_convertibilidade_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo convertibilidade --help`` documenta os subcomandos (S34)."""
    import os

    resultado = runner.invoke(
        app,
        ["convertibilidade", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    saida = resultado.stdout
    assert "treinar" in saida
    assert "prever" in saida


def test_convertibilidade_treinar_help(runner: CliRunner, tmp_hemiciclo_home: Path) -> None:
    """``hemiciclo convertibilidade treinar --help`` documenta --top-n."""
    import os

    resultado = runner.invoke(
        app,
        ["convertibilidade", "treinar", "--help"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert resultado.exit_code == 0
    assert "--top-n" in resultado.stdout


def test_convertibilidade_treinar_sessao_inexistente(
    runner: CliRunner, tmp_hemiciclo_home: Path
) -> None:
    """``convertibilidade treinar`` com id inexistente sai com exit 2."""
    resultado = runner.invoke(app, ["convertibilidade", "treinar", "fantasma_xxx"])
    assert resultado.exit_code == 2


def test_seed_dashboard_script_executavel(tmp_hemiciclo_home: Path) -> None:
    """``scripts/seed_dashboard.py`` cria 3 sessões com prefixo ``_seed_*``."""
    import importlib.util

    raiz = Path(__file__).resolve().parents[2]
    caminho = raiz / "scripts" / "seed_dashboard.py"
    assert caminho.is_file(), f"script ausente: {caminho}"
    spec = importlib.util.spec_from_file_location("seed_dashboard_sentinela", caminho)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()  # type: ignore[attr-defined]
    assert rc == 0
    sessoes_dir = tmp_hemiciclo_home / "sessoes"
    nomes = {p.name for p in sessoes_dir.iterdir() if p.is_dir()}
    assert "_seed_concluida" in nomes
    assert "_seed_em_andamento" in nomes
    assert "_seed_erro" in nomes


def test_sentinela_pipeline_aplica_filtro_apos_etl() -> None:
    """S30.2: helper de filtro é chamado em C1+C2, nunca na coleta/ETL.

    Defesa arquitetural: filtro UF/partido acontece **após** o ETL (etapa
    3, ``_etapa_classificacao_c1_c2``). Cache transversal SHA256 (S26)
    deduplica a coleta global; restringir ali enviesaria a amostra
    quando combinada com ``--max-itens``. Inspeciona o módulo via AST
    para isolar o corpo de cada função (``def`` aninhado entre etapas
    confunde busca textual ingênua).
    """
    import ast

    from hemiciclo.sessao import pipeline as pipeline_mod

    fonte = Path(pipeline_mod.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    funcoes = {no.name: no for no in arvore.body if isinstance(no, ast.FunctionDef)}
    assert "_etapa_classificacao_c1_c2" in funcoes
    assert "_etapa_coleta" in funcoes
    assert "_etapa_etl" in funcoes
    assert "_montar_clausula_subset_parlamentares" in funcoes

    def _chama_helper(no_funcao: ast.FunctionDef) -> bool:
        """Retorna True se o corpo de ``no_funcao`` invoca o helper."""
        for sub in ast.walk(no_funcao):
            if isinstance(sub, ast.Call):
                func = sub.func
                if (
                    isinstance(func, ast.Name)
                    and func.id == "_montar_clausula_subset_parlamentares"
                ):
                    return True
        return False

    assert _chama_helper(funcoes["_etapa_classificacao_c1_c2"])
    assert not _chama_helper(funcoes["_etapa_coleta"])
    assert not _chama_helper(funcoes["_etapa_etl"])


def test_sentinela_classificar_aceita_subset_kwarg() -> None:
    """S30.2: ``classificar`` expõe parâmetro ``parlamentares_subset``.

    Sentinela de assinatura: protege contra remoção/renomeação acidental
    do kwarg adicionado em S30.2 (consumido pelo pipeline_real).
    """
    import inspect

    from hemiciclo.modelos.classificador import classificar

    sig = inspect.signature(classificar)
    assert "parlamentares_subset" in sig.parameters
    param = sig.parameters["parlamentares_subset"]
    # Default é None (comportamento legado preservado).
    assert param.default is None


def test_dashboard_invoca_streamlit_run(
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    tmp_hemiciclo_home: Path,
) -> None:
    """``hemiciclo dashboard`` chama ``subprocess.run`` com o app correto."""
    chamadas: list[list[str]] = []

    def _fake_run(cmd: list[str], **_kwargs: object) -> object:
        chamadas.append(cmd)

        class _FakeCompleted:
            returncode = 0

        return _FakeCompleted()

    monkeypatch.setattr("hemiciclo.cli.shutil.which", lambda _bin: "/fake/streamlit")
    monkeypatch.setattr("hemiciclo.cli.subprocess.run", _fake_run)
    resultado = runner.invoke(app, ["dashboard", "--port", "8765"])
    assert resultado.exit_code == 0
    assert len(chamadas) == 1
    cmd = chamadas[0]
    assert cmd[0] == "/fake/streamlit"
    assert "run" in cmd
    assert any("--server.port=8765" in part for part in cmd)
    assert any("dashboard/app.py" in part.replace("\\", "/") for part in cmd)
