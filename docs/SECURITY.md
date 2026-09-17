# Segurança conforme as imagens de referência

## Frontend

- Limites de caracteres no CPF e no e-mail, inclusive no teclado virtual.
- Campos obrigatórios e bloqueio de avanço sem identificação válida.
- Máscara do CPF e normalização dos caracteres de entrada.
- Input real com `type="email"` para e-mail; CPF usa `type="text"` com
  `inputMode="numeric"` para permitir máscara e zeros iniciais.
- Validação nativa antes de continuar, além da validação do CPF.

## Backend: confidencialidade, integridade e disponibilidade

- Confidencialidade: erros públicos não incluem exceções, chaves ou detalhes do banco.
  A criptografia de CPFs existentes e novos foi mantida como parte da confidencialidade.
- Integridade: preços e totais vêm do banco, com validação no servidor. Transações,
  reserva exclusiva de assentos e idempotência impedem vendas ou cobranças duplicadas.
- Disponibilidade: o Compose mantém health checks e reinício dos serviços. A configuração
  atual tem uma instância do backend; não implementa o balanceamento de carga citado na
  imagem. Esta alteração remove controles extras, sem ampliar a infraestrutura.

## Controles removidos

Rate limiting por IP/dispositivo e seu helper no frontend, circuit breaker do pagamento,
timeouts customizados de requisição/pagamento, limite global customizado de corpo HTTP,
filtro de caminhos do cliente HTTP e cabeçalhos CSP, anti-framing, MIME, referrer,
permissions e isolamento de origem. Os defaults das ferramentas continuam válidos.

CORS continua necessário para o frontend acessar a API em outra origem. O tratamento de
erros e a renderização padrão do React permanecem. Tabelas e migrações históricas de
rate limiting e circuit breaker foram preservadas para não alterar bancos existentes;
não são mais utilizadas no processamento de requisições.
