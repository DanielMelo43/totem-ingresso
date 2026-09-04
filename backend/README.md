# API do Totem de Ingressos

Backend FastAPI para catálogo, disponibilidade de assentos, reserva, pedido e pagamento simulado.

O backend aplica consultas parametrizadas pelo SQLAlchemy, validação independente do frontend,
idempotência persistida, rate limiting por IP e dispositivo, locks com TTL, transações e respostas
de erro padronizadas com `traceId`.

## Executar

No PowerShell, a partir de `backend`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
alembic upgrade head
python run.py
```

A API estará em `http://localhost:8000`, com documentação interativa em `http://localhost:8000/docs`.
O catálogo inicial é inserido na primeira execução da API, depois que a migração preparar o banco.

## PostgreSQL

Crie um usuário e um banco vazio no PostgreSQL local, usando uma senha própria:

```sql
CREATE ROLE totem WITH LOGIN PASSWORD 'sua-senha-segura';
CREATE DATABASE totem_ingresso OWNER totem ENCODING 'UTF8';
```

Depois ajuste a conexão no `.env` sem versionar a senha:

```dotenv
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=totem_ingresso
DATABASE_USER=totem
DATABASE_PASSWORD=sua-senha-segura
CPF_ENCRYPTION_KEY=sua-chave-fernet
```

Em produção, `CPF_ENCRYPTION_KEY` deve ser independente da senha do banco e permanecer fora do
repositório. Gere uma chave com:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Se a chave for omitida no Docker local, ela será derivada da senha do banco. Alterar ou perder a
chave impede recuperar CPFs já gravados. O PostgreSQL armazena somente o valor criptografado e um
HMAC usado para consultas exatas.

O esquema é controlado pelo Alembic:

```powershell
alembic upgrade head       # aplica todas as migrações
alembic current            # mostra a versão do banco
alembic downgrade -1       # desfaz a última migração
```

## Fluxo principal

1. `GET /api/v1/showtimes?on=2026-09-04`
2. `GET /api/v1/showtimes/{id}/seats`
3. `GET /api/v1/ticket-types` e `GET /api/v1/products`
4. `POST /api/v1/reservations` bloqueia os assentos imediatamente ao serem selecionados.
5. `POST /api/v1/orders` converte a reserva em pedido e calcula o preço no servidor.
6. `POST /api/v1/orders/{id}/payment` confirma o pagamento simulado.
7. `POST /api/v1/reservations/{id}/cancel` ou `POST /api/v1/orders/{id}/cancel` libera a compra.
8. `GET /api/v1/orders/{id}/status` recupera o estado após perda de conexão ou reinício.

Todos os `POST` exigem os cabeçalhos abaixo. Uma chave deve ser reutilizada somente ao repetir
a mesma ação e o mesmo corpo:

```http
Idempotency-Key: 2ef74d91-6128-40f1-b5be-7aed57a8292e
X-Device-ID: totem-entrada-01
```

Erros seguem um único contrato seguro:

```json
{
  "erro": {
    "codigo": "ASSENTO_INDISPONIVEL",
    "mensagem": "Um ou mais assentos não estão disponíveis.",
    "status": 409,
    "timestamp": "2026-09-04T13:20:00Z",
    "traceId": "a1b2c3d4"
  }
}
```

Os limites, timeouts, origens CORS e TTLs podem ser alterados no `.env`. Os registros de
idempotência, rate limit, locks e circuit breaker são persistidos no PostgreSQL e compartilhados
pelas instâncias.

Configure o frontend com `VITE_API_URL=http://localhost:8000`.
