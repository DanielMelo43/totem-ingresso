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

Este monorepo deve ser cadastrado como dois projetos na Vercel:

- frontend: diretório raiz `src/frontend`, framework Vite;
- backend: diretório raiz `src/backend`, framework detectado automaticamente como FastAPI.

O PostgreSQL do Docker é apenas local. Em produção, vincule ao projeto do backend um PostgreSQL
gerenciado (por exemplo, Neon pela Vercel Marketplace) e configure estas variáveis:

```text
DATABASE_URL=postgresql+psycopg://usuario:senha@host/banco?sslmode=require
CPF_ENCRYPTION_KEY=<chave-Fernet-independente-e-secreta>
FRONTEND_ORIGINS=https://<projeto-frontend>.vercel.app
```

No projeto do frontend, configure antes do build:

```text
VITE_API_URL=https://<projeto-backend>.vercel.app
```

Antes do primeiro deploy do backend (e sempre que houver uma nova migration), execute a partir de
`src/backend` com as variáveis de produção carregadas:

```powershell
python scripts/migrate.py
```

Não reutilize a senha do banco como `CPF_ENCRYPTION_KEY` em produção e mantenha essa chave fora do
Git. A perda da chave impede a leitura dos CPFs já criptografados.

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

Nos projetos Vercel já existentes, ajuste o campo Root Directory para
`src/backend` e `src/frontend`, respectivamente. Essa configuração externa não é
alterada pelos arquivos locais; nenhum deploy é necessário para revisar a estrutura.
