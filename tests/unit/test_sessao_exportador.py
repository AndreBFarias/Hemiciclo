"""Testes do módulo :mod:`hemiciclo.sessao.exportador` (S35).

Substitui os testes do stub S29 (round-trip simples) por testes que
exercitam:

- exclusão de artefatos efêmeros (``dados.duckdb``, ``pid.lock``,
  ``log.txt``, ``modelos_locais/``);
- inclusão obrigatória de ``manifesto.json`` quando presente;
- validação real de hashes contra o manifesto na importação;
- detecção de adulteração;
- bypass via ``validar=False``;
- sufixo automático em colisão de id.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from hemiciclo.sessao.exportador import (
    IntegridadeImportadaInvalida,
    _artefatos_persistentes,
    exportar_zip,
    exportar_zip_bytes,
    importar_zip,
)


def _materializar_sessao(sessao_dir: Path) -> dict[str, str]:
    """Cria pasta de sessão com artefatos reais + manifesto coerente.

    Retorna o dict de manifesto para reuso nos testes.
    """
    sessao_dir.mkdir(parents=True)
    (sessao_dir / "params.json").write_text('{"topico": "aborto"}', encoding="utf-8")
    (sessao_dir / "status.json").write_text('{"estado": "concluida"}', encoding="utf-8")
    (sessao_dir / "relatorio_state.json").write_text('{"n_props": 87}', encoding="utf-8")
    (sessao_dir / "classificacao_c1_c2.json").write_text('{"top_a_favor": []}', encoding="utf-8")
    raw = sessao_dir / "raw"
    raw.mkdir()
    (raw / "proposicoes.parquet").write_bytes(b"PARQUET_PROP")
    (raw / "votos.parquet").write_bytes(b"PARQUET_VOT")

    # Efêmeros / regeneráveis -- devem ser excluídos do zip.
    (sessao_dir / "dados.duckdb").write_bytes(b"DUCKBIN")
    (sessao_dir / "pid.lock").write_text("12345\n", encoding="utf-8")
    (sessao_dir / "log.txt").write_text("loglog\n", encoding="utf-8")
    modelos = sessao_dir / "modelos_locais"
    modelos.mkdir()
    (modelos / "ajuste.pkl").write_bytes(b"PKL")

    # Manifesto coerente: SHA256 16-char dos artefatos persistentes.
    artefatos: dict[str, str] = {}
    for rel in [
        "params.json",
        "status.json",
        "relatorio_state.json",
        "classificacao_c1_c2.json",
        "raw/proposicoes.parquet",
        "raw/votos.parquet",
        "dados.duckdb",  # vai pro manifesto, mas NÃO pro zip
    ]:
        caminho = sessao_dir / rel
        artefatos[rel] = hashlib.sha256(caminho.read_bytes()).hexdigest()[:16]
    manifesto = {
        "criado_em": "2026-04-28T00:00:00+00:00",
        "versao_pipeline": "1",
        "artefatos": artefatos,
        "limitacoes_conhecidas": ["S24b"],
    }
    (sessao_dir / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return artefatos


# ---------------------------------------------------------------------------
# exportar_zip
# ---------------------------------------------------------------------------


def test_exportar_gera_zip(tmp_path: Path) -> None:
    """``exportar_zip`` produz arquivo válido com tamanho > 0."""
    sessao_dir = tmp_path / "sessoes" / "abc"
    _materializar_sessao(sessao_dir)
    destino = tmp_path / "abc.zip"

    retorno = exportar_zip(sessao_dir, destino)
    assert retorno == destino
    assert destino.is_file()
    assert destino.stat().st_size > 0
    with zipfile.ZipFile(destino, "r") as zf:
        assert zf.testzip() is None


def test_exportar_exclui_artefatos_efemeros(tmp_path: Path) -> None:
    """Zip exclui ``dados.duckdb``, ``pid.lock``, ``log.txt``, ``modelos_locais/``."""
    sessao_dir = tmp_path / "sessoes" / "x"
    _materializar_sessao(sessao_dir)
    destino = tmp_path / "x.zip"
    exportar_zip(sessao_dir, destino)

    with zipfile.ZipFile(destino, "r") as zf:
        nomes = set(zf.namelist())

    assert "dados.duckdb" not in nomes
    assert "pid.lock" not in nomes
    assert "log.txt" not in nomes
    assert not any(n.startswith("modelos_locais") for n in nomes)


def test_exportar_inclui_manifesto(tmp_path: Path) -> None:
    """Zip preserva ``manifesto.json`` e parquets de coleta."""
    sessao_dir = tmp_path / "sessoes" / "x"
    _materializar_sessao(sessao_dir)
    destino = tmp_path / "x.zip"
    exportar_zip(sessao_dir, destino)

    with zipfile.ZipFile(destino, "r") as zf:
        nomes = set(zf.namelist())

    assert "manifesto.json" in nomes
    assert "params.json" in nomes
    assert "status.json" in nomes
    assert "relatorio_state.json" in nomes
    assert "classificacao_c1_c2.json" in nomes
    assert "raw/proposicoes.parquet" in nomes
    assert "raw/votos.parquet" in nomes


def test_exportar_zip_pasta_inexistente_levanta(tmp_path: Path) -> None:
    """Pasta-fonte ausente -> ``FileNotFoundError``."""
    with pytest.raises(FileNotFoundError, match="diretório válido"):
        exportar_zip(tmp_path / "nao_existe", tmp_path / "x.zip")


def test_exportar_zip_bytes_em_memoria(tmp_path: Path) -> None:
    """Variante in-memory devolve bytes do zip sem escrever em disco."""
    sessao_dir = tmp_path / "sessoes" / "y"
    _materializar_sessao(sessao_dir)
    blob = exportar_zip_bytes(sessao_dir)

    assert isinstance(blob, bytes)
    assert len(blob) > 0
    import io as _io

    with zipfile.ZipFile(_io.BytesIO(blob), "r") as zf:
        nomes = set(zf.namelist())
    assert "manifesto.json" in nomes
    assert "dados.duckdb" not in nomes


def test_artefatos_persistentes_ordena_deterministicamente(tmp_path: Path) -> None:
    """Helper retorna lista ordenada (path determinístico)."""
    sessao_dir = tmp_path / "sessoes" / "ord"
    _materializar_sessao(sessao_dir)
    artefatos = _artefatos_persistentes(sessao_dir)
    assert artefatos == sorted(artefatos)
    nomes = {a.relative_to(sessao_dir).as_posix() for a in artefatos}
    assert "manifesto.json" in nomes
    assert "raw/proposicoes.parquet" in nomes
    assert "dados.duckdb" not in nomes


# ---------------------------------------------------------------------------
# importar_zip
# ---------------------------------------------------------------------------


def test_importar_extrai_corretamente(tmp_path: Path) -> None:
    """``importar_zip`` recria pasta com todos os artefatos do zip."""
    origem = tmp_path / "src" / "minha_sessao"
    _materializar_sessao(origem)
    zip_path = tmp_path / "minha_sessao.zip"
    exportar_zip(origem, zip_path)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)

    id_importado = importar_zip(zip_path, home)
    assert id_importado == "minha_sessao"
    extraido = home / "sessoes" / "minha_sessao"
    assert (extraido / "params.json").exists()
    assert (extraido / "status.json").exists()
    assert (extraido / "manifesto.json").exists()
    assert (extraido / "raw" / "proposicoes.parquet").exists()


def test_importar_valida_hash_ok(tmp_path: Path) -> None:
    """Round-trip exportar -> importar com ``validar=True`` não levanta."""
    origem = tmp_path / "src" / "ok"
    _materializar_sessao(origem)
    zip_path = tmp_path / "ok.zip"
    exportar_zip(origem, zip_path)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)

    id_importado = importar_zip(zip_path, home, validar=True)
    assert id_importado == "ok"


def test_importar_recusa_hash_adulterado(tmp_path: Path) -> None:
    """Adulteração de byte em artefato detectada via SHA256."""
    origem = tmp_path / "src" / "adult"
    _materializar_sessao(origem)
    zip_path = tmp_path / "adult.zip"
    exportar_zip(origem, zip_path)

    # Reabre o zip e troca o conteúdo do params.json sem mexer no manifesto.
    novo_zip = tmp_path / "adult_mod.zip"
    with (
        zipfile.ZipFile(zip_path, "r") as src,
        zipfile.ZipFile(novo_zip, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.namelist():
            data = src.read(item)
            if item == "params.json":
                data = b'{"topico": "ADULTERADO"}'
            dst.writestr(item, data)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)
    with pytest.raises(IntegridadeImportadaInvalida, match="params.json"):
        importar_zip(novo_zip, home, validar=True)


def test_importar_sem_validar_aceita_adulterado(tmp_path: Path) -> None:
    """``validar=False`` não recalcula hashes -- útil pra debug."""
    origem = tmp_path / "src" / "skip"
    _materializar_sessao(origem)
    zip_path = tmp_path / "skip.zip"
    exportar_zip(origem, zip_path)

    novo_zip = tmp_path / "skip_mod.zip"
    with (
        zipfile.ZipFile(zip_path, "r") as src,
        zipfile.ZipFile(novo_zip, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for item in src.namelist():
            data = src.read(item)
            if item == "params.json":
                data = b'{"topico": "ADULTERADO"}'
            dst.writestr(item, data)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)
    id_importado = importar_zip(novo_zip, home, validar=False)
    # ``novo_zip`` tem stem ``skip_mod`` -- id derivado do nome do zip.
    assert id_importado == "skip_mod"


def test_importar_id_colidindo_gera_sufixo(tmp_path: Path) -> None:
    """Importar duas vezes a mesma sessão produz ``<id>``, ``<id>_2``, ``<id>_3``."""
    origem = tmp_path / "src" / "colide"
    _materializar_sessao(origem)
    zip_path = tmp_path / "colide.zip"
    exportar_zip(origem, zip_path)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)
    primeiro = importar_zip(zip_path, home)
    segundo = importar_zip(zip_path, home)
    terceiro = importar_zip(zip_path, home)

    assert primeiro == "colide"
    assert segundo == "colide_2"
    assert terceiro == "colide_3"
    assert (home / "sessoes" / "colide").is_dir()
    assert (home / "sessoes" / "colide_2").is_dir()
    assert (home / "sessoes" / "colide_3").is_dir()


def test_importar_sem_manifesto_nao_falha(tmp_path: Path) -> None:
    """Sessão sem ``manifesto.json`` é importada (skip silencioso)."""
    sessao_dir = tmp_path / "src" / "sem_manifesto"
    sessao_dir.mkdir(parents=True)
    (sessao_dir / "params.json").write_text("{}", encoding="utf-8")
    (sessao_dir / "status.json").write_text("{}", encoding="utf-8")

    zip_path = tmp_path / "sem_manifesto.zip"
    exportar_zip(sessao_dir, zip_path)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)
    id_importado = importar_zip(zip_path, home, validar=True)
    assert id_importado == "sem_manifesto"


def test_importar_zip_inexistente_levanta(tmp_path: Path) -> None:
    """Zip-fonte ausente -> ``FileNotFoundError``."""
    with pytest.raises(FileNotFoundError, match="zip não existe"):
        importar_zip(tmp_path / "nao_existe.zip", tmp_path / "home")


def test_importar_manifesto_corrompido_levanta(tmp_path: Path) -> None:
    """``manifesto.json`` com JSON inválido -> ``IntegridadeImportadaInvalida``."""
    sessao_dir = tmp_path / "src" / "json_quebrado"
    sessao_dir.mkdir(parents=True)
    (sessao_dir / "params.json").write_text("{}", encoding="utf-8")
    (sessao_dir / "manifesto.json").write_text("{NAO EH JSON", encoding="utf-8")

    zip_path = tmp_path / "json_quebrado.zip"
    exportar_zip(sessao_dir, zip_path)

    home = tmp_path / "destino"
    (home / "sessoes").mkdir(parents=True)
    with pytest.raises(IntegridadeImportadaInvalida, match="corrompido"):
        importar_zip(zip_path, home, validar=True)
