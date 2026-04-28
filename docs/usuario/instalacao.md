# Guia de instalação -- Linux, macOS e Windows

> Hemiciclo roda nativamente nos três sistemas operacionais majoritários.
> No Linux/macOS use ``./install.sh`` + ``./run.sh``; no Windows 10/11 use
> ``install.bat`` + ``run.bat`` (paridade total desde a sprint S36).

## Pré-requisitos

| Item | Versão mínima |
|---|---|
| Python | 3.11 ou 3.12 |
| RAM disponível | 4 GB (8 GB com modelo bge-m3 ativo) |
| Espaço em disco | 5 GB sem modelo de embeddings, 8 GB com `bge-m3` (S28) |
| Conexão | necessária só para `./install.sh` e coleta inicial; roda offline depois |

## Passo 1 -- Garantir Python 3.11+

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
python3 --version  # deve mostrar 3.11.x ou superior
```

### Fedora

```bash
sudo dnf install -y python3.11
python3 --version
```

### macOS (Homebrew)

```bash
brew install python@3.11
python3 --version
```

> **macOS Apple Silicon (M1/M2/M3):** o `uv` da Astral suporta arm64 nativamente
> desde a versão 0.4. Não há passo extra.

### Windows 10/11

Mínimo: **Windows 10 build 1809** (suporte nativo a UTF-8 no console). Windows 11 ideal.
Três caminhos válidos para instalar o Python 3.11+:

```cmd
:: Opção 1 -- instalador oficial python.org (recomendado)
:: Baixe "Windows installer (64-bit)" em https://python.org/downloads
:: e MARQUE a checkbox "Add Python to PATH" antes de clicar em Install Now.

:: Opção 2 -- winget (Windows Package Manager)
winget install Python.Python.3.11

:: Opção 3 -- Microsoft Store
:: Procure "Python 3.11" e instale (cria o launcher ``py``).
```

Verifique:

```cmd
python --version
:: ou, se instalado via Microsoft Store:
py -3.11 --version
```

Se ambos falharem, o `install.bat` aborta com mensagem clara apontando
[python.org/downloads](https://python.org/downloads).

> **Defender / SmartScreen:** o instalador oficial do `uv` (baixado pelo
> `install.bat` via PowerShell + `irm https://astral.sh/uv/install.ps1`) pode ser
> sinalizado pelo Defender em redes corporativas. Mitigação: clique em "Mais
> informações > Executar assim mesmo" ou libere `astral.sh` no antivírus.

Se `python3 --version` retornar uma versão menor que 3.11, o `./install.sh`
vai abortar com mensagem clara apontando para [python.org/downloads](https://python.org/downloads).

## Passo 2 -- Clonar e instalar

**Linux / macOS:**

```bash
git clone https://github.com/AndreBFarias/Hemiciclo.git
cd Hemiciclo
./install.sh
```

**Windows 10/11 (CMD ou PowerShell):**

```cmd
git clone https://github.com/AndreBFarias/Hemiciclo.git
cd Hemiciclo
install.bat
```

O `./install.sh` (Linux/macOS) e o `install.bat` (Windows) têm paridade
funcional 1:1 desde a sprint S36. Ambos:

1. Detectam o sistema operacional e o Python pré-instalado.
2. Validam versão `>= 3.11` (Windows: cascata `where python` -> `py -3.11`).
3. Instalam o gerenciador `uv` no diretório do usuário se ainda não existir.
4. Rodam `uv sync --all-extras` para popular `.venv/`.
5. Imprimem o tempo decorrido e o próximo comando.

A instalação leva tipicamente **3 a 5 minutos** em conexão de banda larga.

> Em ambiente CI ou para verificar se o ambiente está apto sem efetivamente
> instalar, rode `./install.sh --check` (Linux/macOS) ou `install.bat --check`
> (Windows). Para inspecionar o plano completo (incluindo o passo opcional
> de `--com-modelo`) sem efetivar nada, use `--dry-run`.

### Instalação completa com modelo de embeddings (`--com-modelo`)

Por padrão a instalação **não baixa** o modelo `BAAI/bge-m3` (~2GB).
A camada C3 do classificador (embeddings semânticos) entra em **skip
silencioso** quando o modelo não está em cache, gerando relatórios sem
o eixo de proximidade semântica. Isso é intencional para que a primeira
experiência seja rápida.

Se você quer rodar o `pipeline_real` ponta-a-ponta já na primeira sessão,
adicione a flag `--com-modelo` (alias: `--com-bge`):

**Linux / macOS:**

```bash
./install.sh --com-modelo
```

**Windows 10/11:**

```cmd
install.bat --com-modelo
```

O script roda o passo regular (`uv sync --all-extras`) e em seguida
dispara o download do `bge-m3` via `FlagEmbedding`. O modelo é cacheado
em `~/.cache/huggingface/hub/` (Linux/macOS) ou
`%USERPROFILE%\.cache\huggingface\hub\` (Windows) e fica disponível
para todas as sessões futuras -- inclusive as de outros projetos que
também usem `bge-m3`.

**Trade-off:**

| Cenário | Tempo total | Espaço extra | Camada C3 |
|---|---|---|---|
| Sem flag (default) | 3-5 min | 0 GB | skip silencioso |
| `--com-modelo` | 8-20 min | ~2 GB | ativa |

Falhas durante o download (sem internet, Hugging Face Hub fora do ar,
disco cheio) **não abortam** a instalação base: o script imprime um aviso
PT-BR claro e o dashboard continua utilizável. Você pode tentar de novo
manualmente depois:

```bash
uv run python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)"
```

Para **planejar** a instalação sem efetivar nada (útil para inspecionar
quanto vai gastar em rede e disco antes de comprometer):

```bash
./install.sh --com-modelo --dry-run
```

## Passo 3 -- Subir o dashboard

**Linux / macOS:**

```bash
./run.sh
```

**Windows 10/11:**

```cmd
run.bat
```

O Streamlit abre o navegador automaticamente em `http://localhost:8501`.

Use `Ctrl+C` no terminal para encerrar.

## Verificação manual

Após `./run.sh`, você deve ver:

- A página inicial **Bem-vindo ao Hemiciclo** com o storytelling do
  manifesto curto.
- Quatro botões de navegação no topo: **Início**, **Pesquisas**, **Nova
  pesquisa** e **Sobre**.
- A aba **Pesquisas** mostra um CTA grande "Você ainda não fez nenhuma
  pesquisa" -- esperado em primeira execução.
- A aba **Nova pesquisa** mostra um formulário com tópico, casas,
  legislaturas, UFs, partidos, período e camadas de análise.
- Ao submeter o formulário, o pipeline real (S30) dispara um subprocess
  detached que coleta, faz ETL, classifica e produz o relatório
  multidimensional. O progresso aparece com polling a cada 2 segundos.
- A aba **Sobre** mostra o manifesto, a stack técnica e a licença GPL v3.

## Troubleshooting

### `python3: command not found`

Você não tem Python 3 instalado. Veja [Passo 1](#passo-1----garantir-python-311).

### `Python 3.10 detectado, requer 3.11+`

A versão do Python no PATH é antiga. No Ubuntu LTS isso é comum -- instale
o `python3.11` em paralelo (não substitui o default do sistema):

```bash
sudo apt-get install -y python3.11 python3.11-venv
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version
```

### Certificado SSL falha ao baixar `uv`

Provavelmente proxy corporativo. Defina as variáveis `HTTP_PROXY` /
`HTTPS_PROXY` e tente novamente, ou baixe manualmente o instalador do uv
em [astral.sh/uv](https://astral.sh/uv).

### `streamlit: command not found` ao rodar `./run.sh`

A `.venv` não foi criada ou está vazia. Rode novamente:

```bash
uv sync --all-extras
```

### Browser não abre automaticamente

Acesse manualmente <http://localhost:8501>. Se rodando em servidor remoto,
use `ssh -L 8501:localhost:8501 usuario@servidor` para fazer port-forwarding.

### `Address already in use` na porta 8501

Outra instância do Streamlit já está rodando. Encerre com:

```bash
pkill -f "streamlit run"
```

Ou rode em outra porta:

```bash
uv run streamlit run src/hemiciclo/dashboard/app.py --server.port=8502
```

### Troubleshooting específico de Windows

**`'python' is not recognized as an internal or external command`**

O PATH do CMD não inclui Python. Reinstale com a checkbox "Add Python to PATH"
marcada, ou use o launcher: `py -3.11 --version`. O `install.bat` cobre
ambos os casos automaticamente.

**Mensagens com acento aparecem como `?` ou caracteres quebrados**

Seu terminal não está em UTF-8. Soluções:

1. Use o **Windows Terminal** (Microsoft Store, gratuito) -- já vem em UTF-8.
2. Ou troque para PowerShell 7 (`pwsh`) que usa UTF-8 por padrão.
3. Em CMD legado, rode `chcp 65001` antes do `install.bat` (o script já
   tenta isso, mas em sistemas muito antigos pode falhar).

**`uv: command not found` após `install.bat`**

O instalador do uv coloca o binário em `%USERPROFILE%\.local\bin`, que
pode não estar no PATH ainda. Soluções:

```cmd
:: temporário (sessão atual)
set PATH=%USERPROFILE%\.local\bin;%PATH%

:: ou faça logout/login para o PATH propagar permanentemente
```

**Defender / antivírus bloqueia download do `uv`**

Libere `astral.sh` na whitelist do antivírus temporariamente, ou baixe
manualmente o instalador em [astral.sh/uv](https://astral.sh/uv) e rode com
`powershell -ExecutionPolicy Bypass`.

**Path com espaços (ex: `C:\Users\Andre Farias\Hemiciclo`)**

O `install.bat` já trata aspas em `cd /d "%DIR%"`. Se mesmo assim falhar,
mova o repo para um path sem espaços (ex: `C:\src\Hemiciclo`).

**Prefere ambiente Linux dentro do Windows?**

WSL2 + Ubuntu 22.04 + `./install.sh` continua funcionando como alternativa.
Não é exclusivo do nativo: escolha o que preferir.

## Desinstalar

**Linux / macOS:**

```bash
rm -rf .venv
rm -rf ~/hemiciclo  # apaga TODAS as suas sessões; faça backup antes
```

**Windows 10/11:**

```cmd
rmdir /s /q .venv
rmdir /s /q "%USERPROFILE%\hemiciclo"  :: apaga TODAS as suas sessões; faça backup antes
```
