"""Testes end-to-end de exportação/importação de sessão (S35).

Cobrem o ciclo completo sem mocks:

- exportar sessão fixture -> zip -> importar em outro home -> ler artefatos
- adulterar zip -> importar com validação -> falhar
- workflow CLI ``hemiciclo sessao exportar`` -> ``hemiciclo sessao importar``
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hemiciclo.cli import app
from hemiciclo.sessao.exportador import (
    IntegridadeImportadaInvalida,
    exportar_zip,
    importar_zip,
)


def _criar_sessao_fixture(home: Path, id_sessao: str = "fix_e2e") -> Path:
    """Cria pasta de sessão completa com manifesto coerente."""
    sessao_dir = home / "sessoes" / id_sessao
    sessao_dir.mkdir(parents=True)
    (sessao_dir / "params.json").write_text(
        json.dumps({"topico": "aborto", "casas": ["camara"], "legislaturas": [57]}),
        encoding="utf-8",
    )
    (sessao_dir / "status.json").write_text(
        json.dumps({"id": id_sessao, "estado": "concluida", "progresso_pct": 100.0}),
        encoding="utf-8",
    )
    (sessao_dir / "relatorio_state.json").write_text(
        json.dumps({"n_props": 42, "n_parlamentares": 513, "top_a_favor": []}),
        encoding="utf-8",
    )
    raw = sessao_dir / "raw"
    raw.mkdir()
    (raw / "proposicoes.parquet").write_bytes(b"\x00PARQ_PROP\x00")

    artefatos = {
        rel: hashlib.sha256((sessao_dir / rel).read_bytes()).hexdigest()[:16]
        for rel in (
            "params.json",
            "status.json",
            "relatorio_state.json",
            "raw/proposicoes.parquet",
        )
    }
    manifesto = {
        "criado_em": "2026-04-28T00:00:00+00:00",
        "versao_pipeline": "1",
        "artefatos": artefatos,
        "limitacoes_conhecidas": ["S24b", "S27.1"],
    }
    (sessao_dir / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sessao_dir


def test_round_trip_exportar_importar(tmp_path: Path) -> None:
    """Round-trip exportar -> importar preserva todos os artefatos persistentes."""
    home_a = tmp_path / "pesquisador_a"
    home_b = tmp_path / "pesquisador_b"
    sessao_dir = _criar_sessao_fixture(home_a, id_sessao="fix_round")

    zip_path = tmp_path / "fix_round.zip"
    exportar_zip(sessao_dir, zip_path)

    (home_b / "sessoes").mkdir(parents=True)
    id_importado = importar_zip(zip_path, home_b, validar=True)
    assert id_importado == "fix_round"

    extraido = home_b / "sessoes" / "fix_round"
    # Cada artefato presente no original deve existir no destino com bytes idênticos.
    for rel in (
        "params.json",
        "status.json",
        "relatorio_state.json",
        "raw/proposicoes.parquet",
        "manifesto.json",
    ):
        original = (sessao_dir / rel).read_bytes()
        importado = (extraido / rel).read_bytes()
        assert original == importado, f"divergência em {rel}"


def test_zip_adulterado_falha_import(tmp_path: Path) -> None:
    """Modificar 1 byte de um artefato dentro do zip detectado pelo validador."""
    home_a = tmp_path / "atacante"
    sessao_dir = _criar_sessao_fixture(home_a, id_sessao="fix_adult")

    zip_path = tmp_path / "fix_adult.zip"
    exportar_zip(sessao_dir, zip_path)

    # Reconstrói zip trocando 1 byte do parquet de proposições.
    novo_zip = tmp_path / "fix_adult_mod.zip"
    with (
        zipfile.ZipFile(zip_path, "r") as src,
        zipfile.ZipFile(novo_zip, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.namelist():
            data = src.read(item)
            if item == "raw/proposicoes.parquet":
                # Flip último byte.
                data = data[:-1] + bytes([data[-1] ^ 0xFF])
            dst.writestr(item, data)

    home_b = tmp_path / "vitima"
    (home_b / "sessoes").mkdir(parents=True)
    with pytest.raises(IntegridadeImportadaInvalida, match="raw/proposicoes.parquet"):
        importar_zip(novo_zip, home_b, validar=True)


def test_workflow_cli_exportar_importar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI ``sessao exportar`` -> ``sessao importar`` funciona ponta-a-ponta."""
    home_a = tmp_path / "home_a"
    home_b = tmp_path / "home_b"
    home_a.mkdir()
    (home_a / "sessoes").mkdir()
    home_b.mkdir()
    (home_b / "sessoes").mkdir()
    _criar_sessao_fixture(home_a, id_sessao="fix_cli")

    runner = CliRunner()
    destino_zip = tmp_path / "fix_cli.zip"

    # Exporta a partir de home_a.
    monkeypatch.setenv("HEMICICLO_HOME", str(home_a))
    res_exp = runner.invoke(
        app,
        ["sessao", "exportar", "fix_cli", "--destino", str(destino_zip)],
    )
    assert res_exp.exit_code == 0, res_exp.stdout
    assert "sessao exportar" in res_exp.stdout
    assert "fix_cli.zip" in res_exp.stdout
    assert destino_zip.is_file()

    # Importa em home_b.
    monkeypatch.setenv("HEMICICLO_HOME", str(home_b))
    res_imp = runner.invoke(app, ["sessao", "importar", str(destino_zip)])
    assert res_imp.exit_code == 0, res_imp.stdout
    assert "sessao importar" in res_imp.stdout
    assert "fix_cli" in res_imp.stdout
    assert (home_b / "sessoes" / "fix_cli" / "params.json").is_file()
