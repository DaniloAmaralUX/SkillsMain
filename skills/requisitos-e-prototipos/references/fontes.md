# Conferir as fontes do pedido

Faça esta etapa no projeto da pessoa, antes de gerar o HTML. A pessoa só precisa indicar o documento ou escrever o pedido no chat. O agente prepara o inventário privado, compara regras e exceções com os originais e registra o que falta decidir.

## Registrar o material

Ao lado de `delivery.json`, mantenha um `sources.json` com uma entrada para **cada insumo**. Em projetos anteriores à introdução deste arquivo, monte o inventário a partir dos originais antes de regenerar. Cada `name` é um nome público único, sem pastas, URLs ou informações identificadoras. O campo `path` localiza o arquivo a partir do protótipo. Para um pedido no chat, salve o texto fornecido em um TXT UTF-8 privado e use, por exemplo, o nome público `Pedido no chat`. Verifique se o texto salvo corresponde ao pedido.

```json
{
  "sources": [{
    "name": "Briefing",
    "path": "../../insumos/briefing.txt",
    "context": [
      {"location": "linha 1", "excerpt": "Briefing de retirada", "reason": "Título do documento"}
    ],
    "coverage": [
      {"location": "linha 2", "excerpt": "Escolher o posto. Retirar apenas no posto escolhido.", "target": "RF01"}
    ]
  }]
}
```

Neste exemplo, RF01 pode citar publicamente só `Retirar apenas no posto escolhido.` na linha 2. O restante da passagem fica associado à mesma regra no inventário privado. Se a terceira linha disser `Prazo em aberto.`, registre uma pendência citando essa linha. Apagar a pendência deixará texto sem cobertura e interromperá a geração.

1. Leia o insumo inteiro. O comando `python "<skill>/scripts/source_check.py" "<arquivo>"` mostra as unidades e o texto efetivamente extraído. A saída é material de trabalho privado. Para DOCX, a numeração inclui parágrafos vazios e de tabelas do corpo, na ordem do arquivo.
2. Para cada requisito ou pendência em `delivery.json`, use o mesmo `source` de `sources.json`, a localização e um trecho literal curto. Espaços e quebras de linha são normalizados. Preserve acentos, sentido e negações. Prefira um trecho contíguo e não identificador. Se o trecho se repetir, especifique a célula, página ou linha, ou cite palavras de contexto suficientes para distingui-lo.
3. Confira o caminho inverso, do texto original até a entrega. Cada passagem com regra, exceção ou lacuna deve estar citada ou associada em `coverage`. Use como `target` o ID do requisito ou o texto exato da pergunta em aberto. Inclua a citação pública desse alvo dentro da passagem indicada. Use `context` com uma justificativa específica para títulos, paginação, dados pessoais dispensáveis e outros conteúdos fora do escopo. Separe regras distintas, mesmo quando aparecerem no mesmo parágrafo. Se faltar uma regra na entrega, crie o requisito ou a pendência correspondente.
4. Execute `python "<skill>/scripts/evidence.py" "<projeto>/delivery.json"` para conferir fontes e cobertura durante a montagem. O build repete essa conferência. A pessoa que revisa a entrega deve confirmar que as classificações e as interações preservam o significado de todas as regras, em especial as exceções.

## Localizações verificadas

| Material | Localização no manifesto e na evidência | Leitura |
|---|---|---|
| PDF com texto selecionável | `p. 1` | Verificação do trecho na página original. Instale `pypdf` no Python que executa o build (`python -m pip install pypdf`) se ainda não houver leitor. A instalação existente de PyMuPDF também é reconhecida. |
| DOCX | `Parágrafo 3`, `cabeçalho 1, parágrafo 1` ou `rodapé 1, parágrafo 1` | Parágrafos do corpo e de tabelas, cabeçalhos e rodapés. Campos automáticos, figuras, alterações controladas e notas com conteúdo exigem cópia textual conferida. |
| XLSX simples, com valores | `Postos!C3` ou `Postos!A2:D3` | Use os valores não vazios na ordem das células. Separe colunas com ` | ` e linhas com `; `. Booleanos aparecem como TRUE/FALSE. Datas, erros, números com formatação especial, fórmulas, gráficos e objetos exigem uma cópia textual ou de valores conferidos. Indique a conversão. |
| Texto UTF-8, Markdown, pedido ou transcrição | `linha 1` ou `linhas 1-3` | Uma unidade por linha do arquivo, incluindo as linhas vazias na numeração. |

Inspecione também o que o extrator de texto deixa de fora, como uma assinatura digitalizada, um diagrama no PDF, uma caixa de texto no Word ou um gráfico na planilha. Uma página sem texto em um PDF interrompe a conferência. Para imagem, digitalização ou áudio, confronte a transcrição com o original, identificando a página/região ou o instante em cada linha. Registre **“Transcrição revisada de …”** como nome público da fonte TXT e explique em `limitations` que a comparação automática atinge a transcrição. Se a leitura não puder ser conferida, registre a parte pendente e obtenha material legível para regras que dependam dela.

Os caminhos, os originais e o inventário ficam no projeto local. O viewer recebe os campos públicos do protótipo e as citações escolhidas para exibição. Revise também o texto e os dados de exemplo das telas antes de compartilhar o HTML.
