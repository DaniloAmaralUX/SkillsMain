# Montagem

Execute a partir do projeto da pessoa com Python 3.10+ e Node.js 18+. Substitua SKILL pelo diretório absoluto da instalação. A visualização do HTML final funciona offline em um navegador moderno.

```sh
python "SKILL/scripts/viewer.py" init "prototypes/meu-projeto"
python "SKILL/scripts/viewer.py" build "prototypes/meu-projeto"
```

Entre os comandos, preencha as telas, o projeto e os dados abaixo. Complete o [inventário privado de fontes](fontes.md). Para ler PDF com texto, use o leitor da instalação Python ou instale a versão testada com `python -m pip install -r "SKILL/requirements-pdf.txt"`.

- **project.json**: id único, name, flows com id/title/sum, navigation opcional. Fluxos no painel lateral e passos internos na prévia são independentes.
- **screens.js**: registre cada fluxo uma vez com `Proto.versions(id, [{name, axis, tryThis, tradeoff, render(root,ctx)}])`. Alterne fluxos com `ctx.go(id)`. Estado de negócio compartilhado fica fora de render. Retorne a limpeza de listeners e modais ao sair. Escape valores interpolados com `Kit.esc`.
- **styles.css**: apenas composição local dentro de `.ph`, usando tokens do kit. Preserve o painel e os temas.
- **delivery.json**: versão 1.0, requisitos com fonte e aceite, questões em aberto e listas textuais de decisões visuais, simulações e limitações. Exemplo de **forma**, não de domínio:

```json
{
  "schema_version": "1.0",
  "requirements": [{
    "id": "RF01", "flow": "escolher",
    "description": "Mostrar somente itens disponíveis.",
    "acceptance": "Na seleção, um item indisponível não pode ser escolhido.",
    "evidence": [{"source": "pedido no chat", "location": "linha 1", "excerpt": "Só posso escolher itens disponíveis."}]
  }],
  "open_questions": [], "assumptions": [], "simulations": [], "limitations": []
}
```

Para uma pendência use `{"kind":"gap","question":"…","evidence":[…]}` com a passagem que deixa a decisão em aberto. Para `conflict`, inclua as duas passagens. Use localizações verificáveis conforme o [formato da fonte](fontes.md). No exemplo de chat acima, transcreva a mensagem em TXT e use `linha 1` como localização. Identifique transcrições e omissões.

## Fidelidade e componentes

A referência é o [skeleton original de Apparício Bueno](https://github.com/appariciojunior/prototype-viewer). O [kit original](https://github.com/appariciojunior/prototype-viewer/blob/main/template/src/kit.css) usa superfícies neutras, hierarquia por espaçamento e um acento para ações. A cópia Pitang incluída compõe o mesmo conteúdo nas molduras iOS, Android e Web.

Use o [Kit distribuído](../assets/viewer/template/src/kit.js) e suas [classes](../assets/viewer/template/src/kit.css). Monte o cabeçalho com `Kit.bar({title,icons:[]})`; organize a tarefa em `.sk-scroll`, `.sk-pad`, `.sk-stack` e `.sk-card`. Use `.sk-btn` para ações, os campos nativos do Kit para edição e `Kit.sheet` para confirmação ou seleção contextual quando a tarefa precisar. Monte abas apenas com destinos previstos. Use `Kit.media` para um espaço de mídia necessário e mantenha rótulos/valores reais onde a pessoa precisa decidir. Para uma ação específica, componha os elementos nativos com as mesmas classes e tokens. Use um resumo de confirmação somente quando sustentado pelo material. Preserve navegação por teclado, rótulos e foco visível.

O comando `build` prepara a revisão em `.viewer-build/draft/`. Após o [aceite das telas](aceite.md), `finalize` grava `dist/<id>.html`, `dist/<id>-SPEC.md` e o relatório da geração. O botão **Exportar SPEC.md** usa o mesmo texto da especificação em disco.
