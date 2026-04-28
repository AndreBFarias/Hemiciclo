"""Testes diretos das funções puras das páginas do dashboard.

Funções que não tocam Streamlit (ou o tocam apenas de forma mockável)
podem ser testadas sem AppTest, garantindo cobertura precisa de
``_slugify``, ``_ler_metadados_sessao`` e ``_coletar_sessoes``.

S38.4: ``_persistir_rascunho`` e ``_estimar_tempo_e_espaco`` foram
removidas junto com o stub legacy do botão "Iniciar pesquisa". O fluxo
real dispara :class:`hemiciclo.sessao.SessaoRunner`; ver testes da seção
``nova_pesquisa.render``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from hemiciclo.config import Configuracao
from hemiciclo.dashboard.paginas import lista_sessoes, nova_pesquisa

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# nova_pesquisa: slug
# ---------------------------------------------------------------------------


def test_slugify_remove_acentos_e_pontuacao() -> None:
    """Slugify normaliza acentos PT-BR e pontuação para ASCII seguro."""
    slug = nova_pesquisa._slugify("Reforma Tributária e o Café Açucarado!")
    assert slug == "reforma-tributaria-e-o-cafe-acucarado"


def test_slugify_topico_vazio_volta_default() -> None:
    """Slug de string em branco vira ``sem-topico``."""
    assert nova_pesquisa._slugify("   ") == "sem-topico"


def test_slugify_acentos_principais() -> None:
    """Cobre as classes de caracteres com substituição."""
    assert nova_pesquisa._slugify("àáâã éêè íì óôõò úùü ç") == ("aaaa-eee-ii-oooo-uuu-c")


# ---------------------------------------------------------------------------
# lista_sessoes: leitura de metadados em disco
# ---------------------------------------------------------------------------


def test_ler_metadados_sessao_sem_params_retorna_none(
    tmp_hemiciclo_home: Path,
) -> None:
    """Pasta sem params.json é ignorada pelo coletor."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta = cfg.sessoes_dir / "vazia"
    pasta.mkdir(parents=True)
    assert lista_sessoes._ler_metadados_sessao(pasta) is None


def test_ler_metadados_sessao_rascunho_marca_estado_criada(
    tmp_hemiciclo_home: Path,
) -> None:
    """Sessão sem status.json (rascunho) entra como estado 'criada'."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta = cfg.sessoes_dir / "rascunho_x"
    pasta.mkdir(parents=True)
    (pasta / "params.json").write_text(
        json.dumps(
            {
                "topico": "energia",
                "casas": ["camara"],
                "ufs": ["SP"],
            }
        ),
        encoding="utf-8",
    )
    meta = lista_sessoes._ler_metadados_sessao(pasta)
    assert meta is not None
    assert meta["topico"] == "energia"
    assert meta["estado"] == "criada"
    assert meta["progresso_pct"] == 0.0
    assert meta["iniciada_em"] == "(rascunho)"


def test_ler_metadados_sessao_com_status_completo(
    tmp_hemiciclo_home: Path,
) -> None:
    """Pasta com params.json e status.json devolve metadados completos."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta = cfg.sessoes_dir / "completa"
    pasta.mkdir(parents=True)
    (pasta / "params.json").write_text(
        json.dumps({"topico": "saúde", "casas": ["camara", "senado"]}),
        encoding="utf-8",
    )
    (pasta / "status.json").write_text(
        json.dumps(
            {
                "estado": "coletando",
                "progresso_pct": 38.0,
                "iniciada_em": "2026-04-28T12:00:00",
            }
        ),
        encoding="utf-8",
    )
    meta = lista_sessoes._ler_metadados_sessao(pasta)
    assert meta is not None
    assert meta["estado"] == "coletando"
    assert meta["progresso_pct"] == 38.0
    assert meta["iniciada_em"] == "2026-04-28T12:00:00"


def test_ler_metadados_sessao_params_corrompido_retorna_none(
    tmp_hemiciclo_home: Path,
) -> None:
    """JSON inválido em params.json é tratado e devolve None."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta = cfg.sessoes_dir / "ruim"
    pasta.mkdir(parents=True)
    (pasta / "params.json").write_text("{ não é json }", encoding="utf-8")
    assert lista_sessoes._ler_metadados_sessao(pasta) is None


def test_ler_metadados_sessao_status_corrompido_volta_para_criada(
    tmp_hemiciclo_home: Path,
) -> None:
    """status.json inválido é ignorado; estado vira 'criada'."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta = cfg.sessoes_dir / "status_corrompido"
    pasta.mkdir(parents=True)
    (pasta / "params.json").write_text(json.dumps({"topico": "x", "casas": []}), encoding="utf-8")
    (pasta / "status.json").write_text("not json", encoding="utf-8")
    meta = lista_sessoes._ler_metadados_sessao(pasta)
    assert meta is not None
    assert meta["estado"] == "criada"


def test_coletar_sessoes_vazio_quando_dir_nao_existe(tmp_path: Path, monkeypatch) -> None:
    """Sem diretório de sessões, retorna lista vazia."""
    monkeypatch.setenv("HEMICICLO_HOME", str(tmp_path / "nao_existe"))
    cfg = Configuracao()
    # Não chama garantir_diretorios -- propositadamente.
    assert lista_sessoes._coletar_sessoes(cfg) == []


def test_coletar_sessoes_ordena_e_filtra(tmp_hemiciclo_home: Path) -> None:
    """Coletor lista todas as pastas válidas, ignorando inválidas."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    pasta_a = cfg.sessoes_dir / "a"
    pasta_b = cfg.sessoes_dir / "b"
    pasta_invalida = cfg.sessoes_dir / "c"
    for pasta in (pasta_a, pasta_b, pasta_invalida):
        pasta.mkdir(parents=True)
    # Apenas a e b têm params.json.
    (pasta_a / "params.json").write_text(json.dumps({"topico": "a", "casas": []}), encoding="utf-8")
    (pasta_b / "params.json").write_text(json.dumps({"topico": "b", "casas": []}), encoding="utf-8")
    sessoes = lista_sessoes._coletar_sessoes(cfg)
    assert {s["topico"] for s in sessoes} == {"a", "b"}
    assert len(sessoes) == 2


# ---------------------------------------------------------------------------
# nova_pesquisa.render: caminho de submissão (mockando todos os widgets)
# ---------------------------------------------------------------------------


class _FakeForm:
    """Simula o context manager do ``st.form``."""

    def __enter__(self) -> _FakeForm:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakeCol:
    """Simula o context manager de colunas Streamlit."""

    def __enter__(self) -> _FakeCol:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _patches_form(
    mocker,
    topico: str,
    casas: list[str],
    legislaturas: list[int],
    camadas: list[str],
    submetido: bool,
) -> None:
    """Aplica todos os patches do Streamlit usados em ``nova_pesquisa.render``."""
    from datetime import date

    mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.markdown")
    mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.componentes.storytelling")
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.form",
        return_value=_FakeForm(),
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.columns",
        return_value=[_FakeCol(), _FakeCol()],
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.text_input",
        return_value=topico,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.multiselect",
        side_effect=[
            casas,  # Casas legislativas
            legislaturas,  # Legislaturas
            [],  # UFs
            [],  # Partidos
            camadas,  # Camadas de análise
        ],
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.date_input",
        return_value=(date(2015, 1, 1), date(2026, 4, 28)),
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.st.form_submit_button",
        return_value=submetido,
    )


class _FakeRunner:
    """Stub de :class:`SessaoRunner` que NÃO faz spawn de subprocess.

    Usado para validar o caminho de submissão sem rodar ``pipeline_real``
    de verdade (que demoraria ~30min, dispararia rede + ETL + ML).
    Padrão de mock baseado em ``tests/unit/test_sentinela.py:408-415``.
    """

    instancias: list[_FakeRunner] = []
    iniciar_excecao: Exception | None = None
    init_excecao: Exception | None = None

    def __init__(self, home: object, params: object, **_: object) -> None:
        if _FakeRunner.init_excecao is not None:
            raise _FakeRunner.init_excecao
        self.home = home
        self.params = params
        self.id_sessao = "fake-sessao-123"
        self.iniciar_chamado_com: str | None = None
        _FakeRunner.instancias.append(self)

    def iniciar(self, callable_path: str) -> int:
        if _FakeRunner.iniciar_excecao is not None:
            raise _FakeRunner.iniciar_excecao
        self.iniciar_chamado_com = callable_path
        return 99999


def _resetar_fake_runner() -> None:
    _FakeRunner.instancias = []
    _FakeRunner.iniciar_excecao = None
    _FakeRunner.init_excecao = None


def test_render_form_nao_submetido_retorna_cedo(
    mocker,
    tmp_hemiciclo_home: Path,
) -> None:
    """Render sem submissão não instancia SessaoRunner nem muda página."""
    _resetar_fake_runner()
    _patches_form(
        mocker,
        topico="aborto",
        casas=["Câmara"],
        legislaturas=[57],
        camadas=["Voto nominal (espinha dorsal)"],
        submetido=False,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner",
        _FakeRunner,
    )
    fake_session_state: dict[str, object] = {}
    mocker.patch.object(nova_pesquisa.st, "session_state", fake_session_state)
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.rerun")

    nova_pesquisa.render(Configuracao())

    assert _FakeRunner.instancias == []
    assert "pagina_ativa" not in fake_session_state
    fake_rerun.assert_not_called()


def test_render_form_submetido_dispara_runner_real(
    mocker,
    tmp_hemiciclo_home: Path,
) -> None:
    """Submissão válida instancia SessaoRunner e redireciona para sessao_detalhe."""
    _resetar_fake_runner()
    _patches_form(
        mocker,
        topico="reforma tributária",
        casas=["Câmara", "Senado"],
        legislaturas=[57],
        camadas=[
            "Regex/keywords (sempre confiável)",
            "Voto nominal (espinha dorsal)",
            "Embeddings semânticos (resgata implícitos)",
            "LLM opcional (anota nuance, custa horas)",
        ],
        submetido=True,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner",
        _FakeRunner,
    )
    fake_session_state: dict[str, object] = {}
    mocker.patch.object(nova_pesquisa.st, "session_state", fake_session_state)
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.rerun")
    fake_error = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.error")

    cfg = Configuracao()
    cfg.garantir_diretorios()
    nova_pesquisa.render(cfg)

    assert len(_FakeRunner.instancias) == 1
    runner = _FakeRunner.instancias[0]
    assert runner.home == cfg.home
    # ``params`` chegou como ParametrosBusca com tópico do form e ambas casas.
    assert runner.params.topico == "reforma tributária"  # type: ignore[attr-defined]
    casas_recebidas = [c.value for c in runner.params.casas]  # type: ignore[attr-defined]
    assert set(casas_recebidas) == {"camara", "senado"}
    # Callable disparado é o pipeline real (não dummy).
    assert runner.iniciar_chamado_com == "hemiciclo.sessao.pipeline:pipeline_real"
    # Session state apontando para sessao_detalhe.
    assert fake_session_state["sessao_id"] == "fake-sessao-123"
    assert fake_session_state["pagina_ativa"] == "sessao_detalhe"
    fake_rerun.assert_called_once()
    fake_error.assert_not_called()


def test_render_form_topico_invalido_mostra_erro(
    mocker,
    tmp_hemiciclo_home: Path,
) -> None:
    """Tópico vazio dispara ``st.error`` e NÃO instancia SessaoRunner."""
    _resetar_fake_runner()
    _patches_form(
        mocker,
        topico="",
        casas=["Câmara"],
        legislaturas=[57],
        camadas=["Voto nominal (espinha dorsal)"],
        submetido=True,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner",
        _FakeRunner,
    )
    fake_session_state: dict[str, object] = {}
    mocker.patch.object(nova_pesquisa.st, "session_state", fake_session_state)
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.rerun")
    fake_error = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.error")

    cfg = Configuracao()
    cfg.garantir_diretorios()
    nova_pesquisa.render(cfg)

    fake_error.assert_called()
    assert _FakeRunner.instancias == []
    assert "pagina_ativa" not in fake_session_state
    fake_rerun.assert_not_called()


def test_render_form_oserror_em_iniciar(
    mocker,
    tmp_hemiciclo_home: Path,
) -> None:
    """Falha em ``runner.iniciar`` (Popen) mostra erro PT-BR e mantém a página."""
    _resetar_fake_runner()
    _FakeRunner.iniciar_excecao = OSError("fork failed")
    _patches_form(
        mocker,
        topico="aborto",
        casas=["Câmara"],
        legislaturas=[57],
        camadas=["Voto nominal (espinha dorsal)"],
        submetido=True,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner",
        _FakeRunner,
    )
    fake_session_state: dict[str, object] = {}
    mocker.patch.object(nova_pesquisa.st, "session_state", fake_session_state)
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.rerun")
    fake_error = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.error")

    cfg = Configuracao()
    cfg.garantir_diretorios()
    nova_pesquisa.render(cfg)

    fake_error.assert_called()
    mensagem = " ".join(str(c.args) for c in fake_error.mock_calls)
    assert "Não foi possível iniciar o pipeline" in mensagem
    assert "pagina_ativa" not in fake_session_state
    fake_rerun.assert_not_called()


def test_render_form_oserror_em_init_runner(
    mocker,
    tmp_hemiciclo_home: Path,
) -> None:
    """Falha ao criar pasta da sessão (OSError no __init__) mostra erro amigável."""
    _resetar_fake_runner()
    _FakeRunner.init_excecao = OSError("Permission denied")
    _patches_form(
        mocker,
        topico="aborto",
        casas=["Câmara"],
        legislaturas=[57],
        camadas=["Voto nominal (espinha dorsal)"],
        submetido=True,
    )
    mocker.patch(
        "hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner",
        _FakeRunner,
    )
    fake_session_state: dict[str, object] = {}
    mocker.patch.object(nova_pesquisa.st, "session_state", fake_session_state)
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.rerun")
    fake_error = mocker.patch("hemiciclo.dashboard.paginas.nova_pesquisa.st.error")

    cfg = Configuracao()
    cfg.garantir_diretorios()
    nova_pesquisa.render(cfg)

    fake_error.assert_called()
    mensagem = " ".join(str(c.args) for c in fake_error.mock_calls)
    assert "Não foi possível criar a sessão" in mensagem
    assert "pagina_ativa" not in fake_session_state
    fake_rerun.assert_not_called()
