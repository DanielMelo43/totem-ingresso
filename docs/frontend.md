# Totem de Ingressos

Protótipo funcional touch-first para um totem de autoatendimento de cinema. O fluxo inclui catálogo e sessões, mapa de assentos, tipos de ingresso, bomboniere, identificação com teclado virtual, pagamento simulado e confirmação.

## Executar

Requer Node.js 20 ou superior. Execute os comandos a partir de `src/frontend`.

```bash
npm ci
npm run dev
```

Para gerar a versão de produção:

```bash
npm run build
npm run preview
```

Abra o endereço exibido pelo Vite. Para uso em totem, inicie o Chromium com `--kiosk` apontando para a URL do build publicado.

## Configuração

Se necessário, configure `VITE_API_URL=http://localhost:8000` em `.env.local`. A API FastAPI deve estar disponível em `http://localhost:8000`.
Ao selecionar um assento, o frontend cria imediatamente uma reserva no servidor e atualiza a
disponibilidade a cada 3 segundos. A reserva é convertida em pedido no pagamento ou liberada no
cancelamento e na expiração por inatividade.

## Comportamentos incluídos

- Alvos de toque com no mínimo 44 px e layout adaptável a telas estreitas.
- Carrinho preservado entre todas as etapas da compra.
- Validação de assentos e quantidades de ingressos.
- Aviso após 50 segundos de inatividade e reinício automático após 60 segundos.
- Cancelamento disponível durante todo o fluxo.
- Pagamento apenas simulado; nenhum dado financeiro é coletado ou armazenado.

## Segurança

- Limites de caracteres, campos obrigatórios, máscara de CPF e inputs tipados.
- Identificação validada tanto pelo teclado virtual quanto pela entrada física.
- `src/security.ts` contém o cliente HTTP e preserva as chaves de idempotência para evitar compras duplicadas.
- Os controles adicionais de cabeçalhos HTTP, filtro de caminhos e timeouts customizados foram removidos.
- O escopo completo e os controles de integridade e confidencialidade mantidos estão em [SECURITY.md](SECURITY.md).

## Estrutura

- `src/App.tsx`: fluxo, estado do pedido e componentes reutilizáveis.
- `src/data.ts`: tipos compartilhados, datas da navegação e formatação monetária.
- `src/styles.css`: tema, componentes, responsividade e estados visuais.
