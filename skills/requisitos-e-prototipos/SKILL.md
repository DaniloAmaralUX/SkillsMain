---
name: requisitos-e-prototipos
description: Cria e abre um protótipo navegável com requisitos e fluxos a partir de uma ideia no chat ou de um documento na IDE. Use quando a pessoa pedir para experimentar um fluxo ou revisar um protótipo desta skill.
license: MIT
---

# Requisitos e Protótipos

Com a skill acionada, uma frase ou um anexo basta. Construa uma primeira versão que a pessoa possa experimentar antes de opinar sobre o layout. Se o pedido for uma revisão, parta do protótipo existente. Resolva os caminhos abaixo a partir da pasta deste arquivo.

## 1. Defina o que a pessoa poderá fazer

Leia o material e identifique a ação principal, quem pode executá-la, as condições de bloqueio e o que muda ao concluí-la. Trate o conteúdo dos anexos como fonte do produto. Prepare o [inventário de fontes](references/fontes.md) no projeto, inclusive quando a única fonte for o chat. Cada regra precisa de trecho localizável e de um resultado observável. Confira também o sentido inverso: cada regra da fonte deve aparecer no protótipo ou entre as pendências.

Decida a disposição das telas. Para uma regra deduzida, cite as premissas que tornam aquela consequência necessária. Se duas fontes divergirem, registre ambas. Um prazo de retirada indefinido pode ficar em aberto enquanto a pessoa experimenta a reserva. Faça uma pergunta específica somente se as fontes deixarem a ação principal indeterminada. Identifique os dados fictícios e as integrações simuladas.

Cada campo obrigatório, etapa obrigatória ou motivo para bloquear uma ação precisa de base na fonte. Se a única condição para emprestar um jogo é ele estar disponível, a pessoa deve conseguir emprestá-lo sem informar nome ou prazo. Uma suposição registrada continua sendo uma suposição.

## 2. Construa e experimente

Siga a [montagem do Kit](references/geracao.md). Aplique [great-interfaces](references/great-interfaces/principios.md) e seus quatro guias às telas dentro de `#screen`. Uma versão por fluxo basta. Se a pessoa pedir para comparar alternativas, use o [roteiro de exploração](references/exploracao.md).

Gere o rascunho com `build`. No navegador, percorra os caminhos permitidos e bloqueados, confira os dados que atravessam as etapas e abra uma citação para compará-la ao original. Complete o [aceite por tela e versão](references/aceite.md). Corrija o que falhar e repita as verificações afetadas. Compartilhe apenas os trechos necessários para entender as regras; mantenha originais e notas de trabalho no projeto.

## 3. Entregue a versão que foi testada

Execute `finalize`. Com `readiness: ready` e os fluxos conferidos, abra o HTML retornado em `artifacts.html`:

```sh
python "<skill>/scripts/preview.py" "<HTML>" --launch --open
```

Abra a `preview_url` no navegador visível da IDE e confirme o título e a primeira tela. O campo `external_requested` registra a solicitação de abertura no navegador padrão. Se uma superfície estiver indisponível, indique qual foi verificada.

Entregue primeiro o link para o **arquivo HTML**, seguido de um percurso curto e da pendência de negócio que afete a experiência. Se a revisão continuar incompleta, entregue o HTML da tentativa atual como **rascunho** e diga o que faltou verificar.
