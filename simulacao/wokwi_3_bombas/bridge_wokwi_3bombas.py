"""AgroSense: encaminha tres zonas do Wokwi (broker publico) ao painel MQTT local.

Exige 'paho-mqtt', instalado pelo projeto em painel/requirements.txt.
Nenhuma bomba REAL e acionada; recebe estados de LEDs/comandos simulados.
"""
import json
import math
import os
import time

BROKER_PUBLICO = 'broker.hivemq.com'
TOPICO_WOKWI = 'agrosense/demo/480050529566816257/telemetry/3zonas'
BROKER_LOCAL = os.environ.get('AGROSENSE_MQTT_HOST', 'localhost')
ESPECIES = ('alface', 'cebolinha', 'rucula')


def _inteiro_pct(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError('umidade do solo nao numerica')
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('umidade do solo fora de 0..100')
    return int(round(value))


def _num_ou_nulo(value):
    return float(value) if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) else None


def traduzir(payload, estados_anteriores=None):
    """Retorna (vasos, ambiente) no formato consumido por painel/store.py."""
    dados = json.loads(payload)
    if not isinstance(dados, dict) or not isinstance(dados.get('vasos'), list):
        raise ValueError('payload sem lista de vasos')
    if len(dados['vasos']) != 3:
        raise ValueError('o payload deve conter exatamente 3 vasos')
    anteriores = estados_anteriores if estados_anteriores is not None else [None, None, None]
    vistos, vasos = set(), []
    for item in dados['vasos']:
        if not isinstance(item, dict) or type(item.get('id')) is not int:
            raise ValueError('id do vaso invalido')
        i = item['id']
        if i not in (0, 1, 2) or i in vistos:
            raise ValueError('id do vaso duplicado ou fora de 0,1,2')
        vistos.add(i)
        if not isinstance(item.get('bomba'), bool):
            raise ValueError(f'estado de bomba invalido para vaso {i}')
        solo = _inteiro_pct(item.get('solo_pct'))
        bomba = item['bomba']
        anterior = anteriores[i]
        if anterior is None:
            motivo = 'estado_inicial_simulado'
        elif bomba and not anterior:
            motivo = 'ligou_solo_seco'
        elif not bomba and anterior:
            motivo = 'parou_solo_umido'
        else:
            motivo = 'ocioso'
        vasos.append({
            'vaso': i, 'especie': ESPECIES[i], 'fixa': True, 'confianca': None,
            'solo_pct': solo, 'liga_abaixo': 35, 'desliga_em': 55,
            'bomba': bomba, 'motivo': motivo, 'origem': 'Wokwi, simulacao',
        })
    vasos.sort(key=lambda v: v['vaso'])
    ambiente = {
        'temperatura_c': _num_ou_nulo(dados.get('temperatura_c')),
        'umidade_ar_pct': _num_ou_nulo(dados.get('umidade_ar_pct')),
        'lux': None,  # leitura disponivel e ADC bruto, nao lux calibrados
        'reservatorio_ok': True,  # valor demonstrativo, sem sensor de tanque
        'sensores_ok': _num_ou_nulo(dados.get('temperatura_c')) is not None,
        'luz_adc': dados.get('luz_adc'), 'origem': 'Wokwi, simulacao',
    }
    return vasos, ambiente


def main():
    import paho.mqtt.client as mqtt
    local = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='agrosense-3zonas-local')
    local.reconnect_delay_set(min_delay=1, max_delay=10)
    try:
        local.connect(BROKER_LOCAL, 1883, 60)
    except OSError as err:
        print(f'ERRO: Mosquitto local {BROKER_LOCAL}:1883 indisponivel: {err}')
        return
    local.loop_start()

    remoto = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'agrosense-3zonas-ponte-{os.getpid()}')
    remoto.reconnect_delay_set(min_delay=1, max_delay=15)
    estado = {'anteriores': [None]*3, 'ultima': None, 'offline': False}

    def on_connect(client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            print(f'MQTT publico recusou conexao: {reason_code}')
        else:
            client.subscribe(TOPICO_WOKWI, qos=0)
            print(f'MQTT publico conectado. Ouvindo {TOPICO_WOKWI}')

    def on_message(_client, _userdata, message):
        if not local.is_connected():
            print('Mosquitto local desconectado. Nada foi repassado.')
            return
        try:
            vasos, ambiente = traduzir(message.payload, estado['anteriores'])
        except (ValueError, TypeError, json.JSONDecodeError) as err:
            print(f'Pacote descartado: {err}')
            return
        estado['anteriores'] = [v['bomba'] for v in vasos]
        estado['ultima'] = time.monotonic()
        estado['offline'] = False
        for v in vasos:
            local.publish(f"agrosense/vaso/{v['vaso']}", json.dumps(v,ensure_ascii=False), qos=0, retain=False)
        local.publish('agrosense/ambiente', json.dumps(ambiente,ensure_ascii=False), qos=0, retain=False)
        local.publish('agrosense/no/status', 'online', qos=0, retain=False)
        print('WOKWI -> PAINEL | ' + ' | '.join(
            f"{v['especie']} {v['solo_pct']}% BOMBA {'ON' if v['bomba'] else 'OFF'}" for v in vasos
        ))

    remoto.on_connect = on_connect
    remoto.on_message = on_message
    try:
        print('Iniciando ponte de 3 zonas. Ctrl+C encerra.')
        remoto.connect(BROKER_PUBLICO, 1883, 60)
        remoto.loop_start()
        while True:
            time.sleep(1)
            ultima = estado['ultima']
            if ultima is not None and not estado['offline'] and time.monotonic()-ultima > 12:
                if local.is_connected():
                    local.publish('agrosense/no/status', 'offline', qos=0, retain=False)
                print('Sem leituras do Wokwi por mais de 12 segundos.')
                estado['offline'] = True
    except KeyboardInterrupt:
        print('Ponte finalizada.')
    except OSError as err:
        print(f'Falha de conexao: {err}')
    finally:
        remoto.loop_stop()
        remoto.disconnect()
        if local.is_connected():
            local.publish('agrosense/no/status','offline',qos=0)
            time.sleep(0.2)
        local.loop_stop()
        local.disconnect()


if __name__ == '__main__':
    main()
