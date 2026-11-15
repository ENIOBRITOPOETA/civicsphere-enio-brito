"""Proteção de dados pessoais (LGPD) aplicada no ponto de gravação.

Regra central: religião, opinião política e filiação sindical/partidária são dados
sensíveis. O sistema não constrói perfil de PESSOAS por essas características.
Uma organização religiosa ou sindical existe como organização; a pessoa que a
representa é registrada apenas pela função institucional.

Atenção: a checagem de texto livre é heurística e NÃO substitui revisão humana.
"""
import re


class PrivacyError(ValueError):
    """Gravação recusada por violar a política de proteção de dados."""


CAMPOS_PROIBIDOS = {
    "religiao", "crenca", "fe", "opiniao_politica", "partido", "filiacao_partidaria",
    "filiacao_sindical", "orientacao_sexual", "etnia", "raca", "saude", "condicao_saude",
    "biometria", "genetico", "cpf", "rg", "data_nascimento", "endereco_residencial",
}

_PADROES = [
    r"\bfiliad[oa]\s+(a|ao|à)\b",
    r"\bvot(a|ou|ará|ara)\s+(em|no|na)\b",
    r"\b(é|e|sendo)\s+(cat[óo]lic|evang[ée]lic|esp[íi]rita|umbandist|candomblecist|ateu|petista|bolsonarista)",
    r"\b(simpatizante|militante)\b",
    r"opini[ãa]o\s+pol[íi]tica",
    r"orienta[çc][ãa]o\s+sexual",
    r"\breligi[ãa]o\s+d[oae]\b",
    r"\b(posi[çc][ãa]o|ideologia)\s+pol[íi]tic",
]
_REGEX = [re.compile(p, re.IGNORECASE) for p in _PADROES]


def verificar_campos(dados: dict) -> None:
    """Recusa chaves que representam dados sensíveis ou identificadores desnecessários."""
    for chave in dados:
        if chave.lower() in CAMPOS_PROIBIDOS:
            raise PrivacyError(
                f"O campo '{chave}' não pode ser registrado: dado pessoal sensível "
                "ou desnecessário para a finalidade (coleta mínima)."
            )


def verificar_texto(texto, campo: str) -> None:
    """Recusa texto livre que descreva crença, posição política ou filiação de uma pessoa."""
    if not texto:
        return
    for rx in _REGEX:
        if rx.search(str(texto)):
            raise PrivacyError(
                f"O campo '{campo}' parece descrever religião, posição política ou "
                "filiação de uma pessoa. Registre apenas a função institucional "
                "ou pública, ou descreva a organização, não a pessoa."
            )


def verificar_pessoa(dados: dict, campos_texto: list) -> None:
    verificar_campos(dados)
    for campo in campos_texto:
        verificar_texto(dados.get(campo), campo)
