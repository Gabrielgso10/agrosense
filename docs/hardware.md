# Hardware do protótipo

## Lista de compras

Preços estimados em setembro de 2026; confiram no carrinho. Total aproximado:
R$ 600 a 1.000, menos o que o grupo já tiver.

| Item | Qtd | O que conferir no anúncio | R$ (estim.) |
|---|---|---|---|
| Placa ESP32-S3 N16R8 com câmera OV2640 ou OV3660 | 2 | "S3" no nome; slot microSD; de preferência formato dev board | 110–150 cada |
| Cartão microSD 32 GB | 2 | classe 10 | 25–40 cada |
| Sensor de umidade do solo capacitivo v1.2 | 5 (3 + 2 reserva) | CI TLC555 e regulador na placa | 10–20 cada |
| ADS1115 (ADC I2C de 4 canais) | 1 | — | 25–45 |
| BME280 (ou AHT20) | 1 | BME280 de fato, não BMP280 | 25–60 |
| BH1750 (luminosidade) | 1 | — | 15–25 |
| Mini bomba submersa 3–6 V | 4 (3 + 1) | saída do diâmetro da mangueira | 12–20 cada |
| Módulo relé 4 canais optoacoplado | 1 | aciona com sinal de 3,3 V | 25–40 |
| Boia de nível (chave) | 1 | contato seco | 10–20 |
| Diodos 1N4007, capacitores 1000 µF e resistores | — | — | ~5 |
| Fonte 5 V 3 A + adaptador P4 com borne | 1 | 3 A reais | 30–50 |
| Mangueira de silicone, reservatório 3–5 L, 3 vasos com furo e prato | — | — | 40–80 |
| Bancada: protoboards, jumpers, cabos USB-C de dados, barra de pinos, bornes, termorretrátil | — | pular o que já tiverem | 60–100 |

Comprem em loja nacional: o prazo do AliExpress não cabe no cronograma.

## Ligações (as mesmas de `firmware/main/app_config.h`)

| Função | Ligação |
|---|---|
| Câmera | pinout do ESP32-S3-EYE, também usado pela Freenove ESP32-S3 WROOM CAM |
| I2C (ADS1115, BME280, BH1750) | SDA no GPIO 1, SCL no GPIO 2 |
| Sensores de solo dos vasos 0, 1 e 2 | canais A0, A1 e A2 do ADS1115 |
| Relés das bombas dos vasos 0, 1 e 2 | GPIO 14, 21 e 47 |
| Boia do reservatório | GPIO 42 (pull-up interno) |

## Teste de recebimento (primeiras 48 h)

Compra online tem 7 dias de arrependimento pelo Código de Defesa do Consumidor.

1. **Placas:** gravar o exemplo CameraWebServer e conferir câmera, 8 MB de PSRAM e 16 MB de flash.
2. **Sensores de umidade:** CI TLC555; anotar a leitura no ar e na água; com o multímetro,
   saída abaixo de 3,3 V alimentando em 5 V.
3. **I2C:** BME280 responde ID 0x60 (o BMP280, vendido trocado, responde 0x58); BH1750 em 0x23;
   ADS1115 em 0x48.
4. **Bombas:** se o ESP32 reiniciar na partida do motor, diodo em paralelo com a bomba,
   capacitor junto ao relé e bomba numa derivação separada da fonte.
5. **Registro:** anotar tudo com fotos; vira a tabela de materiais do cap. 3.
