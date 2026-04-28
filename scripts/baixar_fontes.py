"""Baixa Inter + JetBrains Mono e verifica integridade SHA256.

Idempotente: se TTFs já existem em ``src/hemiciclo/dashboard/static/fonts/``
e os hashes batem com ``HASHES_ESPERADOS``, não re-baixa.

Origens oficiais:
- Inter v4.0: https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip (extras/ttf/)
- JetBrains Mono v2.304: https://www.jetbrains.com/lp/mono/

Licença das fontes: SIL Open Font License 1.1 (compatível com GPL v3).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# Hashes calculados na primeira execução (S23.1, 2026-04-28).
# Se URL de origem mudar conteúdo, hash falha e usuário é avisado.
HASHES_ESPERADOS: dict[str, str] = {
    "Inter-Regular.ttf": "64f8be6e55c37e32ef03da99714bf3aa58b8f2099bfe4f759a7578e3b8291123",
    "Inter-Medium.ttf": "1bda81124d6ae26ed16a7201e2bd93766af5a3b14faf79eea14d191ebbd41146",
    "Inter-SemiBold.ttf": "0dc98e8aa59585394880f25ab89e6d915ad5134522e961b046ca51fad3a18255",
    "Inter-Bold.ttf": "0cb1bc1335372d9e3a0cf6f5311c7cce87af90d2a777fdeec18be605a2a70bc1",
    "JetBrainsMono-Regular.ttf": "a0bf60ef0f83c5ed4d7a75d45838548b1f6873372dfac88f71804491898d138f",
    "JetBrainsMono-Bold.ttf": "5590990c82e097397517f275f430af4546e1c45cff408bde4255dad142479dcb",
}


def _sha256(path: Path) -> str:
    """Calcula SHA256 hex de um arquivo (streaming, baixa memória)."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def verificar_fontes(dir_fontes: Path) -> tuple[int, int]:
    """Confere hashes esperados e reporta status.

    Returns:
        (presentes, esperadas) -- contagem de TTFs com hash OK vs total.
    """
    presentes = 0
    esperadas = len(HASHES_ESPERADOS)
    for nome, hash_esperado in HASHES_ESPERADOS.items():
        path = dir_fontes / nome
        if not path.exists():
            print(f"[fontes] {nome}: AUSENTE")
            continue
        hash_atual = _sha256(path)
        if hash_atual == hash_esperado:
            print(f"[fontes] {nome}: hash OK")
            presentes += 1
        else:
            print(f"[fontes] {nome}: HASH DIVERGENTE (esperado {hash_esperado[:16]}..., atual {hash_atual[:16]}...)")
    return presentes, esperadas


def main() -> int:
    """Entry-point CLI: ``uv run python scripts/baixar_fontes.py``."""
    repo_root = Path(__file__).resolve().parent.parent
    dir_fontes = repo_root / "src" / "hemiciclo" / "dashboard" / "static" / "fonts"
    dir_fontes.mkdir(parents=True, exist_ok=True)

    presentes, esperadas = verificar_fontes(dir_fontes)
    if presentes == esperadas:
        print(f"\n[fontes] OK: {presentes}/{esperadas} fontes verificadas com hash íntegro.")
        print(f"[fontes] Diretório: {dir_fontes}")
        return 0

    print(f"\n[fontes] {presentes}/{esperadas} TTFs com hash OK.")
    print("[fontes] Para baixar/atualizar manualmente:")
    print("  1. Inter v4.0 -- https://github.com/rsms/inter/releases (extrair extras/ttf/)")
    print("  2. JetBrains Mono v2.304 -- https://www.jetbrains.com/lp/mono/")
    print(f"  3. Salvar em {dir_fontes}/ com os nomes esperados")
    print(f"  4. Re-rodar este script para validar SHA256")
    return 1


if __name__ == "__main__":
    sys.exit(main())
