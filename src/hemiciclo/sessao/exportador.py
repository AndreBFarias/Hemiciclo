"""Exportação/importação de Sessão de Pesquisa em ZIP -- versão real (S35).

Substitui o stub da S29. Esta versão integra com o ``manifesto.json``
gerado em S30 (:mod:`hemiciclo.sessao.pipeline`) para verificar a
integridade dos artefatos importados via SHA256 truncado em 16 chars
(precedente S24/S25/S26/S30 confirmado em S25.1).

Filosofia
---------

O zip exclui artefatos pesados/regeneráveis -- ``dados.duckdb`` (refeito
a partir dos parquets via :mod:`hemiciclo.etl.consolidador`),
``modelos_locais/`` (refeito por re-projeção C3), ``pid.lock`` (efêmero)
e ``log.txt`` (efêmero). Inclui apenas o que importa para reabrir a
análise em outra máquina: ``params.json``, ``status.json``,
``manifesto.json``, parquets de dados (``raw/``), ``relatorio_state.json``
e ``classificacao_c1_c2.json``.

A validação compara apenas os artefatos do manifesto que estão
presentes no zip extraído. Entradas que apontam para arquivos
intencionalmente excluídos (como ``dados.duckdb``) são ignoradas.
Entradas presentes com hash divergente levantam
:class:`IntegridadeImportadaInvalida`.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

# Subdiretórios cujo conteúdo nunca entra no zip (cache pesado).
_EXCLUIR_DO_ZIP: frozenset[str] = frozenset({"modelos_locais"})

# Arquivos cujo nome (basename) nunca entra no zip.
_EXCLUIR_ARQUIVOS: frozenset[str] = frozenset({"dados.duckdb", "pid.lock", "log.txt"})


class IntegridadeImportadaInvalida(Exception):  # noqa: N818 -- nome do contrato em PT-BR (precedente: IntegridadeViolada em persistencia_modelo)
    """SHA256 de artefato importado não bate com o registrado no manifesto.

    Levantada por :func:`importar_zip` quando ``validar=True`` e algum
    arquivo do zip extraído tem hash diferente do declarado em
    ``manifesto.json``. Mensagem inclui o caminho relativo do artefato
    e os dois hashes (calculado vs esperado) para diagnóstico.
    """


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------


def exportar_zip(sessao_dir: Path, destino: Path) -> Path:
    """Zipa a pasta ``sessao_dir`` em ``destino`` (caminho do .zip resultante).

    Exclui caches pesados/regeneráveis e arquivos efêmeros (ver módulo
    docstring). Inclui ``manifesto.json`` quando presente -- ele é a
    cola que :func:`importar_zip` usa para validar integridade.

    Args:
        sessao_dir: Pasta da sessão (ex.: ``<home>/sessoes/<id>/``).
        destino: Caminho do arquivo ``.zip`` a criar.

    Returns:
        ``destino`` (mesmo path passado, retornado pra encadeamento).

    Raises:
        FileNotFoundError: ``sessao_dir`` não existe ou não é diretório.
    """
    if not sessao_dir.exists() or not sessao_dir.is_dir():
        msg = f"sessao_dir não é um diretório válido: {sessao_dir}"
        raise FileNotFoundError(msg)

    artefatos = _artefatos_persistentes(sessao_dir)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arq in artefatos:
            arcname = arq.relative_to(sessao_dir).as_posix()
            zf.write(arq, arcname=arcname)
    return destino


def exportar_zip_bytes(sessao_dir: Path) -> bytes:
    """Variante in-memory de :func:`exportar_zip`.

    Útil para o ``st.download_button`` do dashboard, que precisa dos
    bytes do zip sem tocar em disco. Mesma seleção de artefatos da
    função canônica.

    Args:
        sessao_dir: Pasta da sessão.

    Returns:
        Bytes do zip pronto para download.

    Raises:
        FileNotFoundError: ``sessao_dir`` não existe ou não é diretório.
    """
    if not sessao_dir.exists() or not sessao_dir.is_dir():
        msg = f"sessao_dir não é um diretório válido: {sessao_dir}"
        raise FileNotFoundError(msg)

    artefatos = _artefatos_persistentes(sessao_dir)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arq in artefatos:
            arcname = arq.relative_to(sessao_dir).as_posix()
            zf.write(arq, arcname=arcname)
    return buffer.getvalue()


def _artefatos_persistentes(sessao_dir: Path) -> list[Path]:
    """Lista artefatos persistentes da sessão (o que entra no zip).

    Inclui:

    - ``params.json``, ``status.json``, ``manifesto.json``,
      ``relatorio_state.json``, ``classificacao_c1_c2.json``,
      ``c3_status.json`` (todos da raiz da sessão).
    - Qualquer ``*.parquet`` fora de ``modelos_locais/``.

    Exclui:

    - ``dados.duckdb`` (regenerado por consolidador).
    - ``pid.lock`` (efêmero).
    - ``log.txt`` (efêmero).
    - Tudo dentro de ``modelos_locais/``.

    Returns:
        Lista ordenada (path determinístico) de arquivos a zipar.
    """
    nomes_inclusos: frozenset[str] = frozenset(
        {
            "params.json",
            "status.json",
            "manifesto.json",
            "relatorio_state.json",
            "classificacao_c1_c2.json",
            "c3_status.json",
        }
    )
    artefatos: list[Path] = []
    for arq in sessao_dir.rglob("*"):
        if not arq.is_file():
            continue
        relativo = arq.relative_to(sessao_dir)
        partes = {parte.replace("\\", "/") for parte in relativo.parts}
        if partes & _EXCLUIR_DO_ZIP:
            continue
        if relativo.name in _EXCLUIR_ARQUIVOS:
            continue
        if relativo.name in nomes_inclusos:
            artefatos.append(arq)
            continue
        if arq.suffix == ".parquet":
            artefatos.append(arq)
    return sorted(artefatos)


# ---------------------------------------------------------------------------
# Importar
# ---------------------------------------------------------------------------


def importar_zip(zip_path: Path, home: Path, *, validar: bool = True) -> str:
    """Extrai ``zip_path`` em ``<home>/sessoes/<id>/`` e devolve o id.

    O ``id`` da sessão é derivado do nome do arquivo (sem ``.zip``). Se
    a pasta destino já existe, sufixa ``_2``, ``_3``, ... até achar um
    nome livre.

    Quando ``validar=True`` (default), recalcula SHA256 de cada
    artefato extraído e compara com o registrado em ``manifesto.json``.
    Hash divergente levanta :class:`IntegridadeImportadaInvalida`.

    Quando o zip não contém ``manifesto.json`` ou quando ``validar=False``,
    a etapa de validação é pulada com aviso silencioso (sessões de
    versões anteriores podem não ter manifesto). Use ``--sem-validar``
    no CLI para forçar o pulo.

    Args:
        zip_path: Caminho do .zip exportado por :func:`exportar_zip`.
        home: Raiz do Hemiciclo (``~/hemiciclo/`` no caso real).
        validar: Se ``True``, valida hashes contra ``manifesto.json``.

    Returns:
        Identificador final da sessão importada (com sufixo ``_<n>`` se
        houve colisão).

    Raises:
        FileNotFoundError: ``zip_path`` não existe.
        zipfile.BadZipFile: ``zip_path`` não é zip válido.
        IntegridadeImportadaInvalida: ``validar=True`` e algum hash não bate.
    """
    if not zip_path.exists():
        msg = f"zip não existe: {zip_path}"
        raise FileNotFoundError(msg)

    id_base = zip_path.stem
    id_sessao = _resolver_id_unico(home, id_base)
    destino = home / "sessoes" / id_sessao
    destino.mkdir(parents=True, exist_ok=False)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(destino)

    if not validar:
        return id_sessao

    manifesto_path = destino / "manifesto.json"
    if not manifesto_path.exists():
        return id_sessao

    try:
        manifesto: dict[str, Any] = json.loads(manifesto_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"manifesto.json corrompido em {manifesto_path}: {exc}"
        raise IntegridadeImportadaInvalida(msg) from exc

    _validar_manifesto(destino, manifesto)
    return id_sessao


def _resolver_id_unico(home: Path, id_base: str) -> str:
    """Retorna ``id_base`` ou ``<id_base>_<n>`` se já existir colisão.

    Procura ``home/sessoes/<id_base>``, ``home/sessoes/<id_base>_2``,
    ``..._3`` etc. até achar um nome livre. Sem limite teórico -- na
    prática, cidadão raramente importa a mesma sessão centenas de vezes.
    """
    sessoes_dir = home / "sessoes"
    if not (sessoes_dir / id_base).exists():
        return id_base
    n = 2
    while (sessoes_dir / f"{id_base}_{n}").exists():
        n += 1
    return f"{id_base}_{n}"


def _validar_manifesto(extraido_dir: Path, manifesto: dict[str, Any]) -> None:
    """Recalcula SHA256 de cada artefato extraído e compara com o manifesto.

    Considera apenas artefatos do manifesto que estão presentes na
    pasta extraída. Arquivos do manifesto ausentes (como
    ``dados.duckdb``, intencionalmente excluído do zip) são pulados
    silenciosamente -- o manifesto descreve a sessão original, não o
    zip.

    Args:
        extraido_dir: Pasta com o zip já extraído.
        manifesto: Dict carregado do ``manifesto.json``.

    Raises:
        IntegridadeImportadaInvalida: Algum artefato presente tem hash
            que não bate com o esperado.
    """
    artefatos: dict[str, str] = dict(manifesto.get("artefatos", {}) or {})
    for rel_path, hash_esperado in artefatos.items():
        caminho = extraido_dir / rel_path
        if not caminho.is_file():
            # Artefato do manifesto não foi extraído (excluído do zip).
            # Coerente: dados.duckdb não vai no zip mas está no manifesto.
            continue
        sha = hashlib.sha256(caminho.read_bytes()).hexdigest()[:16]
        if sha != hash_esperado:
            msg = f"Hash divergente em {rel_path}: calculado={sha} esperado={hash_esperado}"
            raise IntegridadeImportadaInvalida(msg)
