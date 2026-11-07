"""Separação entre treino e teste por sessão de fotos.

Fotos da mesma sessão (mesmo dia, mesmas plantas) são quase iguais: se caírem dos dois
lados, a acurácia de teste sobe sem o modelo ter aprendido a generalizar. Por isso a
sessão vai no começo do nome de cada recorte (AAAA-MM-DD__...) e uma sessão inteira
fica de um lado só.
"""
from pathlib import Path

SEPARADOR = "__"


def sessao_do_arquivo(caminho: Path) -> str | None:
    nome = Path(caminho).name
    return nome.split(SEPARADOR)[0] if SEPARADOR in nome else None


def dividir_por_sessao(caminhos, teste):
    """teste = "ultima" ou lista de sessões. Retorna (treino, teste, sessões de teste).
    Arquivos sem sessão no nome ficam sempre no treino."""
    caminhos = [Path(c) for c in caminhos]
    sessoes = sorted({s for s in map(sessao_do_arquivo, caminhos) if s})
    if teste == "ultima":
        if len(sessoes) < 2:
            raise ValueError(f"Só há {len(sessoes)} sessão de fotos ({', '.join(sessoes) or 'nenhuma'}): "
                             "fotografem em outro dia para ter um teste independente.")
        escolhidas = [sessoes[-1]]
    else:
        escolhidas = sorted(teste)
        faltando = [s for s in escolhidas if s not in sessoes]
        if faltando:
            raise ValueError(f"Sessão sem fotos: {', '.join(faltando)}. Disponíveis: {', '.join(sessoes)}")
        if len(escolhidas) == len(sessoes):
            raise ValueError("Todas as sessões ficariam no teste: sobre pelo menos uma para o treino.")
    treino = [c for c in caminhos if sessao_do_arquivo(c) not in escolhidas]
    teste_ = [c for c in caminhos if sessao_do_arquivo(c) in escolhidas]
    return treino, teste_, escolhidas
