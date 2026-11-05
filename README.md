# AgroSense — ponto de partida do nó de borda

O nó fotografa os vasos, identifica a espécie de cada um com uma CNN rodando no
ESP32-S3 (TinyML) e decide a irrigação localmente, com os limiares daquela espécie.
A nuvem só recebe telemetria por MQTT; sem rede, tudo continua funcionando.

```
Treino (PC)   train.py ──► convert.py ──► compare.py ──► firmware/main/generated/
                                                   (modelo, operadores, quantização, teste de ouro)

Nó (ESP32-S3) câmera ─► recorte de cada vaso ─► CNN ─► espécie confirmada ─► perfil da espécie
              sensores de solo ──────────────────────────────────────────────► decisão ─► bomba
              ambiente (temperatura, umidade do ar, luz) ──► telemetria MQTT ◄── estado dos vasos
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
| Testes da lógica do firmware no PC (`run.sh`) | 34 verificações, 0 falhas |
| Recorte + redimensionamento do firmware × `tf.image.resize` do treino | diferença 0 em 5 recortes |
| Todos os arquivos do firmware compilados com `-Wall -Wextra -Werror` (cabeçalhos reais do TFLM; assinaturas do ESP-IDF e dos drivers conferidas no código-fonte de cada um) | 0 avisos |
| Teste de ouro executado no PC (versão anterior do firmware, mesma lógica) | PASSOU, 0 LSB |

**Ainda não verificado:** o build com `idf.py`, a execução na placa e os sensores, a
câmera e a bomba de verdade. Isso acontece no passo 3.

## Estrutura

```
training/                     pipeline de treino (Python) e testes
firmware/main/
  main.cc                     laço do nó: visão a cada N s, solo a cada 5 s (1 s regando)
  app_config.h                pinos, regiões dos vasos, calibração dos sensores
  Kconfig.projbuild           Wi-Fi, broker MQTT e intervalo (idf.py menuconfig)
  logic/                      lógica pura, testada no PC
    irrigation.*              histerese, tempo máximo, intervalo mínimo, travas de segurança
    species.*                 confirmação da espécie (2 leituras seguidas)
    species_profiles.cc       tabela de perfis por espécie — Leonardo preenche
    preprocess.*              RGB565 → recorte → 96×96 → int8, igual ao treino
  hw/                         camada de hardware (ESP-IDF)
    classifier.*  camera.*  sensors.*  actuators.*  telemetry.*
  generated/                  saída do convert.py e do compare.py (não edite)
firmware/test/host/           testes da lógica e paridade com o TensorFlow
docs/contrato-modelo.md       acordo entre treino, firmware e dataset
```

Os arquivos de `models/` e `firmware/main/generated/` vêm do teste com dataset
sintético (classes "suculenta", "folha larga" e "flor vermelha"). Servem para compilar e
testar o firmware antes de treinar; o primeiro `convert.py` + `compare.py` substitui tudo.
Lembrem de atualizar `species_profiles.cc` com os rótulos novos.

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
python train.py --data-dir ../data/especies --epochs 10   # dataset do grupo
python convert.py
python compare.py
```

`models/compare_report.md` e `models/confusion_matrix_tflm.png` vão direto para o cap. 3.

## 3. Firmware no ESP32-S3

ESP-IDF **5.5.x** (mínimo 5.1). No Windows pode ser nativo, pelo instalador ou pela
extensão do VS Code.

```bash
cd firmware
idf.py set-target esp32s3
idf.py menuconfig        # AgroSense: rede Wi-Fi, broker MQTT, intervalo da câmera
idf.py build
idf.py -p PORTA flash monitor
```

As dependências são baixadas sozinhas na primeira compilação. Sem SSID configurado, o
nó roda em modo offline. Placa N8R8? Troque o tamanho de flash em `sdkconfig.defaults`.

No boot, o log mostra o teste de ouro, o estado de cada sensor e, a cada rodada, o que
a câmera viu em cada vaso e a decisão tomada:

```
I (classificador) TESTE DE OURO: PASSOU (maior diferença 0 LSB)
I (sensores) ADS1115 ok | BH1750 ok | BME280 ok
I (agrosense) Vaso 0: viu 'suculenta' (91%, 50 ms) | espécie confirmada: suculenta
I (agrosense) Vaso 0: solo 12% (2.55 V) | bomba LIGADA | ligou_solo_seco
```

## 4. Ajustes no primeiro teste com a placa

Tudo em `firmware/main/app_config.h`:

1. **Pinos da câmera:** o padrão é o do ESP32-S3-EYE, que a Freenove ESP32-S3 WROOM CAM
   também usa. Outra placa: confira o pinout dela.
2. **Calibração do solo:** para cada sensor, anote a tensão do log com o sensor no ar
   (`kSoilDryVolts`) e mergulhado em água até a marca (`kSoilWetVolts`).
3. **Regiões dos vasos (`kPotRois`):** quadrados no quadro de 320×240 que cobrem cada
   vaso. Fixem câmera e vasos na bancada antes de ajustar.
4. **Relés:** se a bomba ligar quando devia desligar, troque `kRelayActiveLow`.
5. **Boia:** `kTankSwitchGpio = -1` desativa a trava do reservatório.
6. **Cores trocadas na câmera:** inverta `kRgb565BigEndian`.

## 5. Perfis das espécies (Leonardo)

`firmware/main/logic/species_profiles.cc` tem uma linha por espécie: liga abaixo de X%
de umidade, desliga ao chegar em Y%, tempo máximo de bomba e intervalo mínimo entre
regas. O rótulo precisa ser idêntico ao nome da pasta do dataset. A classe "vazio" fica
com `irrigate = false`. Espécie sem perfil nunca é regada.

## 6. Telemetria

| Tópico | Conteúdo |
|---|---|
| `agrosense/vaso/0` … `/2` | espécie confirmada, umidade do solo, bomba e motivo da decisão |
| `agrosense/ambiente` | temperatura, umidade do ar, luz, reservatório |

Mosquitto como broker e um painel no Node-RED bastam; não há código a escrever no servidor.

## 7. Testes

```bash
firmware/test/host/run.sh                              # lógica do firmware (g++)
cd firmware/test/host && python test_resize_parity.py  # firmware × tf.image.resize
cd training && python -m pytest                        # pipeline de treino
```

Rodem os três antes de cada entrega: mudar o pré-processamento de um lado sem o outro é
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
