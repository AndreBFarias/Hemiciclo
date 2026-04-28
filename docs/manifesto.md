## Manifesto do Hemiciclo

Inteligência política aberta. Soberana. Local. Auditável até o último voto.

O Hemiciclo é uma ferramenta cidadã para entender o Congresso Brasileiro com
o mesmo rigor metodológico que se vende, hoje, a lobistas, marcas e gabinetes
empresariais. A diferença é radical: aqui não há servidor central, não há
rastreio, não há custo de licença, não há dependência de provedor que possa
mudar de termos de uso da noite para o dia. O cidadão comum -- o "seu João",
professor de escola pública, engenheiro de obra, dona de casa, jovem que
estuda à noite -- roda o Hemiciclo na própria máquina, com dois comandos, e
tem nas mãos o tipo de leitura que empresas pagam pesquisa cara para receber.

---

### O que faz quem trabalha pra lobistas

O mercado brasileiro de inteligência política privada vende, há anos,
perfilamento comportamental quantitativo a grandes empresas: bancos,
varejistas, operadoras de saúde, federações setoriais, consultorias de
relações governamentais. Netnografia, scraping de redes, modelagem de
tópicos, análise de sentimento sobre legisladores, mapas de afinidade,
dossiês com recomendação operacional sobre como abordar parlamentar X em
comissão Y.

São entregas competentes, metodologicamente rigorosas, e -- importante --
têm preço de mercado de cinco a seis dígitos por estudo. O cliente que
contrata recebe uma vantagem informacional concreta sobre quem nunca
poderia pagar pela mesma análise: ONGs pequenas, jornalistas independentes,
movimentos sociais, professores de ciência política em universidades
estaduais, e o próprio cidadão comum, que vota mas não tem como saber se
quem votou está votando como prometeu.

A pergunta que organiza este projeto é simples: por que o **mesmo método**,
executado sobre os **mesmos dados públicos** (que já estão nas APIs oficiais
da Câmara e do Senado), não está disponível pro lado de fora desse mercado?
Por que a inteligência quantitativa parlamentar é vendida como produto
premium quando os dados de origem são **abertos por lei**?

### Por que isso é problema

A assimetria de informação política é uma das formas mais silenciosas de
desigualdade democrática. Não está em manchete. Não rende escândalo. Mas
estrutura, todos os dias, a maneira como decisões legislativas são tomadas:
quem tem o dossiê fala primeiro, fala melhor, antecipa movimentos, monta
coalizões, identifica vulnerabilidades de gabinete, mapeia padrões de
conversão de voto.

Do outro lado, o eleitor recebe a versão final -- a manchete, o discurso
inflamado, a foto na votação polêmica -- e tenta deduzir, sozinho, se aquele
parlamentar realmente representa o que prometeu. Costuma errar. Não porque
seja burro: porque ninguém colocou nas mãos dele a mesma matéria-prima que
o lobista usa.

O resultado é uma democracia em que a informação política sofisticada é um
**bem de luxo**. E todo bem de luxo -- por definição -- exclui. O Hemiciclo
existe para virar esse vetor do avesso.

### O Hemiciclo é a inversão do vetor

A ideia é simples e radical: pegar todo o ferramental que se vende a empresa
de inteligência política -- coleta automatizada das APIs oficiais, classificação
multicamada (regex + voto nominal + embeddings semânticos + LLM opcional),
modelagem de tópicos, grafos de coautoria, métricas de centralidade,
detecção de mudança de posição ao longo do tempo, ranqueamento de
convertibilidade -- e empacotar tudo isso num executável que o cidadão
instala na própria máquina com um comando.

Sem servidor central. Sem rastreio. Sem cadastro. Sem API paga. Sem
dependência de empresa que possa ser comprada, pressionada ou simplesmente
fechar as portas. O modelo base é compartilhado pela comunidade; o ajuste
fino, os dados, o relatório, **ficam na sua máquina**, num zip auditável que
você abre, exporta, manda por email pra um amigo, copia pro pendrive. É
samizdat técnico aplicado à inteligência política.

Quando dizemos "mesmo rigor metodológico", é literal. A camada 1 do
classificador (regex + voto nominal + categoria oficial) é a mais
**transparente** que existe nessa categoria de produto: dois arquivos -- o
YAML do tópico e o CSV de votos -- bastam para reproduzir o resultado
canônico. As camadas seguintes (TF-IDF, embeddings, LLM) são complementos
desligáveis. Cada uma é independente, auditável e jamais sobrescreve o que a
camada anterior decidiu. Isso é raro mesmo no mercado pago: a maioria dos
produtos comerciais empilha caixas-pretas e exige que você confie na marca.
Aqui, a confiança é substituída pela auditoria.

### Por que GPL v3

A escolha de licença não é cosmética. **GPL v3 é o que garante que o
Hemiciclo permanecerá aberto**. Licenças permissivas (MIT, BSD, Apache)
permitem que uma empresa pegue todo o código, adicione um wrapper proprietário,
venda como produto fechado e nunca devolva nada à comunidade. Isso não é
hipótese -- é o que acontece, sistematicamente, com ferramentas
metodologicamente sofisticadas no campo de inteligência de mercado.

A GPL v3 estabelece uma cláusula clara: qualquer derivação, qualquer
distribuição modificada, **deve preservar a mesma licença**. Quem usa o
Hemiciclo como base para construir uma plataforma maior tem o direito de
fazê-lo -- mas precisa devolver à comunidade o que melhorou. É reciprocidade
estrutural, não apelo moral. A GPL v3 também tem proteções específicas
contra patentes e contra "tivoização" (lockdown de hardware), o que importa
porque a inteligência política, mais cedo ou mais tarde, vai virar tema de
disputa jurídica entre quem quer abrir e quem quer fechar.

A leitura cínica é dizer que GPL afasta empresa. A leitura honesta é dizer
que GPL afasta **um tipo específico de empresa**: a que quer extrair valor
sem devolver. Quem quiser construir produto comercial sobre o Hemiciclo,
respeitando a licença, é bem-vindo -- e a licença em si garante que esse
trabalho derivativo permaneça público.

### O que João Comum ganha

Três casos concretos.

**O jornalista de cidade pequena**, sem orçamento de redação para contratar
pesquisa, abre o Hemiciclo, configura uma sessão sobre "porte de armas"
filtrada pelo deputado da região, e em poucos minutos tem o histórico
completo de voto, a posição agregada, a distância entre discurso e voto
("hipocrisia mensurável"), a rede de coautoria do parlamentar, os colegas
mais próximos em padrão de voto. A pauta da semana sai com base em dado
público, citável, reproduzível. O leitor pode rodar o mesmo Hemiciclo e
verificar.

**O ativista de pauta progressista** que defende, por exemplo, marco
temporal indígena, abre uma sessão filtrando todas as proposições e votações
de uma legislatura sobre o tema. O Hemiciclo devolve top a-favor, top contra,
parlamentares que mudaram de posição, parlamentares com alta volatilidade
("convertibilidade"), comunidades de voto. A campanha de pressão fica
direcionada -- não desperdiça energia em quem nunca vai virar e identifica
quem está no fio da navalha.

**O eleitor curioso** que está em dúvida entre dois candidatos no próximo
ciclo eleitoral, ambos atualmente em mandato, abre uma sessão sobre cinco
ou seis temas que importam pra ele e compara as assinaturas multidimensionais.
Não é "robô que decide voto" -- o Hemiciclo nunca recomenda voto, nunca
emite juízo moral. É lente para enxergar **o que está nos dados públicos**.
A decisão continua sendo do eleitor.

### O que o Hemiciclo NÃO faz

Para evitar promessa que não cumpre, é importante demarcar com clareza o
que está fora do escopo desta ferramenta. O Hemiciclo **não recomenda
voto** ao eleitor, **não emite juízo ideológico embutido nos próprios
dados**, **não detecta corrupção** (apenas correlações comportamentais entre
parlamentares), **não substitui jornalismo investigativo de campo nem
fiscalização institucional formal**, **não prevê o futuro** (o eixo de
convertibilidade é correlacional, não causal), **não cobre conversas
privadas, gabinete, articulação de bastidor, tratativa partidária interna**
-- apenas o registro público formal disponibilizado pelas APIs oficiais.
O modelo é honesto sobre suas limitações: cada camada do classificador
documenta o erro esperado, cada métrica vem acompanhada de caveat
metodológico explícito no dashboard, e os ADRs descrevem em linguagem clara
as decisões fundadoras.

### Roadmap político

A versão 2.0 entrega o produto cidadão funcional ponta-a-ponta: instalação,
sessão de pesquisa, coleta, classificação multicamada, dashboard, grafos,
histórico, ranking de convertibilidade, exportação samizdat. As próximas
versões (v2.1+) ampliam: catálogo comunitário de tópicos curados, paridade
Windows nativa, camada 4 LLM opcional via Ollama local, integração com
Câmaras Municipais e Assembleias Estaduais, plugins para newsrooms e
universidades.

A direção política é clara: **transformar o Hemiciclo em infraestrutura
pública distribuída de inteligência parlamentar**, equivalente em rigor às
plataformas comerciais e em alcance ao que nenhuma plataforma comercial
poderia oferecer -- porque a lógica de produto fechado, por construção,
exclui quem não pode pagar.

A pauta progressista e a pauta conservadora são tratadas com igual
rigor metodológico: o Hemiciclo não é militância disfarçada de software. É
ferramenta de **clareza pública**. Quem usar para defender pauta progressista
tem direito ao mesmo dado que quem usar para defender pauta conservadora.
A neutralidade do método é o que garante que o produto funciona para
**todos os lados** -- e é exatamente isso que torna a ferramenta perigosa
para quem hoje detém monopólio informacional.

---

### Licença

GPL v3. Use, modifique, redistribua. Versões derivadas devem manter a mesma
licença. Esta é a garantia de que o Hemiciclo permanecerá aberto.

---

*"A palavra pública é o solo onde a liberdade se enraíza."* -- Hannah Arendt

*Versão expandida do manifesto, consolidada na release v2.0.0 (sprint S38).
A versão curta original ficou preservada em commits anteriores como
testemunho da progressão do projeto.*
