"""CivicSphere v2 — interface Gradio (AWS). Execute com:  python app.py"""
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import gradio as gr

import agent
import config
import ibge
import taxonomy as T
from privacy import PrivacyError
from repository import Repo

repo = Repo(config.DB_PATH)
repo.inicializar()

# Base mínima da lista original (somente municípios), usada apenas se a base estiver vazia.
# É PROVISÓRIA e marcada como não verificada: use "Importar municípios do IBGE" para a base oficial.
_PROVISORIO = [
    "Goiânia", "Aparecida de Goiânia", "Anápolis", "Rio Verde", "Luziânia", "Trindade", "Formosa",
    "Valparaíso de Goiás", "Planaltina", "Águas Lindas de Goiás", "Novo Gama", "Santo Antônio do Descoberto",
    "Catalão", "Jataí", "Itumbiara", "Mineiros", "Caldas Novas", "Goianésia",
]
repo.semear_provisorio(_PROVISORIO, "Lista original do app.py (provisória, não verificada)")
USUARIO = config.APP_USER or "interface"


# ----------------------------------------------------------------------------- utilidades
def seguro(fn):
    def interno(*args):
        try:
            return fn(*args)
        except (PrivacyError, ValueError) as e:
            return f"⚠️ {e}"
        except sqlite3.IntegrityError as e:
            return f"⚠️ Registro inválido ou duplicado: {e}"
        except Exception as e:  # noqa: BLE001
            return f"⚠️ Erro inesperado: {e}"
    return interno


def _id(valor, nome="registro"):
    if valor in (None, ""):
        raise ValueError(f"Selecione {nome}.")
    return int(valor)


def _ids(valores):
    return [str(v) for v in (valores or [])]


def _opts(pares):
    return [(rotulo, str(v)) for rotulo, v in pares]


def _enum_opts(mapa_ou_lista):
    if isinstance(mapa_ou_lista, dict):
        return [(v, k) for k, v in mapa_ou_lista.items()]
    return [(x.replace("_", " "), x) for x in mapa_ou_lista]


ORIGENS_OPTS = [(v.title(), k) for k, v in T.ORIGENS.items() if k != "inferencia_agente"]
VALID_OPTS = _enum_opts(T.VALIDACAO)


def _cat_nome():
    return {c["id"]: c["nome"] for c in repo.listar("categorias", limite=1000)}


def _org_nome():
    return {o["id"]: o["nome"] for o in repo.listar("organizacoes", limite=5000)}


def _rows(tabela, cols, ordem="id DESC", mapas=None):
    mapas = mapas or {}
    out = []
    for r in repo.listar(tabela, ordem=ordem, limite=1000):
        out.append([mapas[c](r[c]) if c in mapas else r.get(c) for c in cols])
    return out


# ----------------------------------------------------------------------------- getters de opções
def g_terr():
    return _opts([(l, v) for l, v in repo.territorios_opcoes()])


def g_terr_oficial():
    return _opts([(l, v) for l, v in repo.territorios_opcoes() if v.startswith("oficial:")])


def g_cat(tipo):
    return lambda: _opts(repo.opcoes_categoria(tipo))


def g_org():
    return _opts([(f"{o['nome']} (#{o['id']})", o["id"]) for o in repo.listar("organizacoes", ordem="nome", limite=5000)])


def g_int():
    return _opts([(f"{p['nome']} (#{p['id']})", p["id"]) for p in repo.listar("interlocutores", ordem="nome", limite=5000)])


def g_dem():
    return _opts([(f"#{d['id']} {d['titulo']}", d["id"]) for d in repo.listar("demandas", limite=5000)])


def g_pot():
    return _opts([(f"#{p['id']} {p['titulo']}", p["id"]) for p in repo.listar("potencialidades", limite=5000)])


def g_proj():
    return _opts([(f"#{p['id']} {p['titulo']}", p["id"]) for p in repo.listar("projetos", limite=5000)])


# ----------------------------------------------------------------------------- getters de tabelas
def t_territorios():
    rows = []
    for r in repo.listar("territorios_oficiais", ordem="tipo, nome", limite=1000):
        rows.append(["oficial", r["tipo"], r["nome"], r["codigo_ibge"], r["uf"], r["validacao"], r["fonte"]])
    for r in repo.listar("territorios_comunitarios", ordem="nome", limite=1000):
        rows.append(["comunitário", r["tipo"], r["nome"], "", "", r["validacao"], r["fonte"]])
    return rows


def t_orgs():
    cn = _cat_nome()
    return _rows("organizacoes", ["id", "nome", "sigla", "categoria_id", "area_atuacao", "origem", "validacao"],
                 mapas={"categoria_id": lambda v: cn.get(v)})


def t_atuacoes():
    on, cn = _org_nome(), _cat_nome()
    return _rows("atuacoes", ["id", "organizacao_id", "categoria_id", "titulo", "situacao", "validacao"],
                 mapas={"organizacao_id": lambda v: on.get(v), "categoria_id": lambda v: cn.get(v)})


def t_interlocutores():
    return [[p["id"], p["nome"], p["base_legal"], "sim" if p["contato_autorizado"] else "não", p["finalidade"]]
            for p in repo.listar("interlocutores", ordem="nome", limite=1000)]


def t_demandas():
    cn = _cat_nome()
    return _rows("demandas", ["id", "titulo", "categoria_id", "escala", "situacao", "prioridade_nivel",
                              "prioridade_decidida_por", "origem", "validacao"],
                 mapas={"categoria_id": lambda v: cn.get(v)})


def t_pot():
    cn = _cat_nome()
    return _rows("potencialidades", ["id", "titulo", "categoria_id", "origem", "validacao"],
                 mapas={"categoria_id": lambda v: cn.get(v)})


def t_proj():
    return _rows("projetos", ["id", "titulo", "situacao", "proposto_por", "validacao"])


def t_partic():
    return _rows("participacoes", ["id", "tipo", "titulo", "data", "numero_participantes", "decisoes"])


def t_encam():
    return _rows("encaminhamentos", ["id", "demanda_id", "projeto_id", "instituicao", "situacao", "resposta"])


def t_audit():
    return _rows("auditoria", ["id", "ts", "usuario", "acao", "tabela", "registro_id"])[:300]


def status_sistema():
    cont = {t: repo.contar(t) for t in ("territorios_oficiais", "territorios_comunitarios", "organizacoes",
                                        "atuacoes", "interlocutores", "demandas", "potencialidades",
                                        "projetos", "missoes")}
    chave = "configurada" if config.NVIDIA_API_KEY else "**NÃO configurada**"
    linhas = [f"**Versão** {config.VERSAO} · **Modelo** `{config.NVIDIA_MODEL}` (não validado até rodar `check_model.py`)",
              f"**Chave NVIDIA** {chave} · **Banco** `{config.DB_PATH}`",
              "**Login** " + ("ativo" if config.APP_USER else "inativo (defina APP_USER e APP_PASSWORD)"), ""]
    linhas += [f"- {k.replace('_', ' ')}: {v}" for k, v in cont.items()]
    linhas += ["", "**Capacidades reais nesta versão:** consulta ao banco, diagnóstico e propostas pelo modelo, "
               "registro de missões. **Não existe** pesquisa na internet, envio de mensagens nem importação "
               "automática de fontes além dos municípios do IBGE."]
    return "\n".join(linhas)


# ----------------------------------------------------------------------------- ações
@seguro
def a_importar_ibge():
    qtd, completo = ibge.importar(repo)
    sufixo = "Base validada (246 municípios)." if completo else f"Atenção: vieram {qtd}, esperado 246; marcado 'em verificação'."
    return f"✅ {qtd} municípios importados do IBGE. {sufixo}"


@seguro
def a_terr_oficial(nome, tipo, pai, codigo, fonte, validacao):
    pai_id = None
    if pai:
        _, pai_id = repo.parse_territorio(pai)
    rid = repo.criar("territorios_oficiais", {"nome": nome, "tipo": tipo, "pai_id": pai_id, "codigo_ibge": codigo,
                                              "fonte": fonte, "data_fonte": date.today().isoformat(),
                                              "validacao": validacao or "nao_verificado"}, USUARIO)
    return f"✅ Território oficial #{rid} cadastrado."


@seguro
def a_terr_comunitario(nome, tipo, oficial, descricao, fonte, validacao):
    oid = repo.parse_territorio(oficial)[1] if oficial else None
    rid = repo.criar("territorios_comunitarios", {"nome": nome, "tipo": tipo, "oficial_id": oid, "descricao": descricao,
                                                  "fonte": fonte, "data_fonte": date.today().isoformat(),
                                                  "validacao": validacao or "nao_verificado"}, USUARIO)
    return f"✅ Território comunitário #{rid} cadastrado."


@seguro
def a_org(nome, sigla, cat, area, finalid, contato, fonte, origem, validacao, territorios):
    if not territorios:
        raise ValueError("Informe ao menos um território de abrangência.")
    rid = repo.criar("organizacoes", {"nome": nome, "sigla": sigla, "categoria_id": _id(cat, "a categoria"),
                                      "area_atuacao": area, "finalidades": finalid, "contato_publico": contato,
                                      "fonte": fonte, "data_fonte": date.today().isoformat(),
                                      "origem": origem or "nao_verificada", "validacao": validacao or "nao_verificado"},
                     USUARIO)
    for t in territorios:
        repo.definir_abrangencia("organizacao", rid, t, "abrangencia", USUARIO)
    return f"✅ Organização #{rid} cadastrada."


@seguro
def a_atuacao(org, tipo, titulo, descricao, situacao, fonte, origem):
    rid = repo.criar("atuacoes", {"organizacao_id": _id(org, "a organização"), "categoria_id": _id(tipo, "o tipo"),
                                  "titulo": titulo, "descricao": descricao, "situacao": situacao or "em_andamento",
                                  "fonte": fonte, "origem": origem or "nao_verificada"}, USUARIO)
    return f"✅ Atuação #{rid} registrada."


@seguro
def a_interlocutor(nome, base, finalid, contato, autorizado, pref, restr):
    rid = repo.criar_interlocutor(nome, base, finalid, contato, bool(autorizado), pref, restr, USUARIO)
    return f"✅ Interlocutor #{rid} registrado (coleta mínima; sem dados sensíveis)."


@seguro
def a_representacao(pessoa, org, funcao, fonte):
    rid = repo.criar_representacao(_id(pessoa, "a pessoa"), _id(org, "a organização"), funcao, fonte, USUARIO)
    return f"✅ Representação #{rid} registrada (função institucional)."


@seguro
def a_interacao(pessoa, canal, resumo):
    rid = repo.registrar_interacao(_id(pessoa, "a pessoa"), canal, resumo, usuario=USUARIO)
    return f"✅ Interação #{rid} registrada."


@seguro
def a_eliminar(pessoa):
    repo.eliminar_interlocutor(_id(pessoa, "a pessoa"), USUARIO)
    return "✅ Pessoa e registros dependentes eliminados (operação auditada, sem conteúdo)."


@seguro
def a_demanda(titulo, desc, cat, escala, org, fonte, origem, validacao, terr_origem, terr_afetados, data_ident, orgao):
    if not terr_origem:
        raise ValueError("Informe o território de origem da demanda.")
    rid = repo.criar("demandas", {"titulo": titulo, "descricao": desc, "categoria_id": _id(cat, "a categoria"),
                                  "escala": escala, "organizacao_id": int(org) if org else None, "fonte": fonte,
                                  "data_identificacao": data_ident or date.today().isoformat(),
                                  "orgao_relacionado": orgao, "origem": origem or "nao_verificada",
                                  "validacao": validacao or "nao_verificado"}, USUARIO)
    repo.definir_abrangencia("demanda", rid, terr_origem, "origem", USUARIO)
    for t in terr_afetados or []:
        repo.definir_abrangencia("demanda", rid, t, "afetado", USUARIO)
    return f"✅ Demanda #{rid} registrada."


@seguro
def a_prioridade(dem, nivel, criterios, quem):
    repo.decidir_prioridade(_id(dem, "a demanda"), nivel, criterios, quem, USUARIO)
    return "✅ Decisão de prioridade registrada com critérios e responsável."


@seguro
def a_situacao_demanda(dem, situacao):
    repo.atualizar("demandas", _id(dem, "a demanda"), {"situacao": situacao}, USUARIO)
    return "✅ Situação da demanda atualizada."


@seguro
def a_pot(titulo, desc, cat, local, possib, fonte, origem, validacao, territorios):
    if not territorios:
        raise ValueError("Informe ao menos um território.")
    rid = repo.criar("potencialidades", {"titulo": titulo, "descricao": desc, "categoria_id": _id(cat, "a categoria"),
                                         "localizacao": local, "possibilidades": possib, "fonte": fonte,
                                         "origem": origem or "nao_verificada",
                                         "validacao": validacao or "nao_verificado"}, USUARIO)
    for t in territorios:
        repo.definir_abrangencia("potencialidade", rid, t, "abrangencia", USUARIO)
    return f"✅ Potencialidade #{rid} registrada."


@seguro
def a_relacionar(dem, pot):
    repo.vincular("demanda", _id(dem, "a demanda"), "potencialidade", _id(pot, "a potencialidade"),
                  "resposta_possivel", USUARIO)
    return "✅ Demanda e potencialidade relacionadas."


@seguro
def a_projeto(titulo, obj, etapas, recursos, benef, resp, indic, situacao, dem, pot, orgs, territorios):
    rid = repo.criar("projetos", {"titulo": titulo, "objetivos": obj, "etapas": etapas, "recursos": recursos,
                                  "beneficiarios": benef, "responsaveis": resp, "indicadores": indic,
                                  "situacao": situacao or "proposta"}, USUARIO)
    if dem:
        repo.vincular("demanda", int(dem), "projeto", rid, "origem", USUARIO)
    if pot:
        repo.vincular("potencialidade", int(pot), "projeto", rid, "origem", USUARIO)
    for o in orgs or []:
        repo.vincular("organizacao", int(o), "projeto", rid, "participante", USUARIO)
    for t in territorios or []:
        repo.definir_abrangencia("projeto", rid, t, "abrangencia", USUARIO)
    return f"✅ Projeto #{rid} registrado."


@seguro
def a_evidencia(ent, ent_id, titulo, tipo, ref, data):
    rid = repo.anexar_evidencia(ent, _id(ent_id, "o ID"), titulo, tipo, ref, data, USUARIO)
    return f"✅ Evidência #{rid} anexada."


@seguro
def a_resultado(ent, ent_id, indicador, valor, desc):
    rid = repo.registrar_resultado(ent, _id(ent_id, "o ID"), indicador, valor, desc, date.today().isoformat(),
                                   usuario=USUARIO)
    return f"✅ Resultado #{rid} registrado."


@seguro
def a_encam(dem, proj, inst, desc, situacao, resposta):
    if not dem and not proj:
        raise ValueError("Informe uma demanda ou um projeto.")
    rid = repo.criar("encaminhamentos", {"demanda_id": int(dem) if dem else None,
                                         "projeto_id": int(proj) if proj else None, "instituicao": inst,
                                         "descricao": desc, "data": date.today().isoformat(),
                                         "situacao": situacao or "enviado", "resposta": resposta}, USUARIO)
    return f"✅ Encaminhamento #{rid} registrado."


@seguro
def a_partic(tipo, titulo, data, terr, desc, decisoes, n):
    ttipo = tid = None
    if terr:
        ttipo, tid = repo.parse_territorio(terr)
    rid = repo.criar("participacoes", {"tipo": tipo, "titulo": titulo, "data": data or date.today().isoformat(),
                                       "territorio_tipo": ttipo, "territorio_id": tid, "descricao": desc,
                                       "decisoes": decisoes, "numero_participantes": int(n) if n else None}, USUARIO)
    return f"✅ Participação #{rid} registrada (de forma agregada, sem lista de pessoas)."


def a_missao(terr, modo, categoria_alvo, objetivo):
    try:
        if not terr:
            return "⚠️ Selecione um território.", ""
        resp, lac, mid = agent.executar_missao(repo, terr, modo, categoria_alvo, objetivo, USUARIO)
        return resp + f"\n\n---\n*Missão #{mid} registrada.*", lac
    except (PrivacyError, ValueError) as e:
        return f"⚠️ {e}", ""
    except Exception as e:  # noqa: BLE001
        return f"⚠️ Erro inesperado: {e}", ""


@seguro
def a_exportar():
    dados = repo.exportar()
    caminho = Path(tempfile.gettempdir()) / f"civicsphere_export_{date.today().isoformat()}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return str(caminho)


@seguro
def a_restaurar(arquivo, substituir):
    if not arquivo:
        raise ValueError("Envie um arquivo de exportação.")
    caminho = arquivo if isinstance(arquivo, str) else arquivo.name
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    repo.restaurar(dados, substituir=bool(substituir))
    return "✅ Base restaurada."


# ----------------------------------------------------------------------------- interface
REFRESH = []   # (componente, função que devolve o update)
WIRES = []     # (botão, função, entradas, saída, muta)


def dd(label, getter=None, choices=None, multi=False, value=None):
    if getter is not None:
        c = gr.Dropdown(choices=getter(), label=label, multiselect=multi, allow_custom_value=True)
        REFRESH.append((c, lambda g=getter: gr.update(choices=g())))
    else:
        c = gr.Dropdown(choices=choices, label=label, multiselect=multi, value=value)
    return c


def tabela(headers, getter):
    c = gr.Dataframe(headers=headers, value=getter(), interactive=False, wrap=True)
    REFRESH.append((c, lambda g=getter: gr.update(value=g())))
    return c


def ligar(botao, fn, entradas, saida, muta=True):
    WIRES.append((botao, fn, entradas, saida, muta))


def refresh():
    return [fn() for _, fn in REFRESH]


with gr.Blocks(title="CivicSphere") as demo:
    gr.Markdown("# 🌐 CivicSphere — Inteligência Territorial\n"
                "Território · Organizações · Interlocutores · Demandas · Potencialidades · Projetos")

    # ---------------------------------------------------------------- Super Agente
    with gr.Tab("🧠 Super Agente"):
        gr.Markdown("O agente trabalha **somente com o que está cadastrado** e separa o que é oficial, comunitário, "
                    "documental, não verificado e inferência. Não pesquisa na internet e não recebe dados de pessoas.")
        with gr.Row():
            ag_terr = dd("Território", g_terr)
            ag_modo = gr.Dropdown(_enum_opts(T.MODOS_MISSAO), value="diagnostico", label="Tipo de missão")
        with gr.Row():
            ag_cat = gr.Dropdown([c[0] for c in repo.opcoes_categoria("organizacao")], label="Tipo de organização-alvo (opcional)")
            ag_obj = gr.Textbox(label="Objetivo da missão", lines=3)
        ag_btn = gr.Button("Gerar", variant="primary")
        ag_out = gr.Markdown()
        with gr.Accordion("Lacunas de informação detectadas pelo sistema", open=True):
            ag_lac = gr.Markdown()
        ag_btn.click(a_missao, [ag_terr, ag_modo, ag_cat, ag_obj], [ag_out, ag_lac])

    # ---------------------------------------------------------------- Territórios
    with gr.Tab("🗺️ Territórios"):
        gr.Markdown("Dois cadastros independentes e relacionados: **oficial** (IBGE, órgãos públicos) e "
                    "**comunitário** (reconhecido pelos moradores). Não se misturam.")
        b_ibge = gr.Button("Importar os 246 municípios do IBGE")
        s_terr = gr.Markdown()
        ligar(b_ibge, a_importar_ibge, [], s_terr)
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Cadastro oficial")
                to_nome = gr.Textbox(label="Nome")
                to_tipo = gr.Dropdown(_enum_opts(T.TIPOS_TERRITORIO_OFICIAL), value="bairro", label="Tipo")
                to_pai = dd("Território superior (ex.: município do bairro)", g_terr_oficial)
                to_cod = gr.Textbox(label="Código IBGE (se houver)")
                to_fonte = gr.Textbox(label="Fonte")
                to_val = gr.Dropdown(VALID_OPTS, value="nao_verificado", label="Validação")
                to_btn = gr.Button("Cadastrar território oficial")
            with gr.Column():
                gr.Markdown("### Cadastro comunitário")
                tc_nome = gr.Textbox(label="Nome (como a comunidade chama)")
                tc_tipo = gr.Dropdown(_enum_opts(T.TIPOS_TERRITORIO_COMUNITARIO), value="comunidade_urbana", label="Tipo")
                tc_of = dd("Território oficial relacionado", g_terr_oficial)
                tc_desc = gr.Textbox(label="Descrição", lines=2)
                tc_fonte = gr.Textbox(label="Fonte (quem informou / como foi levantado)")
                tc_val = gr.Dropdown(VALID_OPTS, value="nao_verificado", label="Validação")
                tc_btn = gr.Button("Cadastrar território comunitário")
        s_terr2 = gr.Markdown()
        ligar(to_btn, a_terr_oficial, [to_nome, to_tipo, to_pai, to_cod, to_fonte, to_val], s_terr2)
        ligar(tc_btn, a_terr_comunitario, [tc_nome, tc_tipo, tc_of, tc_desc, tc_fonte, tc_val], s_terr2)
        tabela(["Cadastro", "Tipo", "Nome", "Código", "UF", "Validação", "Fonte"], t_territorios)

    # ---------------------------------------------------------------- Organizações
    with gr.Tab("🏛️ Organizações"):
        gr.Markdown("**Organização** = entidade coletiva. **Atuação** = o que ela faz. Pessoas ficam na aba Interlocutores.")
        with gr.Row():
            with gr.Column():
                o_nome = gr.Textbox(label="Nome")
                o_sigla = gr.Textbox(label="Sigla")
                o_cat = dd("Categoria", g_cat("organizacao"))
                o_area = gr.Textbox(label="Área de atuação")
                o_fin = gr.Textbox(label="Finalidades institucionais", lines=2)
                o_cont = gr.Textbox(label="Contato público da organização")
                o_fonte = gr.Textbox(label="Fonte da informação")
                with gr.Row():
                    o_orig = gr.Dropdown(ORIGENS_OPTS, value="nao_verificada", label="Natureza da informação")
                    o_val = gr.Dropdown(VALID_OPTS, value="nao_verificado", label="Validação")
                o_terr = dd("Territórios de abrangência", g_terr, multi=True)
                o_btn = gr.Button("Cadastrar organização", variant="primary")
            with gr.Column():
                gr.Markdown("### Atuação (projeto, iniciativa, serviço...)")
                at_org = dd("Organização", g_org)
                at_tipo = dd("Tipo de atuação", g_cat("atuacao"))
                at_tit = gr.Textbox(label="Título")
                at_desc = gr.Textbox(label="Descrição", lines=2)
                at_sit = gr.Dropdown(_enum_opts(T.SITUACAO_ATUACAO), value="em_andamento", label="Situação")
                at_fonte = gr.Textbox(label="Fonte")
                at_orig = gr.Dropdown(ORIGENS_OPTS, value="nao_verificada", label="Natureza da informação")
                at_btn = gr.Button("Registrar atuação")
        s_org = gr.Markdown()
        ligar(o_btn, a_org, [o_nome, o_sigla, o_cat, o_area, o_fin, o_cont, o_fonte, o_orig, o_val, o_terr], s_org)
        ligar(at_btn, a_atuacao, [at_org, at_tipo, at_tit, at_desc, at_sit, at_fonte, at_orig], s_org)
        tabela(["ID", "Organização", "Sigla", "Categoria", "Área", "Natureza", "Validação"], t_orgs)
        tabela(["ID", "Organização", "Tipo", "Atuação", "Situação", "Validação"], t_atuacoes)

    # ---------------------------------------------------------------- Interlocutores
    with gr.Tab("👤 Interlocutores"):
        gr.Markdown("**Coleta mínima.** Registre só a função institucional. O sistema **recusa** religião, posição "
                    "política, filiação sindical/partidária e documentos pessoais. Contato só com autorização. "
                    "Esses dados nunca são enviados ao modelo de IA.")
        with gr.Row():
            with gr.Column():
                i_nome = gr.Textbox(label="Nome")
                i_base = gr.Dropdown(_enum_opts(T.BASES_LEGAIS), value="consentimento", label="Base legal")
                i_fin = gr.Textbox(label="Finalidade do registro (obrigatória)")
                i_cont = gr.Textbox(label="Forma de contato autorizada (opcional)")
                i_aut = gr.Checkbox(label="A pessoa autorizou o contato e o registro")
                i_pref = gr.Textbox(label="Preferências de comunicação")
                i_restr = gr.Textbox(label="Restrições (ex.: não contatar após 20h)")
                i_btn = gr.Button("Registrar interlocutor", variant="primary")
            with gr.Column():
                gr.Markdown("### Representação (pessoa ↔ organização)")
                r_pessoa = dd("Pessoa", g_int)
                r_org = dd("Organização", g_org)
                r_func = gr.Textbox(label="Função institucional (ex.: presidente, coordenadora)")
                r_fonte = gr.Textbox(label="Fonte")
                r_btn = gr.Button("Registrar representação")
                gr.Markdown("### Interação autorizada")
                x_pessoa = dd("Pessoa", g_int)
                x_canal = gr.Dropdown(_enum_opts(T.CANAIS_INTERACAO), value="mensagem", label="Canal")
                x_resumo = gr.Textbox(label="Resumo (assunto tratado)")
                x_btn = gr.Button("Registrar interação")
                gr.Markdown("### Direito de eliminação")
                e_pessoa = dd("Pessoa", g_int)
                e_btn = gr.Button("Eliminar pessoa e registros dependentes", variant="stop")
        s_int = gr.Markdown()
        ligar(i_btn, a_interlocutor, [i_nome, i_base, i_fin, i_cont, i_aut, i_pref, i_restr], s_int)
        ligar(r_btn, a_representacao, [r_pessoa, r_org, r_func, r_fonte], s_int)
        ligar(x_btn, a_interacao, [x_pessoa, x_canal, x_resumo], s_int)
        ligar(e_btn, a_eliminar, [e_pessoa], s_int)
        tabela(["ID", "Nome", "Base legal", "Contato autorizado", "Finalidade"], t_interlocutores)

    # ---------------------------------------------------------------- Demandas
    with gr.Tab("📣 Demandas"):
        with gr.Row():
            with gr.Column():
                d_tit = gr.Textbox(label="Título")
                d_desc = gr.Textbox(label="Descrição", lines=3)
                d_cat = dd("Categoria temática", g_cat("demanda"))
                d_esc = gr.Dropdown(_enum_opts(T.ESCALAS_DEMANDA), value="bairro_comunidade", label="Escala")
                d_org = dd("Organização que apresentou (opcional)", g_org)
                d_fonte = gr.Textbox(label="Fonte")
                with gr.Row():
                    d_orig = gr.Dropdown(ORIGENS_OPTS, value="comunitaria", label="Natureza da informação")
                    d_val = gr.Dropdown(VALID_OPTS, value="nao_verificado", label="Validação")
                d_to = dd("Território de origem", g_terr)
                d_ta = dd("Territórios afetados", g_terr, multi=True)
                d_data = gr.Textbox(label="Data de identificação (AAAA-MM-DD)")
                d_orgao = gr.Textbox(label="Órgão ou instituição relacionado")
                d_btn = gr.Button("Registrar demanda", variant="primary")
            with gr.Column():
                gr.Markdown("### Prioridade — decisão humana registrada")
                p_dem = dd("Demanda", g_dem)
                p_niv = gr.Dropdown(_enum_opts(T.NIVEIS_PRIORIDADE), value="media", label="Nível")
                p_crit = gr.Textbox(label="Critérios usados", lines=2)
                p_quem = gr.Textbox(label="Quem decidiu (assembleia, conselho, pessoa...)")
                p_btn = gr.Button("Registrar decisão")
                gr.Markdown("### Situação no ciclo de acompanhamento")
                s_dem = dd("Demanda", g_dem)
                s_sit = gr.Dropdown(_enum_opts(T.SITUACAO_DEMANDA), value="registrada", label="Nova situação")
                s_btn = gr.Button("Atualizar situação")
        s_d = gr.Markdown()
        ligar(d_btn, a_demanda, [d_tit, d_desc, d_cat, d_esc, d_org, d_fonte, d_orig, d_val, d_to, d_ta, d_data, d_orgao], s_d)
        ligar(p_btn, a_prioridade, [p_dem, p_niv, p_crit, p_quem], s_d)
        ligar(s_btn, a_situacao_demanda, [s_dem, s_sit], s_d)
        tabela(["ID", "Título", "Categoria", "Escala", "Situação", "Prioridade", "Decidida por", "Natureza", "Validação"], t_demandas)

    # ---------------------------------------------------------------- Potencialidades
    with gr.Tab("🌱 Potencialidades"):
        with gr.Row():
            with gr.Column():
                pt_tit = gr.Textbox(label="Título")
                pt_desc = gr.Textbox(label="Descrição", lines=3)
                pt_cat = dd("Categoria", g_cat("potencialidade"))
                pt_loc = gr.Textbox(label="Localização (descrição)")
                pt_pos = gr.Textbox(label="Possibilidades de desenvolvimento", lines=2)
                pt_fonte = gr.Textbox(label="Fonte")
                with gr.Row():
                    pt_orig = gr.Dropdown(ORIGENS_OPTS, value="comunitaria", label="Natureza da informação")
                    pt_val = gr.Dropdown(VALID_OPTS, value="nao_verificado", label="Validação")
                pt_terr = dd("Territórios", g_terr, multi=True)
                pt_btn = gr.Button("Registrar potencialidade", variant="primary")
            with gr.Column():
                gr.Markdown("### Relacionar demanda ↔ potencialidade")
                rl_dem = dd("Demanda", g_dem)
                rl_pot = dd("Potencialidade", g_pot)
                rl_btn = gr.Button("Relacionar")
        s_p = gr.Markdown()
        ligar(pt_btn, a_pot, [pt_tit, pt_desc, pt_cat, pt_loc, pt_pos, pt_fonte, pt_orig, pt_val, pt_terr], s_p)
        ligar(rl_btn, a_relacionar, [rl_dem, rl_pot], s_p)
        tabela(["ID", "Título", "Categoria", "Natureza", "Validação"], t_pot)

    # ---------------------------------------------------------------- Projetos
    with gr.Tab("🛠️ Projetos"):
        with gr.Row():
            with gr.Column():
                pj_tit = gr.Textbox(label="Título")
                pj_obj = gr.Textbox(label="Objetivos", lines=2)
                pj_eta = gr.Textbox(label="Etapas", lines=2)
                pj_rec = gr.Textbox(label="Recursos necessários", lines=2)
                pj_ben = gr.Textbox(label="Beneficiários (definidos de forma legítima)")
                pj_res = gr.Textbox(label="Responsáveis (funções ou organizações)")
                pj_ind = gr.Textbox(label="Indicadores")
                pj_sit = gr.Dropdown(_enum_opts(T.SITUACAO_PROJETO), value="proposta", label="Situação")
            with gr.Column():
                pj_dem = dd("Demanda de origem (opcional)", g_dem)
                pj_pot = dd("Potencialidade de origem (opcional)", g_pot)
                pj_org = dd("Organizações participantes", g_org, multi=True)
                pj_terr = dd("Territórios de atuação", g_terr, multi=True)
                pj_btn = gr.Button("Registrar projeto", variant="primary")
        s_pj = gr.Markdown()
        ligar(pj_btn, a_projeto, [pj_tit, pj_obj, pj_eta, pj_rec, pj_ben, pj_res, pj_ind, pj_sit, pj_dem, pj_pot,
                                  pj_org, pj_terr], s_pj)
        tabela(["ID", "Título", "Situação", "Proposto por", "Validação"], t_proj)

    # ---------------------------------------------------------------- Articulação
    with gr.Tab("🤝 Articulação e evidências"):
        gr.Markdown("A participação é registrada de forma **agregada**: sem lista de pessoas e sem monitoramento individual.")
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Evidência")
                ev_ent = gr.Dropdown(list(T.ENTIDADES), value="demanda", label="Vincular a")
                ev_id = gr.Number(label="ID do registro", precision=0)
                ev_tit = gr.Textbox(label="Título")
                ev_tipo = gr.Dropdown(_enum_opts(T.TIPOS_EVIDENCIA), value="documento", label="Tipo")
                ev_ref = gr.Textbox(label="Referência (link, nº do documento, local de guarda)")
                ev_data = gr.Textbox(label="Data do documento")
                ev_btn = gr.Button("Anexar evidência")
                gr.Markdown("### Resultado / indicador")
                rs_ent = gr.Dropdown(list(T.ENTIDADES), value="projeto", label="Vincular a")
                rs_id = gr.Number(label="ID do registro", precision=0)
                rs_ind = gr.Textbox(label="Indicador")
                rs_val = gr.Textbox(label="Valor")
                rs_desc = gr.Textbox(label="Descrição")
                rs_btn = gr.Button("Registrar resultado")
            with gr.Column():
                gr.Markdown("### Encaminhamento")
                en_dem = dd("Demanda", g_dem)
                en_proj = dd("Projeto", g_proj)
                en_inst = gr.Textbox(label="Instituição")
                en_desc = gr.Textbox(label="Descrição", lines=2)
                en_sit = gr.Dropdown(_enum_opts(T.SITUACAO_ENCAMINHAMENTO), value="enviado", label="Situação")
                en_resp = gr.Textbox(label="Resposta recebida")
                en_btn = gr.Button("Registrar encaminhamento")
                gr.Markdown("### Reunião, consulta ou fórum")
                pa_tipo = gr.Dropdown(_enum_opts(T.TIPOS_PARTICIPACAO), value="reuniao", label="Tipo")
                pa_tit = gr.Textbox(label="Título")
                pa_data = gr.Textbox(label="Data")
                pa_terr = dd("Território", g_terr)
                pa_desc = gr.Textbox(label="Descrição", lines=2)
                pa_dec = gr.Textbox(label="Decisões coletivas", lines=2)
                pa_n = gr.Number(label="Nº de participantes (total)", precision=0)
                pa_btn = gr.Button("Registrar")
        s_a = gr.Markdown()
        ligar(ev_btn, a_evidencia, [ev_ent, ev_id, ev_tit, ev_tipo, ev_ref, ev_data], s_a)
        ligar(rs_btn, a_resultado, [rs_ent, rs_id, rs_ind, rs_val, rs_desc], s_a)
        ligar(en_btn, a_encam, [en_dem, en_proj, en_inst, en_desc, en_sit, en_resp], s_a)
        ligar(pa_btn, a_partic, [pa_tipo, pa_tit, pa_data, pa_terr, pa_desc, pa_dec, pa_n], s_a)
        tabela(["ID", "Tipo", "Título", "Data", "Participantes", "Decisões"], t_partic)
        tabela(["ID", "Demanda", "Projeto", "Instituição", "Situação", "Resposta"], t_encam)

    # ---------------------------------------------------------------- Sistema
    with gr.Tab("⚙️ Sistema"):
        st = gr.Markdown(status_sistema())
        REFRESH.append((st, lambda: gr.update(value=status_sistema())))
        gr.Markdown("### Exportar e restaurar (portabilidade)")
        ex_btn = gr.Button("Exportar base (JSON)")
        ex_file = gr.File(label="Arquivo exportado")
        ex_btn.click(a_exportar, [], ex_file)
        rt_file = gr.File(label="Arquivo para restaurar (.json)")
        rt_sub = gr.Checkbox(label="Substituir dados existentes")
        rt_btn = gr.Button("Restaurar")
        rt_out = gr.Markdown()
        ligar(rt_btn, a_restaurar, [rt_file, rt_sub], rt_out)
        gr.Markdown("### Auditoria (últimas 300 operações)")
        tabela(["ID", "Data/hora", "Usuário", "Ação", "Tabela", "Registro"], t_audit)

    # ---------------------------------------------------------------- ligações finais
    todos = [c for c, _ in REFRESH]
    for botao, fn, entradas, saida, muta in WIRES:
        ev = botao.click(fn, entradas, saida)
        if muta:
            ev.then(refresh, [], todos)
    demo.load(refresh, [], todos)
    demo.queue()


if __name__ == "__main__":
    auth = (config.APP_USER, config.APP_PASSWORD) if config.APP_USER and config.APP_PASSWORD else None
    demo.launch(server_name=config.HOST, server_port=config.PORT, auth=auth)
