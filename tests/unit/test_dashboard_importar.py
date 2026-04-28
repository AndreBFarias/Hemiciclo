"""Testes da página ``importar`` do dashboard (S35).

Carrega o app via ``streamlit.testing.v1.AppTest`` e força a rota
interna ``importar`` via ``session_state``. Cobre:

- render inicial (sem upload) -- header e uploader presentes
- mensagem de erro quando o zip uploaded é inválido
- mensagem de erro quando hash é adulterado
- sucesso quando round-trip é íntegro
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

_APP = "src/hemiciclo/dashboard/app.py"
_TIMEOUT = 15


@pytest.fixture
def home_vazia(tmp_hemiciclo_home: Path) -> Path:
    """Home temporária com pasta sessões vazia."""
    (tmp_hemiciclo_home / "sessoes").mkdir(parents=True, exist_ok=True)
    return tmp_hemiciclo_home


def _criar_zip_valido(tmp: Path, id_sessao: str = "imp_ok") -> Path:
    """Materializa zip íntegro pronto para importar."""
    fonte = tmp / "fonte" / id_sessao
    fonte.mkdir(parents=True)
    (fonte / "params.json").write_text('{"topico": "aborto"}', encoding="utf-8")
    (fonte / "status.json").write_text('{"estado": "concluida"}', encoding="utf-8")
    artefatos = {
        rel: hashlib.sha256((fonte / rel).read_bytes()).hexdigest()[:16]
        for rel in ("params.json", "status.json")
    }
    manifesto: dict[str, Any] = {
        "criado_em": "2026-04-28T00:00:00+00:00",
        "versao_pipeline": "1",
        "artefatos": artefatos,
        "limitacoes_conhecidas": [],
    }
    (fonte / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False), encoding="utf-8"
    )
    zip_path = tmp / f"{id_sessao}.zip"
    from hemiciclo.sessao.exportador import exportar_zip

    exportar_zip(fonte, zip_path)
    return zip_path


def test_pagina_importar_renderiza_uploader(home_vazia: Path) -> None:
    """Página ``importar`` mostra storytelling e uploader sem upload feito."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "importar"
    app.run()
    assert not app.exception
    saida = " ".join(md.value for md in app.markdown)
    assert "Importar sessão" in saida
    # st.file_uploader não vira widget testável simples no AppTest, mas a
    # ausência de exceção e o header renderizado bastam pra cobertura.


def test_pagina_importar_chama_importar_zip_em_sucesso(
    home_vazia: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stub de UploadedFile + click no botão dispara ``importar_zip``."""
    from hemiciclo.dashboard.paginas import importar as importar_mod

    zip_path = _criar_zip_valido(tmp_path)
    chamadas: list[tuple[Path, Path, bool]] = []

    def _fake_importar_zip(zp: Path, home: Path, *, validar: bool = True) -> str:
        chamadas.append((zp, home, validar))
        return "imp_ok"

    monkeypatch.setattr(importar_mod, "importar_zip", _fake_importar_zip)

    class _FakeUpload:
        name = "imp_ok.zip"

        def __init__(self, blob: bytes) -> None:
            self._blob = blob

        def getbuffer(self) -> bytes:
            return self._blob

    fake_upload = _FakeUpload(zip_path.read_bytes())

    chamadas_uploader: list[Any] = []

    def _fake_file_uploader(
        _label: str,
        *,
        type: list[str] | None = None,  # noqa: A002, ARG001 -- streamlit signature
        accept_multiple_files: bool = False,  # noqa: ARG001
        key: str | None = None,  # noqa: ARG001
        help: str | None = None,  # noqa: A002, ARG001
    ) -> Any:
        chamadas_uploader.append(_label)
        return fake_upload

    botao_clicks: list[str] = []

    def _fake_button(
        label: str,
        *,
        key: str | None = None,
        type: str | None = None,  # noqa: A002, ARG001
    ) -> bool:
        # Simula clique apenas no botão "Importar".
        if key == "importar_botao":
            botao_clicks.append(label)
            return True
        return False

    sucesso_msgs: list[str] = []

    def _fake_success(msg: str) -> None:
        sucesso_msgs.append(msg)

    erros: list[str] = []

    def _fake_error(msg: str) -> None:
        erros.append(msg)

    monkeypatch.setattr(importar_mod.st, "file_uploader", _fake_file_uploader)
    monkeypatch.setattr(importar_mod.st, "button", _fake_button)
    monkeypatch.setattr(importar_mod.st, "success", _fake_success)
    monkeypatch.setattr(importar_mod.st, "error", _fake_error)
    monkeypatch.setattr(importar_mod.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(importar_mod.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(importar_mod.st, "caption", lambda *a, **k: None)

    class _FakeColumn:
        def __enter__(self) -> _FakeColumn:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(importar_mod.st, "columns", lambda _spec: (_FakeColumn(), _FakeColumn()))

    from hemiciclo.config import Configuracao

    cfg = Configuracao()
    cfg.garantir_diretorios()
    importar_mod.render(cfg)

    assert len(chamadas) == 1
    assert chamadas[0][2] is True  # validar default
    assert sucesso_msgs
    assert "imp_ok" in sucesso_msgs[0]
    assert not erros


def test_pagina_importar_mostra_erro_em_zip_invalido(
    home_vazia: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload de zip corrompido emite ``st.error``."""
    from hemiciclo.dashboard.paginas import importar as importar_mod

    class _FakeUpload:
        name = "broken.zip"

        def getbuffer(self) -> bytes:
            return b"NOT_A_ZIP"

    monkeypatch.setattr(importar_mod.st, "file_uploader", lambda *a, **k: _FakeUpload())
    monkeypatch.setattr(importar_mod.st, "button", lambda *a, **k: k.get("key") == "importar_botao")
    monkeypatch.setattr(importar_mod.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(importar_mod.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(importar_mod.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(importar_mod.st, "success", lambda *a, **k: None)

    erros: list[str] = []
    monkeypatch.setattr(importar_mod.st, "error", lambda msg: erros.append(msg))

    class _FakeColumn:
        def __enter__(self) -> _FakeColumn:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(importar_mod.st, "columns", lambda _spec: (_FakeColumn(), _FakeColumn()))

    from hemiciclo.config import Configuracao

    cfg = Configuracao()
    cfg.garantir_diretorios()
    importar_mod.render(cfg)

    assert erros, "esperado pelo menos uma mensagem de erro"
    assert "inválido" in erros[0].lower() or "invalido" in erros[0].lower()


def test_pagina_importar_detecta_hash_adulterado(
    home_vazia: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hash divergente vira mensagem clara de integridade violada."""
    from hemiciclo.dashboard.paginas import importar as importar_mod

    zip_ok = _criar_zip_valido(tmp_path, id_sessao="adult_ui")

    # Reconstrói zip com bytes de params.json trocados.
    blob = zip_ok.read_bytes()
    novo_blob = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(blob), "r") as src,
        zipfile.ZipFile(novo_blob, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.namelist():
            data = src.read(item)
            if item == "params.json":
                data = b'{"topico": "MOD"}'
            dst.writestr(item, data)
    zip_adulterado = novo_blob.getvalue()

    class _FakeUpload:
        name = "adult_ui.zip"

        def getbuffer(self) -> bytes:
            return zip_adulterado

    monkeypatch.setattr(importar_mod.st, "file_uploader", lambda *a, **k: _FakeUpload())
    monkeypatch.setattr(importar_mod.st, "button", lambda *a, **k: k.get("key") == "importar_botao")
    monkeypatch.setattr(importar_mod.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(importar_mod.st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(importar_mod.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(importar_mod.st, "success", lambda *a, **k: None)

    erros: list[str] = []
    monkeypatch.setattr(importar_mod.st, "error", lambda msg: erros.append(msg))

    class _FakeColumn:
        def __enter__(self) -> _FakeColumn:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(importar_mod.st, "columns", lambda _spec: (_FakeColumn(), _FakeColumn()))

    from hemiciclo.config import Configuracao

    cfg = Configuracao()
    cfg.garantir_diretorios()
    importar_mod.render(cfg)

    assert erros, "esperado pelo menos uma mensagem de erro"
    assert "integridade" in erros[0].lower()
