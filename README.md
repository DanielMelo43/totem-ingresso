# Totem de Ingressos

Aplicação completa com React, FastAPI e PostgreSQL.

## Executar com Docker

```powershell
Copy-Item .env.docker.example .env
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

- frontend: diretório raiz `frontend`, framework Vite;
- backend: diretório raiz `backend`, framework detectado automaticamente como FastAPI.

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
`backend` com as variáveis de produção carregadas:

```powershell
python scripts/migrate.py
```

Não reutilize a senha do banco como `CPF_ENCRYPTION_KEY` em produção e mantenha essa chave fora do
Git. A perda da chave impede a leitura dos CPFs já criptografados.
