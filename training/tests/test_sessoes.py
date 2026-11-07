from pathlib import Path

import pytest

from sessoes import dividir_por_sessao, sessao_do_arquivo


def arquivos(*nomes):
    return [Path("data/especies/alface") / n for n in nomes]


def test_sessao_e_o_prefixo_antes_dos_dois_sublinhados():
    assert sessao_do_arquivo(Path("x/2026-11-05__2026-11-06__IMG-1__r0.jpg")) == "2026-11-05"
    assert sessao_do_arquivo(Path("x/2026-11-20__no__143000_vaso1.jpg")) == "2026-11-20"
    assert sessao_do_arquivo(Path("x/foto_solta.jpg")) is None


def test_ultima_sessao_vai_inteira_para_o_teste():
    a = arquivos("2026-11-05__l__a__r0.jpg", "2026-11-05__l__a__r1.jpg", "2026-11-12__l__b__r0.jpg",
                 "2026-11-19__l__c__r0.jpg")
    treino, teste, sessoes = dividir_por_sessao(a, "ultima")
    assert sessoes == ["2026-11-19"]
    assert [p.name for p in teste] == ["2026-11-19__l__c__r0.jpg"] and len(treino) == 3


def test_sessoes_escolhidas_para_teste():
    a = arquivos("2026-11-05__l__a__r0.jpg", "2026-11-12__l__b__r0.jpg", "2026-11-19__l__c__r0.jpg")
    treino, teste, _ = dividir_por_sessao(a, ["2026-11-05", "2026-11-19"])
    assert sorted(p.name[:10] for p in teste) == ["2026-11-05", "2026-11-19"] and len(treino) == 1


def test_arquivo_sem_sessao_fica_no_treino():
    treino, _, _ = dividir_por_sessao(arquivos("solta.jpg", "2026-11-05__l__a__r0.jpg", "2026-11-12__l__b__r0.jpg"), "ultima")
    assert "solta.jpg" in [p.name for p in treino]


def test_uma_sessao_so_nao_permite_teste_independente():
    with pytest.raises(ValueError, match="sessão"):
        dividir_por_sessao(arquivos("2026-11-05__l__a__r0.jpg", "2026-11-05__l__b__r0.jpg"), "ultima")


def test_sessao_pedida_que_nao_existe_e_erro():
    with pytest.raises(ValueError, match="2026-12-01"):
        dividir_por_sessao(arquivos("2026-11-05__l__a__r0.jpg", "2026-11-12__l__b__r0.jpg"), ["2026-12-01"])
