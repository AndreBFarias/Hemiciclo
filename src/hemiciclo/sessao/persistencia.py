"""Persistência da Sessão de Pesquisa em disco.

Cada sessão é uma pasta autocontida em ``<home>/sessoes/<id>/`` com:

- ``params.json`` -- :class:`ParametrosBusca` serializado
- ``status.json`` -- :class:`StatusSessao`, atualizado pelo subprocess
- ``pid.lock`` -- PID + ISO timestamp (uma linha cada)
- ``log.txt`` -- saída agregada do pipeline (escrita pelo runner)
- ``manifesto.json`` -- hashes dos artefatos (preenchido em S30/S35)

Toda escrita é **atômica** via ``tempfile.NamedTemporaryFile + Path.replace``
(precedente em :mod:`hemiciclo.coleta.checkpoint`). Sobrevive a ``kill -9``:
ou o arquivo final foi escrito inteiro, ou ainda contém a versão anterior.

Cobre I3 (determinismo via slug + timestamp), I6 (Pydantic estrito sem dicts
soltos), I7 (tipagem precisa), do VALIDATOR_BRIEF.
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from hemiciclo.sessao.modelo import ParametrosBusca, StatusSessao

# Caracteres permitidos em slug de id de sessão. Exclui acentos e símbolos.
_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def _slugificar(texto: str) -> str:
    """Converte texto livre em slug ASCII ``[a-z0-9_]+``.

    Útil pra construir id de sessão a partir do tópico do usuário sem
    introduzir acentos ou separadores ambíguos no nome de pasta.
    """
    base = _SLUG_RE.sub("_", texto.lower()).strip("_")
    return base or "sessao"


def gerar_id_sessao(params: ParametrosBusca) -> str:
    """Gera id único da sessão como ``<slug-do-topico>_<UTC-timestamp>_<rand>``.

    O timestamp tem precisão de microssegundos. Windows tem relógio com
    resolução de ~15ms, então adicionamos sufixo aleatório de 3 bytes hex
    pra garantir unicidade em chamadas consecutivas.

    Returns:
        Identificador ASCII seguro pra path (ex.: ``aborto_20260428T120015_123456_a3f1c9``).
    """
    import secrets

    slug = _slugificar(params.topico)
    agora = datetime.now(UTC)
    carimbo = agora.strftime("%Y%m%dT%H%M%S_%f")
    sufixo = secrets.token_hex(3)
    return f"{slug}_{carimbo}_{sufixo}"


def caminho_sessao(home: Path, id_sessao: str) -> Path:
    """Resolve o caminho canônico ``<home>/sessoes/<id_sessao>/``."""
    return home / "sessoes" / id_sessao


def _escrever_json_atomico(payload: dict[str, object], destino: Path) -> None:
    """Serializa ``payload`` em JSON UTF-8 indentado via tmpfile + replace."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destino.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(destino)


def salvar_params(params: ParametrosBusca, path: Path) -> None:
    """Persiste :class:`ParametrosBusca` em ``path`` via escrita atômica."""
    _escrever_json_atomico(params.model_dump(mode="json"), path)


def carregar_params(path: Path) -> ParametrosBusca | None:
    """Carrega :class:`ParametrosBusca` de ``path`` ou retorna ``None``.

    Retorna ``None`` se o arquivo não existe ou está corrompido (JSON
    inválido / payload incompatível com o schema). Logar é
    responsabilidade do chamador.
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            dados = json.load(f)
        return ParametrosBusca.model_validate(dados)
    except (json.JSONDecodeError, ValueError):
        return None


def salvar_status(status: StatusSessao, path: Path) -> None:
    """Persiste :class:`StatusSessao` em ``path`` via escrita atômica."""
    _escrever_json_atomico(status.model_dump(mode="json"), path)


def carregar_status(path: Path) -> StatusSessao | None:
    """Carrega :class:`StatusSessao` de ``path`` ou retorna ``None``.

    Retorna ``None`` se ausente ou corrompido.
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            dados = json.load(f)
        return StatusSessao.model_validate(dados)
    except (json.JSONDecodeError, ValueError):
        return None


def listar_sessoes(home: Path) -> list[tuple[str, ParametrosBusca, StatusSessao]]:
    """Lista todas as sessões válidas em ``<home>/sessoes/`` ordenadas por ``iniciada_em`` desc.

    Sessões com ``params.json`` ou ``status.json`` ausentes/corrompidos são
    silenciosamente puladas -- a UI ainda pode listar via ``listar_sessoes_brutas``
    se quiser exibir entradas em ruína (não implementado nesta sprint).

    Returns:
        Lista de triplas ``(id_sessao, params, status)`` ordenada da mais
        recente pra mais antiga.
    """
    raiz = home / "sessoes"
    if not raiz.exists():
        return []

    sessoes: list[tuple[str, ParametrosBusca, StatusSessao]] = []
    for pasta in raiz.iterdir():
        if not pasta.is_dir():
            continue
        params = carregar_params(pasta / "params.json")
        status = carregar_status(pasta / "status.json")
        if params is None or status is None:
            continue
        sessoes.append((pasta.name, params, status))

    sessoes.sort(key=lambda triple: triple[2].iniciada_em, reverse=True)
    return sessoes


def deletar_sessao(home: Path, id_sessao: str) -> None:
    """Remove a pasta da sessão recursivamente.

    Idempotente: chamar em sessão inexistente não levanta. Recusa caminhos
    fora de ``<home>/sessoes/`` por segurança contra path traversal via
    id_sessao malicioso (``../`` etc).
    """
    alvo = caminho_sessao(home, id_sessao).resolve()
    raiz = (home / "sessoes").resolve()
    try:
        alvo.relative_to(raiz)
    except ValueError as exc:  # alvo fora de raiz -- recusa.
        msg = f"id_sessao fora da pasta sessoes: {id_sessao!r}"
        raise ValueError(msg) from exc

    if not alvo.exists():
        return

    # Apaga conteúdo recursivamente. shutil.rmtree é o caminho padrão.
    import shutil

    shutil.rmtree(alvo)
