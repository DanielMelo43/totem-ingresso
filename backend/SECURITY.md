# Controles de segurança implementados

Este backend segue `regras-backend-controle-requisicoes-e-erros.md` nos recursos atualmente
existentes.

- Todas as consultas usam SQLAlchemy com parâmetros vinculados. O único SQL textual é o
  `SELECT 1` constante do health check, sem entrada do usuário.
- Todo endpoint `POST` exige `Idempotency-Key`; estado, hash da requisição, status e resposta são
  persistidos. Repetições devolvem o mesmo resultado e uso da chave com outro corpo retorna 409.
- Rate limiting é persistido por IP e `X-Device-ID`, com limites distintos para leitura, pedido,
  pagamento e outras escritas. Respostas 429 incluem `Retry-After`.
- Pagamentos usam lock persistido com TTL. Reservas usam atualização condicional dentro da
  transação para impedir que duas requisições ocupem o mesmo assento.
- Exceções HTTP, validação, banco e falhas inesperadas passam por handlers centrais. Toda resposta
  de erro contém código, mensagem pública, status, timestamp e `traceId`; detalhes e stack traces
  ficam somente nos logs.
- Corpo, identificadores e campos têm limites e validação no servidor. Requisições possuem limite
  de tamanho e timeout global.
- CPFs são armazenados com criptografia autenticada Fernet e nunca em texto puro. Um HMAC separado
  permite busca exata sem descriptografar ou revelar o documento no banco.
- A criação do pedido, seus itens e a reserva de assentos são atômicas. A confirmação do pagamento
  e o estado do pedido também são persistidos.
- O adaptador de pagamento possui timeout explícito e circuit breaker persistido. Timeout mantém o
  pedido pendente para consulta e reconciliação, sem registrar sucesso indevido.
- `GET /api/v1/orders/{id}/status` permite retomar o fluxo após perda de conexão ou energia.
- `GET /health` verifica banco e estado do circuito do gateway.
- Respostas recebem `X-Trace-ID`, `nosniff`, proteção contra framing, política de referência e
  `Cache-Control: no-store`. CORS permite somente as origens configuradas.

Proteção de login/senha não se aplica: esta API não possui autenticação por credenciais. Caso esse
recurso seja adicionado, ele deverá ter bucket próprio, bloqueio temporário e auditoria. Impressão
e filas também não estão acopladas ao fluxo atual; uma futura impressão deve ser assíncrona e não
bloquear a confirmação já persistida do pedido.
