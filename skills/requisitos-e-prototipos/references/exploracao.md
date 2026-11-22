# A pergunta que o protótipo responde

Determine pelos insumos o que a pessoa pode aprender ao experimentar o protótipo. A pergunta fica no campo `axis` da versão e os passos para testá-la em `tryThis`. Use-os como roteiro de trabalho e de demonstração. Construa diretamente a versão mais simples que permita observar o resultado.

**Lógica.** Quando a dúvida envolver permissões, exceções ou transições, modele as decisões fora dos eventos do DOM. Depois de cada ação, apresente os dados que mudaram em termos do domínio. Permita explorar livremente. Quando o pedido for testar um modelo difícil, ofereça também cenários guiados, cada um com ponto de partida reproduzível e passos acionáveis. Use a mesma lógica nos dois percursos.

Na reserva de bicicletas, a pergunta é se trocar a loja preserva a configuração e respeita o estoque. Escolher Urbana no Centro, cancelar uma troca e depois salvá-la para Praia permite observar as duas consequências. Tentar escolher uma bicicleta na Lagoa exercita o bloqueio. O teste termina conferindo a loja e o valor na confirmação.

**Interface.** Escolha a estrutura mais adequada aos objetivos e restrições do briefing. Se a pessoa pedir alternativas, mantenha os mesmos dados e regras em cada versão do mesmo fluxo. Varie a hierarquia, a posição da decisão ou a sequência de interação. Use a URL do viewer com `flow` e `v` para retornar à alternativa exata. Valide cada versão entregue.

Registre qual pergunta o ensaio respondeu, a observação e o que continua dependendo da equipe. Uma validação no protótipo é uma observação de comportamento simulado. Transforme-a em regra de negócio somente quando houver fonte para essa regra.

Método adaptado da [skill prototype de Matt Pocock](https://github.com/mattpocock/skills).
