# Totem de Ingressos

Aplicação completa com React, FastAPI e PostgreSQL.

## Executar com Docker

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.docker.example .env }
# Edite POSTGRES_PASSWORD no arquivo .env
docker compose up --build -d
```

Acesse:

- Totem: `http://localhost:8080`
- Swagger da API: `http://localhost:8080/docs`
- Health check: `http://localhost:8080/health`

## Abrir o banco no DBeaver

Cadastre uma conexão PostgreSQL com os dados abaixo:

- Host: `localhost`
- Porta: valor de `POSTGRES_PORT` no `.env` (padrão `5432`)
- Database: valor de `POSTGRES_DB` no `.env`
- Usuário: valor de `POSTGRES_USER` no `.env`
- Senha: valor de `POSTGRES_PASSWORD` no `.env`

O PostgreSQL é publicado apenas em `127.0.0.1`, portanto o DBeaver local consegue acessá-lo sem
expor o banco para outros computadores da rede.

Comandos úteis:

```powershell
docker compose ps
docker compose logs -f
docker compose down
docker compose down -v  # também apaga definitivamente o banco local
```

O PostgreSQL é publicado exclusivamente no loopback da máquina para acesso pelo DBeaver. Backend
e banco comunicam-se pela rede interna do Compose. O volume `postgres_data` preserva os dados entre
reinicializações.

## Publicar na Vercel

O `vercel.json` na raiz publica frontend e backend em um unico projeto.
O PostgreSQL continua no Neon ou em outro provedor externo.

1. Envie os arquivos para o GitHub e importe o repositorio na Vercel.
2. Deixe **Root Directory** na raiz (`./`).
3. Selecione **Framework Preset: Other**. O arquivo define os comandos de
   install/build e a pasta de saida automaticamente.
4. Cadastre as variaveis abaixo e clique em **Deploy**:

```text
DATABASE_URL=postgresql+psycopg://usuario:senha@host/banco?sslmode=require
CPF_ENCRYPTION_KEY=<sua-chave-Fernet-secreta>
```

Ao reutilizar o banco, preserve a mesma CPF_ENCRYPTION_KEY para conseguir ler
os CPFs existentes. Nunca salve essas credenciais no Git.
Para um banco novo, gere uma chave com Python e cryptography instalados:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Deixe **VITE_API_URL ausente** no projeto unificado. Remova qualquer valor antigo
antes do build para que o frontend use a API no mesmo dominio.
FRONTEND_ORIGINS so precisa ser configurada para acesso por outro dominio.

Depois do deploy, confira `/`, `/health` e `/docs` no dominio gerado.
Para aplicar migrations a um banco existente, execute em `src/backend`, com
as variaveis do banco correto carregadas: `python scripts/migrate.py`.

Os arquivos Vercel dentro de `src/frontend` e `src/backend` continuam disponiveis
para deploys separados. O deploy unificado usa o arquivo da raiz.

## Organização

```text
src/
  backend/           # FastAPI, Alembic, scripts e dependências Python
  frontend/          # React/Vite, public e dependências Node
tests/              # Testes automatizados (backend/)
docs/               # Guias do backend, frontend e segurança
assets/             # Reservado para arquivos estáticos compartilhados
config/             # Configuração centralizada do pytest
compose.yaml        # Orquestração Docker
.env.docker.example # Modelo de ambiente do Docker
.gitignore
README.md
```

Não há necessidade de `data/`: os dados persistidos ficam no PostgreSQL e os
catálogos iniciais continuam no código do backend. `src/frontend/public` permanece
junto ao Vite. Manifestos, lockfile, Dockerfiles, configurações Vercel, TypeScript,
Vite, Nginx e Alembic permanecem junto às respectivas aplicações.

Documentação detalhada: [backend](docs/backend.md), [frontend](docs/frontend.md)
e [segurança](docs/SECURITY.md). Os caminhos internos dos guias são relativos à
aplicação indicada.

## Desenvolvimento local (PowerShell)

Use Python 3.12, conforme `src/backend/pyproject.toml`, e Node.js 22.
O Dockerfile existente do backend utiliza Python 3.13; essa diferença preexistente
foi preservada nesta reorganização. Execute a partir da raiz:

```powershell
cd src/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Ajuste a conexão PostgreSQL e a chave de criptografia no .env.
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe run.py
```

Em outro terminal, a partir da raiz:

```powershell
cd src/frontend
npm.cmd ci
npm.cmd run dev
```

A API atende em `http://localhost:8000` e o Vite informa a URL do frontend
(normalmente `http://localhost:5173`). `npm.cmd` evita depender da política de
execução de scripts PowerShell; em outros shells, use `npm`.

### Variáveis de ambiente

- O Compose continua lendo `.env` na raiz e repassa as variáveis aos containers.
- O backend lê `.env` no diretório de execução: inicie-o em `src/backend`.
  Ele não carrega `.env.local` automaticamente; variáveis fornecidas pelo ambiente
  continuam tendo prioridade.
- O Vite lê `.env`, `.env.local` e os arquivos por modo em `src/frontend`.
  Use `VITE_API_URL` para apontar para outra API; essa variável é pública no build.
- Os arquivos locais foram preservados e os exemplos `.env.example` permanecem
  versionados. Não sobrescreva arquivos locais ao configurar o projeto.

### Testes e build

A partir da raiz, após instalar as dependências:

```powershell
src/backend/.venv/Scripts/python.exe -m pytest -c config/pytest.ini
npm.cmd --prefix src/frontend run build
```

Os testes usam SQLite em memória, sem precisar de PostgreSQL. O frontend não possui
suíte automatizada própria; o build verifica TypeScript e gera `src/frontend/dist`.
Para visualizar o build: `npm.cmd --prefix src/frontend run preview`.

Para validar a configuração e construir as imagens Docker, a partir da raiz:

```powershell
docker compose config --quiet
docker compose build
```

Para publicar tudo em um projeto Vercel existente, ajuste Root Directory para
`./` e Framework Preset para Other. Os arquivos locais nao alteram o painel.
