"""Importação dos 246 municípios de Goiás a partir da API pública de localidades do IBGE.

Roda no servidor AWS (precisa de acesso HTTPS de saída). Só marca a base como
'verificado' se vierem exatamente 246 municípios.
"""
import json
import urllib.request

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/52/municipios"
FONTE = "IBGE — API de Localidades (estados/52/municipios)"


def baixar_municipios(timeout=30):
    req = urllib.request.Request(URL, headers={"User-Agent": "CivicSphere/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return sorted(((str(m["id"]), m["nome"]) for m in dados), key=lambda x: x[1])


def importar(repo):
    municipios = baixar_municipios()
    qtd, completo = repo.importar_municipios(municipios, FONTE)
    return qtd, completo
