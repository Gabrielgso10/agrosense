# Contrato do modelo (treino ↔ firmware ↔ dataset)

Este documento amarra o trabalho de programação (Gabriel), infraestrutura (Caio) e
dataset/botânica (Leonardo). Se algo aqui mudar, os três precisam saber.

## Entrada

| Item | Valor |
|---|---|
| Formato | 96 × 96 × 3, RGB888, int8 |
| Recorte | quadrado central da região da planta (no firmware: a região fixa de cada vaso) |
| Redimensionamento | bilinear, direto para 96 × 96 |
| Normalização | dentro do modelo (camada `Rescaling`); o firmware **não** normaliza |
| Quantização | `QuantizePixel()` de `firmware/main/generated/model_settings.h` |

Nunca fixe escala e zero point no código: eles saem da calibração e mudam a cada
modelo. Exemplo real: com imagens que não chegam ao pixel 255, a escala sai 0,945 em
vez de 1,0. O `convert.py` grava os valores corretos em `model_settings.h`.

A câmera entrega RGB565 ou JPEG. A conversão para RGB888, o recorte e o
redimensionamento no firmware precisam reproduzir exatamente `training/data.py`.

## Saída

| Item | Valor |
|---|---|
| Formato | uma pontuação int8 por classe (`kNumClasses`) |
| Probabilidade | `DequantizeOutput()` de `model_settings.h` |
| Decisão | classe de maior pontuação, **se** passar do limiar de confiança |

Abaixo do limiar, o nó não aplica o perfil de espécie e fica no comportamento
conservador (definir o limiar com a matriz de confusão da S6).

## Dataset (Leonardo)

- Uma pasta por classe em `data/<nome da classe>/`; o nome da pasta vira o rótulo.
- Incluir a classe **vazio/fundo**: com regiões fixas, um espaço pode estar sem vaso.
- Parte das fotos deve sair da própria câmera do nó (slot microSD), não só do
  celular, para o modelo não estranhar a imagem real.
- Variar iluminação, ângulo e fundo. As 200 imagens de calibração da quantização
  saem do conjunto de treino, então elas também precisam dessa variação.
