# AgroSense — ponto de partida do nó de borda

O nó fotografa os vasos, identifica a espécie de cada um com uma CNN rodando no
ESP32-S3 (TinyML) e decide a irrigação localmente, com os limiares daquela espécie.
A nuvem só recebe telemetria por MQTT; sem rede, tudo continua funcionando.

```
Treino (PC)   train.py ──► convert.py ──► compare.py ──► firmware/main/generated/
                                                   (modelo, operadores, quantização, teste de ouro)

Nó (ESP32-S3) câmera ─► recorte de cada vaso ─► CNN ─► espécie confirmada ─► perfil da espécie
              sensores de solo ──────────────────────────────────────────────► decisão ─► bomba
              ambiente (temperatura, umidade do ar, luz) ──► telemetria MQTT ◄── estado dos vasos e foto

Painel (PC)   broker MQTT ─► app.py (SQLite) ─► navegador: foto, vasos, histórico, regas
                                           └─► exportar_dataset.py ─► data/especies/ ─► train.py
```

## Conteúdo do repositório

| Pasta | O que tem |
|---|---|
| `tcc/` | documento do TCC (introdução e fundamentação). Com o Git, não precisa de V2, V3 no nome: o histórico guarda as versões |
| `docs/` | planejamento do grupo, hardware e contrato do modelo |
| `training/` | pipeline de treino, conversão int8 e comparação |
| `firmware/` | firmware do nó ESP32-S3 e testes no PC |
| `models/` | modelo e relatórios (hoje, do teste com dataset sintético) |

A cada push, o GitHub Actions roda os três conjuntos de testes (`.github/workflows/testes.yml`).

## O que já foi verificado

| Verificação | Resultado |
|---|---|
| Testes do pipeline de treino (`pytest`) | 17 passando |
| Pipeline completo em dataset sintético, com pesos ImageNet | treino → int8 → comparação OK |
| LiteRT (kernels de referência) × TFLM | 0 LSB de diferença |
| Testes da lógica do firmware no PC (`run.sh`) | 54 verificações, 0 falhas |
| Testes do pipeline de treino, incluindo a separação por sessão | 23 passando |
| Testes do painel (`pytest` em `painel/`): armazenamento, API, rotulagem e exportação | 18 passando |
| Rotulagem usada num navegador real com as 71 fotos: área desenhada, salva e exportada | ok |
| Painel aberto num navegador real, em tela de computador e de celular, com dados simulados | sem erros no console |
| Sono profundo e MQTT (QoS, retenção, testamento): funções conferidas no ESP-IDF 5.5.5 e no esp-mqtt; firmware compilado com e sem sono profundo, em C++17 e C++20 | 0 avisos |
| Recorte + redimensionamento do firmware × `tf.image.resize` do treino | diferença 0 em 5 recortes |
| Todos os arquivos do firmware compilados com `-Wall -Wextra -Werror` (cabeçalhos reais do TFLM; assinaturas do ESP-IDF e dos drivers conferidas no código-fonte de cada um) | 0 avisos |
| Teste de ouro executado no PC (versão anterior do firmware, mesma lógica) | PASSOU, 0 LSB |

**Ainda não verificado:** o build com `idf.py`, a execução na placa e os sensores, a
câmera e a bomba de verdade. Isso acontece no passo 3.

## Estrutura

```
training/                     pipeline de treino (Python) e testes
firmware/main/
  main.cc                     laço do nó: estado na memória RTC, sono profundo entre ciclos
  app_config.h                pinos, regiões dos vasos, calibração dos sensores
  Kconfig.projbuild           Wi-Fi, broker, sono profundo e intervalos (idf.py menuconfig)
  logic/                      lógica pura, testada no PC
    irrigation.*              histerese, tempo máximo, intervalo mínimo, travas de segurança
    cycle.*                   quando rodar a câmera, quando dormir e o QoS de cada mensagem
    species.*                 confirmação da espécie (2 leituras seguidas)
    species_profiles.cc       p de cada espécie (FAO 56) — Leonardo mantém
    preprocess.*              RGB565 → recorte → 96×96 → int8, igual ao treino
  hw/                         camada de hardware (ESP-IDF)
    classifier.*  camera.*  sensors.*  actuators.*  telemetry.*
  generated/                  saída do convert.py e do compare.py (não edite)
firmware/test/host/           testes da lógica e paridade com o TensorFlow
painel/                       painel de acompanhamento, rotulagem das fotos, simulador e exportadores
docs/contrato-modelo.md       acordo entre treino, firmware e dataset
```

Os arquivos de `models/` e `firmware/main/generated/` vêm do teste com dataset
sintético (classes "suculenta", "folha larga" e "flor vermelha"). Servem para compilar e
testar o firmware antes de treinar; o primeiro `convert.py` + `compare.py` substitui tudo.
Treinem com as pastas `alface`, `cebolinha`, `rucula` e `vazio`, os mesmos rótulos de
`species_profiles.cc`.

## 1. Ambiente de treino

O pacote `tflite-micro` só existe para Linux x86-64. **No Windows, use o WSL2 (Ubuntu).**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r training/requirements.txt
cd training && python -m pytest        # 17 passed
```

## 2. Treinar, converter e comparar

```bash
cd training
python train.py                          # tf_flowers como placeholder
python train.py --data-dir ../data/especies --teste-ultima-sessao --ajuste-fino 5   # dataset do grupo
python convert.py
python compare.py
```

`models/compare_report.md` e `models/confusion_matrix_tflm.png` vão direto para o cap. 3.

Com `--teste-ultima-sessao`, a sessão de fotos mais recente fica inteira fora do treino e vira o
teste do cap. 3; `models/divisao.json` registra qual foi. Sem a opção, a divisão é aleatória e
pode pôr fotos quase iguais da mesma sessão no treino e na validação, inflando a acurácia.
`--ajuste-fino` libera as últimas camadas da MobileNetV2 por mais algumas épocas.

## 3. Firmware no ESP32-S3

ESP-IDF **5.5.x** (mínimo 5.1). No Windows pode ser nativo, pelo instalador ou pela
extensão do VS Code.

```bash
cd firmware
idf.py set-target esp32s3
idf.py menuconfig        # AgroSense: rede, broker, sono profundo e intervalos
idf.py build
idf.py -p PORTA flash monitor
```

As dependências são baixadas sozinhas na primeira compilação. Sem SSID configurado, o
nó roda em modo offline. Placa N8R8? Troque o tamanho de flash em `sdkconfig.defaults`.

No boot, o log mostra o teste de ouro, o estado de cada sensor e, a cada rodada, o que
a câmera viu em cada vaso e a decisão tomada:

```
I (agrosense) Partida a frio | ciclo 1
I (classificador) TESTE DE OURO: PASSOU (maior diferença 0 LSB)
I (sensores) ADS1115 ok | BH1750 ok | BME280 ok
I (agrosense) Vaso 0: viu 'suculenta' (91%, 50 ms) | espécie confirmada: suculenta
I (agrosense) Vaso 0: solo 12% (2.55 V) | bomba LIGADA | ligou_solo_seco
I (agrosense) Vaso 0: solo 30% (2.32 V) | bomba desligada | parou_solo_umido
I (agrosense) Dormindo por 600 s
```

## Modos de operação

**Sono profundo (padrão).** O nó acorda pelo temporizador a cada `AGROSENSE_SLEEP_SECONDS`
(600 s), lê os sensores, roda a câmera só quando precisa (espécie ainda não confirmada ou
reverificação vencida, a cada `AGROSENSE_VISION_SECONDS`), decide a irrigação, publica o estado
se houver rede e volta a dormir. Detalhes:

- **Nunca dorme regando:** com uma bomba ligada, o controlador fica acordado até o limiar de
  parada ou o tempo máximo.
- **Estado preservado:** espécie confirmada e horário da última rega ficam na memória RTC, que
  sobrevive ao sono; o teste de ouro roda só na partida a frio.
- **Relés travados:** antes de dormir, as bombas são desligadas e os pinos travados nesse estado.
- **Sem rede, sem bloqueio:** o nó espera a conexão por até 8 s; se não vier, dorme assim mesmo e
  o estado sai no ciclo seguinte.
- **Log some durante o sono:** a USB cai junto com o chip. Para acompanhar na bancada, use o modo
  contínuo.

**Contínuo (bancada e banca).** Em `idf.py menuconfig` → AgroSense, desmarque o sono profundo:
o nó fica acordado, confere o solo a cada 5 s (1 s regando) e manda o relatório completo a cada
minuto.

## 4. Ajustes no primeiro teste com a placa

Tudo em `firmware/main/app_config.h`:

1. **Pinos da câmera:** o padrão é o do ESP32-S3-EYE, que a Freenove ESP32-S3 WROOM CAM
   também usa. Outra placa: confira o pinout dela.
2. **Calibração do sensor:** para cada sensor, anote a tensão do log com o sensor no ar
   (`kSoilDryVolts`) e mergulhado em água até a marca (`kSoilWetVolts`).
3. **Calibração do vaso:** com o sensor já no vaso, anote a umidade do log de 1 a 2 h depois
   de uma rega completa, quando a água para de escorrer (`kSoilFieldCapacityPct`), e use a
   referência do substrato para o ponto de murcha (`kSoilWiltingPct`). Os limiares saem daí.
4. **Regiões dos vasos (`kPotRois`):** quadrados no quadro de 320×240 que cobrem cada
   vaso. Fixem câmera e vasos na bancada antes de ajustar.
5. **Relés:** se a bomba ligar quando devia desligar, troque `kRelayActiveLow`.
6. **Boia:** `kTankSwitchGpio = -1` desativa a trava do reservatório.
7. **Cores trocadas na câmera:** inverta `kRgb565BigEndian`.
8. **Espécie fixa (`kFixedSpecies`):** vem preenchida com alface, cebolinha e rúcula, para o nó regar
   durante a germinação, quando o broto ainda não é reconhecível. Troquem por `nullptr` quando o
   modelo treinado com as fotos de vocês estiver gravado; daí em diante a câmera decide.

## 5. Perfis das espécies (Leonardo)

`firmware/main/logic/species_profiles.cc` guarda, para cada espécie, o fator de depleção p da
Tabela 22 da FAO 56 (alface 0,30 e cebolinha 0,30, pela cebola verde; a rúcula não consta da tabela
e usa 0,30 por premissa, o mesmo valor da alface e do rabanete), o tempo máximo de bomba e o
intervalo mínimo entre regas. Os limiares de cada vaso são calculados no nó:

- desliga ao chegar na capacidade de campo (θ_CC);
- liga abaixo de θ_CC − p × (θ_CC − θ_PMP).

Com θ_CC = 70% e θ_PMP = 20%, as três ligam abaixo de 55%. Uma espécie com outro p, como o feijão
(0,45, ligaria abaixo de 48%), entra só com uma linha nova na tabela.
O rótulo precisa ser idêntico ao nome da pasta do dataset. A classe "vazio" não é regada, e
espécie sem perfil também não.

## 6. Telemetria

| Tópico | Conteúdo | QoS e retenção |
|---|---|---|
| `agrosense/vaso/0` … `/2` | espécie confirmada, umidade do solo, bomba e motivo da decisão | QoS 1 com retenção quando a bomba muda; QoS 0 nas leituras periódicas |
| `agrosense/ambiente` | temperatura, umidade do ar, luz, reservatório | QoS 0 |
| `agrosense/no/status` | `online`, `dormindo` ou `offline` (testamento, se o nó cair sem avisar) | QoS 1 com retenção |
| `agrosense/camera` | foto da bancada em JPEG, a cada classificação | QoS 0 com retenção |
| `agrosense/camera/info` | região de cada vaso na foto e o que a câmera viu nela | QoS 0 com retenção |

As mensagens de vaso também levam a espécie, se ela é fixa, a confiança da câmera e os
limiares em uso.

## Rotulagem das fotos

As fotos de celular ficam em `data/originais/<lote>/`, uma pasta por lote, com um `manifesto.json`
que registra nome, tamanho e SHA-256 de cada foto. Para rotular:

1. `cd painel` e `python app.py`; abra `http://localhost:8000/rotular.html`.
2. Escolha a espécie (teclas 1 a 4) e arraste sobre a foto para marcar cada área de plantio num
   quadrado. Se a foto não tiver planta aproveitável, use "Sem planta útil". As áreas ficam em
   `data/originais/<lote>/rotulos.json`, versionado junto com as fotos.
3. "Exportar recortes" gera `data/especies/<espécie>/<sessão>__<lote>__<foto>__r<n>.jpg`, pronto
   para o `train.py`. Exportar de novo refaz os recortes, então mudar um rótulo nunca deixa recorte velho.

A sessão é a data da foto, lida do nome do arquivo (como em `IMG-20261105-WA0020.jpg`), ou o nome
do lote quando o arquivo não traz data. Para um lote novo, copie as fotos para uma pasta nova em
`data/originais/` e gere o manifesto: `python criar_manifesto.py ../data/originais/<lote>`.

## Painel de acompanhamento

O painel roda num computador da mesma rede do nó e mostra a foto da bancada com a espécie
reconhecida em cada vaso, a umidade de cada vaso com a faixa entre os limiares, o
histórico de 24 horas ou 7 dias, o ambiente e as regas recentes. Ele funciona sem internet.

1. **Broker:** instale o Mosquitto e rode-o com a configuração do repositório. Sem ela, o Mosquitto
   só aceita conexões da própria máquina e o ESP32 não consegue publicar.
   ```bash
   mosquitto -c painel/mosquitto.conf -v
   ```
2. **Nó:** em `idf.py menuconfig` → AgroSense, aponte o broker para `mqtt://IP-DO-COMPUTADOR`.
3. **Painel:**
   ```bash
   pip install -r painel/requirements.txt
   cd painel
   python app.py          # http://localhost:8000, ou http://IP-DO-COMPUTADOR:8000 no celular
   ```

Os dados ficam em `painel/agrosense.db` (SQLite), fora do Git.

**Sem o protótipo:** `python simular.py --direto` grava 48 horas simuladas no banco, e o
`app.py` mostra tudo. Com o broker rodando, `python simular.py` publica ao vivo, como o nó faria.

**Dataset a partir da câmera do nó:** com a espécie fixa ligada, cada foto já sai rotulada.
`python exportar_dataset.py` recorta a região de cada vaso e grava em
`data/especies/<espécie>/`, pronto para o `train.py`. Por padrão, ele só usa vasos com espécie
fixa: a espécie que a câmera confirmou sozinha não pode servir de rótulo para treinar a própria
câmera.

## 7. Testes

```bash
firmware/test/host/run.sh                              # lógica do firmware (g++)
cd firmware/test/host && python test_resize_parity.py  # firmware × tf.image.resize
cd training && python -m pytest                        # pipeline de treino
cd painel && python -m pytest                          # painel e exportação do dataset
```

Rodem os quatro antes de cada entrega: mudar o pré-processamento de um lado sem o outro é
o jeito mais comum de derrubar a acurácia na placa.

## 8. Experimento para o cap. 3: com e sem ESP-NN

`idf.py menuconfig` → ESP-NN → *ANSI C*, compile de novo e compare a latência do log
com a versão otimizada.

## Bibliotecas usadas pelo firmware

| Biblioteca | Para quê |
|---|---|
| `espressif/esp-tflite-micro` | inferência da CNN (TFLM + ESP-NN) |
| `espressif/esp32-camera` | captura da câmera |
| `esp-idf-lib/ads111x`, `bh1750`, `bmp280`, `i2cdev` | ADS1115, luminosidade, BME280 e barramento I2C |
| ESP-IDF (Wi-Fi, MQTT, NVS, GPIO) | rede, telemetria e acionamento |

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `UnsupportedOpError` no `convert.py` | operador sem mapeamento; adicione em `OP_TO_METHOD` (`codegen.py`) |
| `AllocateTensors falhou` | arena pequena; aumente `ARENA_MARGIN` em `config.py` e rode `compare.py` |
| `Sem memória para a arena` | PSRAM desabilitada ou placa sem PSRAM octal |
| Sensor com `FALHOU` no boot | pinos I2C (`kI2cSda`/`kI2cScl`) ou endereço; BME280 pode estar em 0x77 |
| Umidade do ar sempre 0 | o módulo é BMP280, não BME280 |
| Espécie nunca confirmada | região do vaso errada ou `kMinConfidence` alto demais |
| Cliente MQTT ausente no ESP-IDF 6 | adicione `espressif/mqtt` ao `idf_component.yml` |
| LiteRT e TFLM diferem ~20 LSB | LiteRT usando XNNPACK; o `compare.py` já força kernels de referência |
| Log some no monitor serial | sono profundo: a USB cai junto com o chip; use o modo contínuo na bancada |
| Nó não volta a dormir | alguma bomba está ligada; ele dorme ao atingir o limiar de parada ou o tempo máximo |
