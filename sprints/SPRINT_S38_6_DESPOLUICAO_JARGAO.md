# Sprint S38.6 -- Despoluição de jargão técnico no dashboard

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Status:** READY
**Esforço:** P-M (2-3h)
**Branch:** feature/s38-6-despoluicao-jargao
**Depende de:** --

---

## 1. Objetivo

Esconder jargão de roadmap e linguagem técnica do produto exposta ao usuário comum. Substituir por linguagem cidadã ou ocultar até a feature estar pronta.

## 2. Contexto

Smoke real revelou vazamentos de roadmap e linguagem técnica que confundem o usuário João:

**Vazamentos identificados nos screenshots:**

| Onde | Texto atual | Problema |
|---|---|---|
| Assinatura multidimensional | `hipocrisia (S33)`, `centralidade (S32)`, `convertibilidade (S34)`, `enquadramento (S34b)` | IDs de sprint expostos |
| Redes de coautoria | `(proxy enquanto S27.1 não traz proposicao_id)` | Vazamento dev |
| Card de coautoria | `Grafo ainda não gerado para esta sessão. Rode hemiciclo rede analisar <id_sessao> ou aguarde o pipeline.` | Comando CLI exposto |
| Card de coautoria | `SKIPPED — dados.duckdb ausente` | Mensagem técnica de log |
| Convertibilidade | `Probabilidade de cada parlamentar mudar de posição nas próximas votações. Modelo: regressão logística (sklearn) com features de volatilidade histórica (S33), centralidade na rede de voto (S32) e proporção SIM no tópico (S27). Limites metodológicos em docs/arquitetura/convertibilidade.md ...` | Path de doc no dashboard |
| Limitações conhecidas | "Esta análise herda os limites das sprints abaixo:" + `S<NN>` | Lista de IDs de sprint |
| Heatmap | "(em S<NN>)" abundante | IDs de sprint expostos |
| Card "Iniciar pesquisa" (S23 stub) | `Funcionalidade chega em S30 — ...` | Vazamento de cronograma |

## 3. Escopo

### 3.1 In-scope

**3.1.1. `dashboard/widgets/radar_assinatura.py`:**
Trocar rótulos dos eixos de "(em SXX)" por:
- "intensidade" (já disponível, manter)
- "posição" (já disponível, manter)
- "hipocrisia (em breve)"
- "volatilidade (em breve)"
- "centralidade (em breve)"
- "convertibilidade (em breve)"
- "enquadramento (em breve)"

Ou ocultar eixos não-disponíveis e mostrar só os 2 ativos com nota "Mais 5 dimensões em breve."

**3.1.2. `dashboard/paginas/sessao_detalhe.py`:**
- Trocar texto "Quem articula com quem. Coautoria = votar nas mesmas votações (proxy enquanto S27.1 não traz proposicao_id)" por simplesmente "Coautoria = votar nas mesmas votações."
- Trocar `Grafo ainda não gerado... Rode hemiciclo rede analisar <id_sessao>...` por mensagem amigável: "Os grafos de articulação política aparecerão aqui assim que a análise terminar."
- Trocar `SKIPPED — dados.duckdb ausente` por nada (esconder ou mensagem genérica "Análise ainda não disponível para esta sessão.")
- Convertibilidade: simplificar para "Probabilidade de mudar de posição em votações futuras. Modelo experimental." -- esconder path de doc; opcionalmente botão "Saiba mais" que abre manifesto/doc em modal.

**3.1.3. `dashboard/paginas/sessao_detalhe.py` -- Limitações conhecidas:**
Reescrever bloco para esconder IDs de sprint:
- Antes: "Esta análise herda os limites das sprints abaixo: S<NN>..."
- Depois: "Esta versão tem limites conhecidos: histórico de votação ainda não filtrado por tópico; redes de coautoria usam aproximação por co-votação; convertibilidade é experimental."

**3.1.4. `dashboard/paginas/nova_pesquisa.py`:**
Já será corrigida pela S38.4. Garantir que mensagem de S30 stub seja removida.

### 3.2 Out-of-scope
- Reescrever explicações metodológicas para leigo (sprint educativa futura S39.1)
- Tooltip/glossário em hover (sprint UX dedicada)

## 4. Proof-of-work

```bash
$ grep -E "\(S[0-9]+[a-z]*\)|S<NN>|SKIPPED|hemiciclo rede analisar|S30 -- " src/hemiciclo/dashboard/
# (zero hits — exceto comentários de código, que podem manter sprint refs)
```

Critério de aceite:
- [ ] Nenhum "(SXX)" visível ao usuário no dashboard
- [ ] Nenhum path `docs/arquitetura/*.md` exposto
- [ ] Nenhum comando CLI hardcoded em mensagem de UX
- [ ] "SKIPPED" substituído por mensagem cidadã

## 5. Riscos

Mínimo. Sprint puramente cosmética; não toca lógica.

## 6. Próximo passo após DONE

Combina com S38.5 -- ambas afetam UX visual; mergear juntas se possível.
