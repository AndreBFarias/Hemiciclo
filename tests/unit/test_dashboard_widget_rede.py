"""Testes do widget Streamlit que embeda o grafo pyvis (S32).

Mockamos ``streamlit`` em parte: ``st.components.v1.html`` é o que
precisamos espionar. Os outros (``info``, ``warning``) basta que sejam
chamáveis sem levantar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hemiciclo.dashboard.widgets import rede

if TYPE_CHECKING:
    from pathlib import Path


def test_renderizar_rede_chama_components_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HTML existente -> ``st.components.v1.html`` invocado com o conteúdo."""
    html = tmp_path / "grafo.html"
    html.write_text("<html><body>OI</body></html>", encoding="utf-8")

    chamadas: list[dict[str, object]] = []

    def _fake_html(conteudo: str, **kwargs: object) -> None:
        chamadas.append({"conteudo": conteudo, "kwargs": kwargs})

    monkeypatch.setattr(rede.st.components.v1, "html", _fake_html)

    rede.renderizar_rede(html, altura=500)

    assert len(chamadas) == 1
    assert "OI" in str(chamadas[0]["conteudo"])
    assert chamadas[0]["kwargs"].get("height") == 500


def test_html_inexistente_mostra_aviso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Path inexistente -> ``st.info`` chamado com mensagem clara."""
    chamadas_info: list[str] = []
    chamadas_html: list[object] = []

    def _fake_info(msg: str) -> None:
        chamadas_info.append(msg)

    def _fake_html(*args: object, **kwargs: object) -> None:
        chamadas_html.append((args, kwargs))

    monkeypatch.setattr(rede.st, "info", _fake_info)
    monkeypatch.setattr(rede.st.components.v1, "html", _fake_html)

    rede.renderizar_rede(tmp_path / "fantasma.html")

    assert len(chamadas_info) == 1
    # S38.6: mensagem cidadã sem comando CLI exposto.
    assert "articulação política" in chamadas_info[0].lower()
    assert "hemiciclo rede" not in chamadas_info[0].lower()
    assert chamadas_html == []


def test_oserror_em_leitura_chama_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError ao ler HTML -> ``st.warning`` invocado, sem quebrar."""
    html = tmp_path / "g.html"
    html.write_text("<html></html>", encoding="utf-8")

    avisos: list[str] = []

    def _fake_warning(msg: str) -> None:
        avisos.append(msg)

    def _fake_read_text(*_args: object, **_kwargs: object) -> str:
        raise OSError("simulado")

    monkeypatch.setattr(rede.st, "warning", _fake_warning)
    monkeypatch.setattr("pathlib.Path.read_text", _fake_read_text)
    rede.renderizar_rede(html)
    assert len(avisos) == 1
    assert "g.html" in avisos[0]


def test_altura_configuravel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Altura passada vai para ``height`` do components.html."""
    html = tmp_path / "g.html"
    html.write_text("<html></html>", encoding="utf-8")

    capturado: dict[str, object] = {}

    def _fake_html(_conteudo: str, **kwargs: object) -> None:
        capturado.update(kwargs)

    monkeypatch.setattr(rede.st.components.v1, "html", _fake_html)
    rede.renderizar_rede(html, altura=850)
    assert capturado.get("height") == 850
