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
