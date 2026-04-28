"""Persistencia do modelo base com integridade SHA256 (S28).

Salva o :class:`hemiciclo.modelos.base.ModeloBaseV1` em
``<dir>/base_v1.joblib`` (binário) acompanhado de
``<dir>/base_v1.meta.json`` com manifesto auditável:

- ``versão`` -- string ``"1"`` (incrementa em mudancas incompativeis).
- ``treinado_em`` -- ISO 8601 UTC.
- ``hash_sha256`` -- SHA256 do arquivo binário; conferido no carregamento.
- ``hash_amostra`` -- SHA256 dos ``hash_conteudo`` que entraram na amostra.
- ``n_componentes`` / ``feature_names`` -- shape do espaco induzido.

Quando :func:`carregar_modelo_base` detecta divergencia entre o SHA256
calculado e o registrado em ``meta.json``, levanta
:class:`IntegridadeViolada` -- nunca carregamos um artefato corrompido
silenciosamente. Versao incompatível tambem aborta.

Decisão tecnica: usamos ``joblib`` em vez do serializador stdlib porque
o sklearn recomenda ``joblib`` para artefatos de PCA (compressao + zero-copy
para arrays numpy grandes). O formato e stdlib-compatível internamente.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import joblib

from hemiciclo.modelos.base import ModeloBaseV1

_NOME_BIN = "base_v1.joblib"
_NOME_META = "base_v1.meta.json"


class IntegridadeViolada(Exception):  # noqa: N818 -- nome do contrato em PT-BR
    """Hash do artefato divergente ou versão incompatível."""


def _sha256_arquivo(path: Path) -> str:
    """SHA256 streaming (chunks de 8 KiB) do conteudo binário."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def salvar_modelo_base(modelo: ModeloBaseV1, dir_destino: Path) -> dict[str, object]:
    """Serializa ``modelo`` em ``dir_destino`` + escreve manifesto JSON.

    Retorna o manifesto (dict). O manifesto e escrito em UTF-8 com
    indentacao 2 (legivel por humanos para auditoria).
    """
    dir_destino.mkdir(parents=True, exist_ok=True)
    caminho_bin = dir_destino / _NOME_BIN
    caminho_meta = dir_destino / _NOME_META

    joblib.dump(modelo, caminho_bin)

    hash_arq = _sha256_arquivo(caminho_bin)
    meta: dict[str, object] = {
        "versao": modelo.versao,
        "treinado_em": modelo.treinado_em.astimezone(UTC).isoformat(),
        "hash_sha256": hash_arq,
        "hash_amostra": modelo.hash_amostra,
        "n_componentes": modelo.n_componentes,
        "feature_names": list(modelo.feature_names),
        "salvo_em": datetime.now(UTC).isoformat(),
    }
    caminho_meta.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return meta


def carregar_modelo_base(dir_origem: Path) -> ModeloBaseV1:
    """Carrega o modelo validando integridade.

    Raises:
        FileNotFoundError: arquivos ausentes.
        IntegridadeViolada: versão incompatível ou hash divergente.
    """
    caminho_bin = dir_origem / _NOME_BIN
    caminho_meta = dir_origem / _NOME_META

    if not caminho_bin.exists() or not caminho_meta.exists():
        raise FileNotFoundError(
            f"Modelo base ausente em {dir_origem} (esperados '{_NOME_BIN}' e '{_NOME_META}')."
        )

    meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
    versao = meta.get("versao")
    if versao != "1":
        raise IntegridadeViolada(
            f"Versao incompatível: meta='{versao}' (esperado '1'). Re-treine o modelo base."
        )

    hash_atual = _sha256_arquivo(caminho_bin)
    hash_esperado = meta.get("hash_sha256")
    if hash_atual != hash_esperado:
        raise IntegridadeViolada(
            f"Hash divergente em {caminho_bin.name}: "
            f"calculado={hash_atual} != registrado={hash_esperado}. "
            f"Artefato corrompido; re-treine o modelo base."
        )

    return cast(ModeloBaseV1, joblib.load(caminho_bin))


def info_modelo_base(dir_origem: Path) -> dict[str, object] | None:
    """Le apenas o ``meta.json`` sem desserializar o binário.

    Retorna ``None`` se o manifesto não existe. Util para CLI ``info``
    sem custo de carregar o modelo.
    """
    caminho_meta = dir_origem / _NOME_META
    if not caminho_meta.exists():
        return None
    meta = json.loads(caminho_meta.read_text(encoding="utf-8"))
    return cast(dict[str, object], meta)
