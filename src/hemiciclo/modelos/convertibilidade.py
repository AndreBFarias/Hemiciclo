"""ML de convertibilidade por parlamentar (S34).

Eixo ``convertibilidade`` da assinatura multidimensional (D4 / ADR-004).
Dado um parlamentar, prevê a probabilidade de mudar de posição num
tópico nas próximas N votações, a partir de features já calculadas
pelas sprints anteriores:

- ``indice_volatilidade`` (S33 -- :mod:`hemiciclo.modelos.historico`).
- ``centralidade_grau``, ``centralidade_intermediacao`` (S32 grafo voto
  -- :mod:`hemiciclo.modelos.grafo`).
- ``comunidade_voto`` (S32, codificada por embedding numérico).
- ``proporcao_sim_topico`` (S27 C1+C2 -- ``classificacao_c1_c2.json``).
- ``n_votos_topico`` (S27 C1+C2).

Pipeline:

1. :class:`ExtratorFeatures` lê os 3 artefatos JSON da sessão e
   constrói um :class:`polars.DataFrame` numérico + target binário.
2. Target ``mudou_recentemente`` = 1 se o parlamentar tem ao menos 1
   evento em ``mudancas_detectadas`` (S33), 0 caso contrário. Proxy
   correlacional documentado em :file:`docs/arquitetura/convertibilidade.md`.
3. :class:`ModeloConvertibilidade` treina um
   :class:`sklearn.linear_model.LogisticRegression` com split 70/30
   estratificado, ``random_state=42`` em todos os pontos estocásticos.
4. Persistência via ``joblib`` + ``meta.json`` paralelo com SHA256
   (precedente :mod:`hemiciclo.modelos.persistencia_modelo` -- S28).
   :class:`IntegridadeViolada` no carregamento se hash divergir.

Skip graceful rigoroso:

- Artefatos S32/S33 ausentes -> :meth:`ExtratorFeatures.extrair`
  devolve DataFrame vazio + ``logger.warning``. Caller decide.
- Amostra < :data:`MIN_AMOSTRA` -> :meth:`ModeloConvertibilidade.treinar`
  levanta :class:`AmostraInsuficiente` (caller deve tratar como SKIPPED).
- Apenas 1 classe presente em ``y`` -> :class:`AmostraInsuficiente`
  (split estratificado precisa de ambas).

Caveats metodológicos honestos (também documentados no doc):

- Amostra pequena (top 100) limita generalização.
- Target sintético é proxy.
- Vazamento parcial de target via ``indice_volatilidade`` (que já
  resume mudanças passadas). MVP aceita; v2 deve ter feature engineering
  com janela temporal estrita.
- Modelo é correlacional, não causal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import joblib
import numpy as np
import polars as pl
from loguru import logger
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

RANDOM_STATE: int = 42
"""Semente fixa em todos os pontos estocásticos (I3 do BRIEF)."""

MIN_AMOSTRA: int = 30
"""Amostra mínima pra treino. Abaixo disso o modelo é piada estatística."""

TEST_SIZE: float = 0.30
"""Proporção do split estratificado (70/30 conforme spec)."""

VERSAO_MODELO: str = "1"
"""Versão do schema serializado. Bump em mudanças incompatíveis."""

FEATURE_NAMES_PADRAO: tuple[str, ...] = (
    "indice_volatilidade",
    "centralidade_grau",
    "centralidade_intermediacao",
    "proporcao_sim_topico",
    "n_votos_topico",
)
"""Ordem canônica das features. Persistida no ``meta.json`` para
garantir que ``prever_proba`` use a mesma ordem que ``treinar``."""

_NOME_BIN: str = "convertibilidade.joblib"
_NOME_META: str = "convertibilidade.meta.json"


# ---------------------------------------------------------------------------
# Exceções
# ---------------------------------------------------------------------------


class IntegridadeViolada(Exception):  # noqa: N818 -- contrato em PT-BR (precedente S28)
    """Hash do artefato divergente ou versão incompatível.

    Padrão idêntico a :class:`hemiciclo.modelos.persistencia_modelo.IntegridadeViolada`
    -- mantido separado pra não acoplar S34 ao S28 em caso de evolução
    independente.
    """


class AmostraInsuficiente(Exception):  # noqa: N818 -- contrato em PT-BR
    """Amostra insuficiente para treino (< :data:`MIN_AMOSTRA` ou monoclasse)."""


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _sha256_arquivo(path: Path) -> str:
    """SHA256 streaming (chunks de 8 KiB). Idêntico ao S28."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _ler_json(path: Path) -> dict[str, object]:
    """Lê JSON como dict, devolve ``{}`` em ausência/corrupção (skip graceful)."""
    if not path.is_file():
        return {}
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("[convertibilidade] JSON corrompido em {p}: {e}", p=path, e=exc)
        return {}
    if not isinstance(dados, dict):
        return {}
    return cast(dict[str, object], dados)


# ---------------------------------------------------------------------------
# ExtratorFeatures
# ---------------------------------------------------------------------------


class ExtratorFeatures:
    """Constrói DataFrame de features + target a partir dos artefatos da sessão.

    Lê (todos opcionais; ausência vira skip graceful):

    - ``<sessao_dir>/historico_conversao.json`` (S33)
    - ``<sessao_dir>/metricas_rede.json`` (S32)
    - ``<sessao_dir>/classificacao_c1_c2.json`` (S27)

    DataFrame final (Polars) com colunas:

    - ``parlamentar_id`` (Int64)
    - ``casa`` (Utf8)
    - ``nome`` (Utf8) -- útil pra ranking final
    - ``indice_volatilidade`` (Float64)
    - ``centralidade_grau`` (Float64)
    - ``centralidade_intermediacao`` (Float64)
    - ``proporcao_sim_topico`` (Float64)
    - ``n_votos_topico`` (Int64)
    - ``mudou_recentemente`` (Int8) -- target binário
    """

    @staticmethod
    def extrair(sessao_dir: Path) -> pl.DataFrame:
        """Lê os 3 artefatos e devolve DataFrame Polars com features + target.

        Args:
            sessao_dir: Pasta da sessão de pesquisa
                (``~/hemiciclo/sessoes/<id>/``).

        Returns:
            DataFrame com 1 linha por parlamentar presente no histórico
            (S33). DataFrame vazio se ``historico_conversao.json`` ausente
            ou se a etapa S33 fez skip graceful (sem parlamentares).

            Centralidades faltantes (parlamentar não está no top do
            grafo de voto) viram ``0.0`` -- decisão consciente: assumir
            que ausência == nó periférico, melhor do que descartar
            amostra.

            ``proporcao_sim_topico`` faltante (parlamentar não consta no
            ranking C1+C2 do tópico) também vira ``0.0`` + ``n_votos_topico=0``.
        """
        hist_path = sessao_dir / "historico_conversao.json"
        rede_path = sessao_dir / "metricas_rede.json"
        classif_path = sessao_dir / "classificacao_c1_c2.json"

        historico = _ler_json(hist_path)
        rede = _ler_json(rede_path)
        classif = _ler_json(classif_path)

        parlamentares_obj = historico.get("parlamentares") or {}
        if not isinstance(parlamentares_obj, dict) or not parlamentares_obj:
            logger.warning(
                "[convertibilidade] historico_conversao.json ausente/vazio em {p}; DataFrame vazio",
                p=sessao_dir,
            )
            return _df_vazio()

        # Indexa centralidades do grafo voto. Estrutura:
        # rede["voto"]["top_centrais"] = lista de dicts com chaves
        # parlamentar/centralidade_grau/centralidade_intermediacao etc.
        cent_por_id: dict[str, dict[str, float]] = {}
        voto_obj_raw = rede.get("voto") or {}
        voto_obj = voto_obj_raw if isinstance(voto_obj_raw, dict) else {}
        if voto_obj and not voto_obj.get("skipped"):
            top = voto_obj.get("top_centrais") or []
            if isinstance(top, list):
                for entrada in top:
                    if not isinstance(entrada, dict):
                        continue
                    pid_raw = (
                        entrada.get("parlamentar_id")
                        or entrada.get("id")
                        or entrada.get("parlamentar")
                    )
                    if pid_raw is None:
                        continue
                    cent_por_id[str(pid_raw)] = {
                        "centralidade_grau": float(entrada.get("centralidade_grau", 0.0) or 0.0),
                        "centralidade_intermediacao": float(
                            entrada.get("centralidade_intermediacao", 0.0) or 0.0
                        ),
                    }

        # Indexa proporcao_sim_topico do C1+C2. Combina top_a_favor + top_contra.
        prop_por_id: dict[str, dict[str, float]] = {}
        for chave in ("top_a_favor", "top_contra"):
            lista = classif.get(chave) or []
            if not isinstance(lista, list):
                continue
            for parl in lista:
                if not isinstance(parl, dict):
                    continue
                pid_raw = parl.get("parlamentar_id") or parl.get("id")
                if pid_raw is None:
                    continue
                # Schema S27: proporcao_sim ou pct_a_favor; aceitamos ambos.
                prop_val = float(parl.get("proporcao_sim", parl.get("pct_a_favor", 0.0)) or 0.0)
                n_votos = int(parl.get("n_votos", 0) or 0)
                prop_por_id[str(pid_raw)] = {
                    "proporcao_sim_topico": prop_val,
                    "n_votos_topico": float(n_votos),
                }

        linhas: list[dict[str, object]] = []
        for pid_str, bloco in parlamentares_obj.items():
            if not isinstance(bloco, dict):
                continue
            try:
                parl_id = int(pid_str)
            except (TypeError, ValueError):
                continue
            casa = str(bloco.get("casa", "camara"))
            nome = str(bloco.get("nome", pid_str))
            volat = float(bloco.get("indice_volatilidade", 0.0) or 0.0)
            mudancas = bloco.get("mudancas_detectadas") or []
            target = 1 if isinstance(mudancas, list) and len(mudancas) > 0 else 0

            cent = cent_por_id.get(pid_str, {})
            prop = prop_por_id.get(pid_str, {})

            linhas.append(
                {
                    "parlamentar_id": parl_id,
                    "casa": casa,
                    "nome": nome,
                    "indice_volatilidade": float(volat),
                    "centralidade_grau": float(cent.get("centralidade_grau", 0.0)),
                    "centralidade_intermediacao": float(
                        cent.get("centralidade_intermediacao", 0.0)
                    ),
                    "proporcao_sim_topico": float(prop.get("proporcao_sim_topico", 0.0)),
                    "n_votos_topico": int(prop.get("n_votos_topico", 0)),
                    "mudou_recentemente": int(target),
                }
            )

        if not linhas:
            return _df_vazio()

        return pl.DataFrame(linhas, schema=_schema_features())


def _schema_features() -> dict[str, pl.DataType]:
    """Schema canônico do DataFrame produzido por :meth:`ExtratorFeatures.extrair`."""
    return {
        "parlamentar_id": pl.Int64(),
        "casa": pl.Utf8(),
        "nome": pl.Utf8(),
        "indice_volatilidade": pl.Float64(),
        "centralidade_grau": pl.Float64(),
        "centralidade_intermediacao": pl.Float64(),
        "proporcao_sim_topico": pl.Float64(),
        "n_votos_topico": pl.Int64(),
        "mudou_recentemente": pl.Int64(),
    }


def _df_vazio() -> pl.DataFrame:
    """DataFrame vazio com schema canônico."""
    return pl.DataFrame(schema=_schema_features())


# ---------------------------------------------------------------------------
# ModeloConvertibilidade
# ---------------------------------------------------------------------------


@dataclass
class ModeloConvertibilidade:
    """LogisticRegression treinada + métricas + metadata.

    O atributo :attr:`classifier` é a instância sklearn ajustada. As
    :attr:`feature_names` definem a ordem em que features chegam ao
    ``predict_proba`` -- mesma ordem usada no treino.

    Persistência: :meth:`salvar` grava ``joblib`` + ``meta.json``;
    :meth:`carregar` valida SHA256 e versão antes de desserializar.
    """

    classifier: LogisticRegression
    feature_names: tuple[str, ...]
    metricas: dict[str, float]
    treinado_em: datetime = field(default_factory=lambda: datetime.now(UTC))
    versao: str = VERSAO_MODELO

    @classmethod
    def treinar(
        cls,
        X: pl.DataFrame,  # noqa: N803 -- convenção sklearn maiúsculas
        y: pl.Series,
        feature_names: tuple[str, ...] | None = None,
    ) -> ModeloConvertibilidade:
        """Treina LogisticRegression com split 70/30 estratificado.

        Args:
            X: DataFrame com colunas em :data:`FEATURE_NAMES_PADRAO`
                (ou ``feature_names`` customizado).
            y: Série binária com target ``mudou_recentemente``.
            feature_names: Ordem das colunas de ``X`` a usar. Default
                :data:`FEATURE_NAMES_PADRAO`.

        Returns:
            :class:`ModeloConvertibilidade` ajustado.

        Raises:
            AmostraInsuficiente: ``len(X) < MIN_AMOSTRA`` ou só 1 classe
                presente em ``y`` (split estratificado precisa de duas).
        """
        nomes = feature_names if feature_names is not None else FEATURE_NAMES_PADRAO
        n = len(X)
        if n < MIN_AMOSTRA:
            raise AmostraInsuficiente(
                f"amostra insuficiente: {n} < {MIN_AMOSTRA} "
                "(recomenda-se coleta com mais parlamentares)"
            )

        # Filtra colunas na ordem canônica.
        faltando = [c for c in nomes if c not in X.columns]
        if faltando:
            raise AmostraInsuficiente(f"colunas ausentes em X: {faltando}")

        x_arr = X.select(list(nomes)).to_numpy().astype(float)
        y_arr = y.to_numpy().astype(int)

        if len(set(y_arr.tolist())) < 2:  # noqa: PLR2004
            raise AmostraInsuficiente("y tem apenas 1 classe; split estratificado impossível")

        # Split 70/30 estratificado, random_state fixo (3 pontos: split,
        # classifier interno se solver lbfgs com warm start, e qualquer
        # passo que envolva permutação).
        x_tr, x_te, y_tr, y_te = train_test_split(
            x_arr,
            y_arr,
            test_size=TEST_SIZE,
            stratify=y_arr,
            random_state=RANDOM_STATE,
        )

        clf = LogisticRegression(
            max_iter=1000,
            random_state=RANDOM_STATE,
            solver="lbfgs",
        )
        clf.fit(x_tr, y_tr)

        y_pred = clf.predict(x_te)
        # ROC-AUC só faz sentido com 2 classes presentes em y_te. Defesa.
        if len(set(y_te.tolist())) > 1:  # noqa: PLR2004
            y_proba = clf.predict_proba(x_te)[:, 1]
            roc_auc = float(roc_auc_score(y_te, y_proba))
        else:
            roc_auc = 0.0

        metricas: dict[str, float] = {
            "accuracy": float(accuracy_score(y_te, y_pred)),
            "precision": float(precision_score(y_te, y_pred, zero_division=0)),
            "recall": float(recall_score(y_te, y_pred, zero_division=0)),
            "f1": float(f1_score(y_te, y_pred, zero_division=0)),
            "roc_auc": roc_auc,
            "n_treino": float(len(y_tr)),
            "n_teste": float(len(y_te)),
            "n_total": float(n),
        }

        return cls(
            classifier=clf,
            feature_names=tuple(nomes),
            metricas=metricas,
        )

    def prever_proba(self, X: pl.DataFrame) -> pl.Series:  # noqa: N803 -- convenção sklearn
        """Probabilidade da classe positiva (mudou_recentemente=1).

        Args:
            X: DataFrame com as mesmas colunas usadas no treino, na mesma
                ordem (:attr:`feature_names`).

        Returns:
            ``pl.Series[Float64]`` em [0, 1] com 1 valor por linha.
        """
        faltando = [c for c in self.feature_names if c not in X.columns]
        if faltando:
            raise ValueError(f"colunas ausentes em X: {faltando}")
        if len(X) == 0:
            return pl.Series("proba", [], dtype=pl.Float64)
        x_arr = X.select(list(self.feature_names)).to_numpy().astype(float)
        proba = self.classifier.predict_proba(x_arr)[:, 1]
        return pl.Series("proba", proba.tolist(), dtype=pl.Float64)

    def coeficientes(self) -> dict[str, float]:
        """Retorna ``{feature: coef}`` da regressão (proxy de SHAP).

        Útil para tooltip de interpretabilidade no widget de ranking.
        Coeficientes positivos indicam features que aumentam a
        probabilidade prevista de conversão.
        """
        coefs = self.classifier.coef_[0]
        return {nome: float(c) for nome, c in zip(self.feature_names, coefs, strict=True)}

    def salvar(self, dir_destino: Path) -> dict[str, object]:
        """Persiste em ``<dir_destino>/convertibilidade.{joblib,meta.json}``.

        Returns:
            Manifesto (dict) gravado em ``meta.json``. Útil para CLI/log.
        """
        dir_destino.mkdir(parents=True, exist_ok=True)
        bin_path = dir_destino / _NOME_BIN
        meta_path = dir_destino / _NOME_META

        joblib.dump(self.classifier, bin_path)

        hash_arq = _sha256_arquivo(bin_path)
        meta: dict[str, object] = {
            "versao": self.versao,
            "treinado_em": self.treinado_em.astimezone(UTC).isoformat(),
            "hash_sha256": hash_arq,
            "feature_names": list(self.feature_names),
            "metricas": dict(self.metricas),
            "coeficientes": self.coeficientes(),
            "salvo_em": datetime.now(UTC).isoformat(),
        }
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return meta

    @classmethod
    def carregar(cls, dir_origem: Path) -> ModeloConvertibilidade:
        """Carrega validando integridade SHA256 e versão.

        Raises:
            FileNotFoundError: arquivos ausentes.
            IntegridadeViolada: versão incompatível ou hash divergente.
        """
        bin_path = dir_origem / _NOME_BIN
        meta_path = dir_origem / _NOME_META
        if not bin_path.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"Modelo de convertibilidade ausente em {dir_origem} "
                f"(esperados '{_NOME_BIN}' e '{_NOME_META}')."
            )

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        versao = meta.get("versao")
        if versao != VERSAO_MODELO:
            raise IntegridadeViolada(
                f"Versão incompatível: meta='{versao}' "
                f"(esperado '{VERSAO_MODELO}'). Re-treine o modelo."
            )

        hash_atual = _sha256_arquivo(bin_path)
        hash_esperado = meta.get("hash_sha256")
        if hash_atual != hash_esperado:
            raise IntegridadeViolada(
                f"Hash divergente em {bin_path.name}: "
                f"calculado={hash_atual} != registrado={hash_esperado}. "
                "Artefato corrompido; re-treine o modelo."
            )

        clf = cast(LogisticRegression, joblib.load(bin_path))
        feature_names = tuple(str(x) for x in meta.get("feature_names", []))
        metricas_obj = meta.get("metricas", {})
        metricas = (
            {str(k): float(v) for k, v in metricas_obj.items()}
            if isinstance(metricas_obj, dict)
            else {}
        )
        treinado_em_str = str(meta.get("treinado_em", datetime.now(UTC).isoformat()))
        try:
            treinado_em = datetime.fromisoformat(treinado_em_str)
        except ValueError:
            treinado_em = datetime.now(UTC)

        return cls(
            classifier=clf,
            feature_names=feature_names,
            metricas=metricas,
            treinado_em=treinado_em,
            versao=str(versao),
        )


# ---------------------------------------------------------------------------
# Função de conveniência -- treino end-to-end a partir da sessão
# ---------------------------------------------------------------------------


def treinar_convertibilidade_sessao(
    sessao_dir: Path,
    top_n: int = 100,
) -> dict[str, object]:
    """Treina e persiste o modelo de convertibilidade para uma sessão.

    Helper consumido pela CLI ``hemiciclo convertibilidade treinar`` e
    pelo pipeline (``_etapa_convertibilidade``).

    Pipeline:

    1. :meth:`ExtratorFeatures.extrair` lê os 3 artefatos da sessão.
    2. :meth:`ModeloConvertibilidade.treinar` ajusta o classificador.
    3. :meth:`ModeloConvertibilidade.salvar` grava em
       ``<sessao_dir>/modelo_convertibilidade/`` (subpasta dedicada,
       não polui a raiz da sessão).
    4. Top ``top_n`` ranqueado por ``proba`` desc é gravado em
       ``<sessao_dir>/convertibilidade_scores.json``.

    Returns:
        Dict serializável com manifesto + scores + status::

            {
                "skipped": bool,
                "motivo": str | None,
                "n_amostra": int,
                "metricas": {...},
                "scores": [{"parlamentar_id", "nome", "casa", "proba"}, ...],
                "coeficientes": {...},
            }

        Em caso de skip graceful (features vazias / amostra < 30),
        ``skipped=True`` e ``scores=[]``.
    """
    df = ExtratorFeatures.extrair(sessao_dir)
    n = len(df)
    if n == 0:
        logger.warning(
            "[convertibilidade] sessão {p} sem features -- SKIPPED",
            p=sessao_dir,
        )
        return _resultado_skipped("features vazias (artefatos S32/S33 ausentes)")

    if n < MIN_AMOSTRA:
        logger.warning(
            "[convertibilidade] amostra={n} < {m}; SKIPPED graceful",
            n=n,
            m=MIN_AMOSTRA,
        )
        return _resultado_skipped(
            f"amostra insuficiente: {n} < {MIN_AMOSTRA} "
            "(recomenda-se coleta com mais parlamentares)"
        )

    df_x = df.select(list(FEATURE_NAMES_PADRAO))
    serie_y = df["mudou_recentemente"].cast(pl.Int64)

    try:
        modelo = ModeloConvertibilidade.treinar(df_x, serie_y)
    except AmostraInsuficiente as exc:
        logger.warning("[convertibilidade] {e}", e=exc)
        return _resultado_skipped(str(exc))

    # Ranking: usa todo o DataFrame (não só treino) pra gerar scores
    # úteis ao usuário. Prática comum em ML aplicado quando o modelo
    # serve para ranqueamento e não classificação binária estrita.
    proba = modelo.prever_proba(df_x)
    df_scores = (
        df.with_columns(proba.alias("proba"))
        .select(["parlamentar_id", "nome", "casa", "proba", "indice_volatilidade"])
        .sort("proba", descending=True)
        .head(top_n)
    )

    dir_modelo = sessao_dir / "modelo_convertibilidade"
    meta = modelo.salvar(dir_modelo)

    scores_payload: dict[str, object] = {
        "skipped": False,
        "motivo": None,
        "n_amostra": int(n),
        "metricas": dict(modelo.metricas),
        "coeficientes": modelo.coeficientes(),
        "feature_names": list(modelo.feature_names),
        "treinado_em": modelo.treinado_em.astimezone(UTC).isoformat(),
        "hash_sha256": str(meta.get("hash_sha256", "")),
        "scores": df_scores.to_dicts(),
    }
    destino = sessao_dir / "convertibilidade_scores.json"
    destino.write_text(
        json.dumps(scores_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(
        "[convertibilidade] amostra={n} accuracy={a:.2f} f1={f:.2f} roc_auc={r:.2f}",
        n=n,
        a=modelo.metricas["accuracy"],
        f=modelo.metricas["f1"],
        r=modelo.metricas["roc_auc"],
    )
    return scores_payload


def _resultado_skipped(motivo: str) -> dict[str, object]:
    """Resultado canônico de skip graceful (sem treino)."""
    return {
        "skipped": True,
        "motivo": motivo,
        "n_amostra": 0,
        "metricas": {},
        "coeficientes": {},
        "feature_names": list(FEATURE_NAMES_PADRAO),
        "scores": [],
    }


# ---------------------------------------------------------------------------
# Exports declarados (PEP 8 / facilita import do pipeline)
# ---------------------------------------------------------------------------

__all__ = [
    "FEATURE_NAMES_PADRAO",
    "MIN_AMOSTRA",
    "RANDOM_STATE",
    "AmostraInsuficiente",
    "ExtratorFeatures",
    "IntegridadeViolada",
    "ModeloConvertibilidade",
    "treinar_convertibilidade_sessao",
]


# ``np`` precisa estar importado para o sklearn aceitar arrays sem warning
# em algumas versões do polars. Mantemos a referência viva no escopo
# do módulo (não é dead code -- evita lint que sugira remover o import).
_ = np
