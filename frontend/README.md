# Totem de Ingressos

Protótipo funcional touch-first para um totem de autoatendimento de cinema. O fluxo inclui catálogo e sessões, mapa de assentos, tipos de ingresso, bomboniere, identificação com teclado virtual, pagamento simulado e confirmação.

## Executar

Requer Node.js 20 ou superior.

```bash
npm install
npm run dev
```

Para gerar a versão de produção:

```bash
npm run build
npm run preview
```

Abra o endereço exibido pelo Vite. Para uso em totem, inicie o Chromium com `--kiosk` apontando para a URL do build publicado.

## Configuração

Copie `.env.example` para `.env`. A API FastAPI deve estar disponível em `http://localhost:8000`.
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

- O frontend restringe e valida os formatos aceitos, usa a renderização escapada do React e não injeta HTML recebido de usuários.
- `src/security.ts` fornece um cliente HTTP com JSON, timeout, caminhos restritos e mensagens públicas genéricas. Respostas técnicas são registradas somente no ambiente de desenvolvimento.
- Uma barreira global impede que stack traces e detalhes internos apareçam na tela do totem.
- O servidor Vite de desenvolvimento/preview envia CSP e cabeçalhos contra framing, MIME sniffing, vazamento de referência e acesso indevido a dispositivos. O servidor de produção deve replicar esses cabeçalhos.
- Prepared statements, validação definitiva, logs protegidos e rate limiting por IP/dispositivo devem obrigatoriamente ser implementados na API. Restrições no navegador são apenas uma camada complementar e não protegem o banco de dados sozinhas.

## Estrutura

- `src/App.tsx`: fluxo, estado do pedido e componentes reutilizáveis.
- `src/data.ts`: tipos compartilhados, datas da navegação e formatação monetária.
- `src/styles.css`: tema, componentes, responsividade e estados visuais.
