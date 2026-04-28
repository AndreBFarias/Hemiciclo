"""Pacote de modelos analíticos do Hemiciclo (S27+).

Subdivide-se em camadas conforme ADR-011 (D11 -- classificação multicamada
em cascata):

- :mod:`hemiciclo.modelos.classificador_c1` -- C1, determinística (regex,
  categoria oficial, voto agregado).
- :mod:`hemiciclo.modelos.classificador_c2` -- C2, estatística leve
  (TF-IDF, intensidade discursiva).
- :mod:`hemiciclo.modelos.classificador` -- orquestrador que costura as
  camadas e persiste resultado.
- :mod:`hemiciclo.modelos.embeddings` -- C3, wrapper lazy do bge-m3 (S28).
- :mod:`hemiciclo.modelos.base` -- modelo base v1 (PCA sobre embeddings,
  ADR-008/D8) com amostragem determinística (S28).
- :mod:`hemiciclo.modelos.persistencia_modelo` -- salvar/carregar com
  validação de integridade SHA256 (S28).
- :mod:`hemiciclo.modelos.projecao` -- ``transform`` no espaco induzido
  para sessões locais (interface S28; ajuste fino em S30).
- :mod:`hemiciclo.modelos.topicos_induzidos` -- wrapper BERTopic stub
  (treino real em S30/S31).

C4 (LLM opcional) entra em S34b. O sistema deve produzir resultado útil
mesmo com C3+C4 desligados -- esta é a invariante D11.
"""

from __future__ import annotations
