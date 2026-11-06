# Fotos originais — importação de 2026-11-06

71 imagens JPEG enviadas pelo autor ao Google Drive em 6 de novembro de 2026.
Os nomes e bytes originais foram preservados (10.409.456 bytes no total).
A data no nome dos arquivos é 2026-11-05; a pasta identifica a data da importação.

`manifesto.json` registra nome, tamanho e SHA-256 de cada imagem. Os rótulos estão
pendentes (`null`); não foram inferidos automaticamente das fotos.

## Preparação para treino

Este lote é um arquivo de originais, não a entrada direta de `train.py`.
Há fotos com várias áreas de plantio. Recorte cada região relevante, confirme a
espécie com o responsável pelo cultivo e salve os recortes em
`data/especies/<classe>/`, usando os rótulos adotados pelo projeto.
Não classifique uma área sem planta visível pela espécie que foi semeada.

Mantenha os recortes de uma mesma foto/sessão no mesmo conjunto ao separar treino
e avaliação, para evitar vazamento. O carregador atual faz divisão aleatória por
imagem; uma avaliação independente por sessão requer preparação adicional.

Os arquivos originais deste lote são versionados no Git; os dados preparados em
`data/especies/` continuam sob a regra geral do `.gitignore`.
