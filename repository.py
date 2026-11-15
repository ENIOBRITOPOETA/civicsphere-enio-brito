"""Camada de dados: toda leitura/escrita do CivicSphere passa por aqui.

- Gravação genérica com colunas validadas contra o próprio esquema (sem listas duplicadas).
- Auditoria automática de cada alteração.
- Regras de privacidade aplicadas antes de gravar pessoas.
- Montagem do contexto territorial usado pelo agente (sem dados pessoais).
"""
import json
from contextlib import contextmanager
from datetime import date

import database
import privacy
import taxonomy as T
from privacy import PrivacyError

TABELAS = set(database.ORDEM_TABELAS)
_NAO_EDITAVEIS = {"id", "criado_em", "atualizado_em", "ts"}
_CATEGORIA_DA_TABELA = {
    "organizacoes": "organizacao",
    "atuacoes": "atuacao",
    "demandas": "demanda",
    "potencialidades": "potencialidade",
}
_TEXTOS_PESSOAIS = {
    "interlocutores": ["finalidade", "preferencias_comunicacao", "restricoes"],
    "representacoes": ["funcao"],
    "interacoes": ["resumo"],
}
_MASCARAR_NA_AUDITORIA = {"interlocutores": ["contato", "nome"], "interacoes": ["resumo"]}


class Repo:
    def __init__(self, caminho):
        self.caminho = caminho
        self._colunas = {}

    # ------------------------------------------------------------------ base
    def inicializar(self):
        database.inicializar(self.caminho)
        self.semear_categorias()

    @contextmanager
    def conn(self):
        c = database.conectar(self.caminho)
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def colunas(self, tabela):
        if tabela not in TABELAS:
            raise ValueError(f"Tabela desconhecida: {tabela}")
        if tabela not in self._colunas:
            with self.conn() as c:
                info = c.execute(f"PRAGMA table_info({tabela})").fetchall()
            self._colunas[tabela] = [r["name"] for r in info]
        return self._colunas[tabela]

    def _limpar(self, tabela, dados):
        validas = set(self.colunas(tabela)) - _NAO_EDITAVEIS
        limpo = {}
        for k, v in dados.items():
            if k not in validas:
                raise ValueError(f"Campo '{k}' não existe em {tabela}.")
            if isinstance(v, str):
                v = v.strip()
            limpo[k] = None if v == "" else v
        return limpo

    def _auditar(self, c, usuario, acao, tabela, rid, antes, depois):
        mascara = _MASCARAR_NA_AUDITORIA.get(tabela, [])

        def mask(d):
            if d is None:
                return None
            return json.dumps({k: ("***" if k in mascara else v) for k, v in d.items()},
                              ensure_ascii=False, default=str)

        c.execute(
            "INSERT INTO auditoria(usuario, acao, tabela, registro_id, antes, depois) VALUES (?,?,?,?,?,?)",
            (usuario, acao, tabela, rid, mask(antes), mask(depois)),
        )

    def _checar_categoria(self, c, tabela, dados):
        tipo = _CATEGORIA_DA_TABELA.get(tabela)
        if tipo and dados.get("categoria_id") is not None:
            r = c.execute("SELECT tipo FROM categorias WHERE id=?", (dados["categoria_id"],)).fetchone()
            if not r or r["tipo"] != tipo:
                raise ValueError(f"A categoria informada não é do tipo '{tipo}'.")

    # ------------------------------------------------------------------ CRUD
    def criar(self, tabela, dados, usuario="sistema"):
        dados = self._limpar(tabela, dados)
        if tabela in _TEXTOS_PESSOAIS:
            privacy.verificar_pessoa(dados, _TEXTOS_PESSOAIS[tabela])
        if not dados:
            raise ValueError("Nenhum dado informado.")
        with self.conn() as c:
            self._checar_categoria(c, tabela, dados)
            cols = ", ".join(dados)
            marcas = ", ".join("?" for _ in dados)
            cur = c.execute(f"INSERT INTO {tabela} ({cols}) VALUES ({marcas})", list(dados.values()))
            rid = cur.lastrowid
            self._auditar(c, usuario, "criar", tabela, rid, None, dados)
        return rid

    def atualizar(self, tabela, rid, dados, usuario="sistema"):
        dados = self._limpar(tabela, dados)
        if tabela in _TEXTOS_PESSOAIS:
            privacy.verificar_pessoa(dados, _TEXTOS_PESSOAIS[tabela])
        with self.conn() as c:
            antes = c.execute(f"SELECT * FROM {tabela} WHERE id=?", (rid,)).fetchone()
            if not antes:
                raise ValueError(f"Registro {rid} não encontrado em {tabela}.")
            self._checar_categoria(c, tabela, dados)
            sets = ", ".join(f"{k}=?" for k in dados)
            c.execute(
                f"UPDATE {tabela} SET {sets}, atualizado_em=datetime('now') WHERE id=?"
                if "atualizado_em" in self.colunas(tabela) else f"UPDATE {tabela} SET {sets} WHERE id=?",
                list(dados.values()) + [rid],
            )
            self._auditar(c, usuario, "atualizar", tabela, rid,
                          {k: antes[k] for k in dados}, dados)

    def obter(self, tabela, rid):
        with self.conn() as c:
            r = c.execute(f"SELECT * FROM {tabela} WHERE id=?", (rid,)).fetchone()
        return dict(r) if r else None

    def listar(self, tabela, filtros=None, ordem="id DESC", limite=500):
        if tabela not in TABELAS:
            raise ValueError(f"Tabela desconhecida: {tabela}")
        validas = set(self.colunas(tabela))
        where, vals = [], []
        for k, v in (filtros or {}).items():
            if k not in validas:
                raise ValueError(f"Filtro inválido: {k}")
            where.append(f"{k}=?")
            vals.append(v)
        sql = f"SELECT * FROM {tabela}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if ordem.split()[0] not in validas:
            ordem = "id DESC"
        sql += f" ORDER BY {ordem} LIMIT {int(limite)}"
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, vals).fetchall()]

    def contar(self, tabela):
        with self.conn() as c:
            return c.execute(f"SELECT COUNT(*) n FROM {tabela}").fetchone()["n"]

    # ------------------------------------------------------------ categorias
    def semear_categorias(self):
        with self.conn() as c:
            for tipo, itens in T.CATEGORIAS.items():
                for codigo, nome, grupo in itens:
                    c.execute(
                        "INSERT INTO categorias(tipo, codigo, nome, grupo) VALUES (?,?,?,?) "
                        "ON CONFLICT(tipo, codigo) DO UPDATE SET nome=excluded.nome, grupo=excluded.grupo",
                        (tipo, codigo, nome, grupo),
                    )

    def opcoes_categoria(self, tipo):
        with self.conn() as c:
            rows = c.execute(
                "SELECT id, nome, grupo FROM categorias WHERE tipo=? AND ativa=1 ORDER BY grupo, nome", (tipo,)
            ).fetchall()
        return [(f"{r['nome']}", r["id"]) for r in rows]

    def categoria_id(self, tipo, codigo):
        with self.conn() as c:
            r = c.execute("SELECT id FROM categorias WHERE tipo=? AND codigo=?", (tipo, codigo)).fetchone()
        return r["id"] if r else None

    # ------------------------------------------------------------- territórios
    def importar_municipios(self, municipios, fonte, esperado=246, usuario="sistema"):
        """municipios: lista de (codigo_ibge, nome). Retorna (quantidade, verificado)."""
        completo = len(municipios) == esperado
        validacao = "verificado" if completo else "em_verificacao"
        hoje = date.today().isoformat()
        with self.conn() as c:
            est = c.execute("SELECT id FROM territorios_oficiais WHERE tipo='estado' AND uf='GO'").fetchone()
            if est:
                estado_id = est["id"]
            else:
                estado_id = c.execute(
                    "INSERT INTO territorios_oficiais(codigo_ibge, nome, tipo, uf, fonte, data_fonte, validacao) "
                    "VALUES ('52','Goiás','estado','GO',?,?,?)", (fonte, hoje, validacao)).lastrowid
            for codigo, nome in municipios:
                ja = c.execute("SELECT id FROM territorios_oficiais WHERE codigo_ibge=?", (str(codigo),)).fetchone()
                if ja:
                    c.execute("UPDATE territorios_oficiais SET nome=?, fonte=?, data_fonte=?, validacao=?, "
                              "atualizado_em=datetime('now') WHERE id=?", (nome, fonte, hoje, validacao, ja["id"]))
                else:
                    c.execute(
                        "INSERT INTO territorios_oficiais(codigo_ibge, nome, tipo, uf, pai_id, fonte, data_fonte, validacao) "
                        "VALUES (?,?,'municipio','GO',?,?,?,?)",
                        (str(codigo), nome, estado_id, fonte, hoje, validacao))
            self._auditar(c, usuario, "importar_municipios", "territorios_oficiais", None, None,
                          {"quantidade": len(municipios), "fonte": fonte, "validacao": validacao})
        return len(municipios), completo

    def semear_provisorio(self, nomes, fonte):
        """Só se NÃO houver município algum: base mínima para uso offline, marcada como não verificada."""
        with self.conn() as c:
            if c.execute("SELECT COUNT(*) n FROM territorios_oficiais WHERE tipo='municipio'").fetchone()["n"]:
                return 0
            est = c.execute("SELECT id FROM territorios_oficiais WHERE tipo='estado' AND uf='GO'").fetchone()
            estado_id = est["id"] if est else c.execute(
                "INSERT INTO territorios_oficiais(nome, tipo, uf, fonte, validacao) "
                "VALUES ('Goiás','estado','GO',?, 'nao_verificado')", (fonte,)).lastrowid
            for nome in nomes:
                c.execute(
                    "INSERT OR IGNORE INTO territorios_oficiais(nome, tipo, uf, pai_id, fonte, validacao) "
                    "VALUES (?,'municipio','GO',?,?,'nao_verificado')", (nome, estado_id, fonte))
            self._auditar(c, "sistema", "semear_provisorio", "territorios_oficiais", None, None,
                          {"quantidade": len(nomes), "fonte": fonte})
        return len(nomes)

    def territorios_opcoes(self):
        """[(rótulo, 'oficial:ID' | 'comunitario:ID')]"""
        out = []
        with self.conn() as c:
            for r in c.execute("SELECT id, nome, tipo, uf FROM territorios_oficiais ORDER BY uf, tipo, nome"):
                out.append((f"[oficial · {r['tipo']}] {r['nome']} ({r['uf']})", f"oficial:{r['id']}"))
            for r in c.execute(
                "SELECT t.id, t.nome, t.tipo, o.nome AS mun FROM territorios_comunitarios t "
                "LEFT JOIN territorios_oficiais o ON o.id=t.oficial_id ORDER BY t.nome"):
                ref = f" — {r['mun']}" if r["mun"] else ""
                out.append((f"[comunitário · {r['tipo']}] {r['nome']}{ref}", f"comunitario:{r['id']}"))
        return out

    @staticmethod
    def parse_territorio(valor):
        tipo, _, rid = str(valor).partition(":")
        if tipo not in ("oficial", "comunitario") or not rid.isdigit():
            raise ValueError("Território inválido.")
        return tipo, int(rid)

    def _nome_territorio(self, c, tipo, rid):
        tabela = "territorios_oficiais" if tipo == "oficial" else "territorios_comunitarios"
        r = c.execute(f"SELECT nome FROM {tabela} WHERE id=?", (rid,)).fetchone()
        return r["nome"] if r else None

    # ------------------------------------------------------- relações genéricas
    def _existe(self, c, entidade_tipo, rid):
        tabela = T.ENTIDADES.get(entidade_tipo)
        if not tabela:
            raise ValueError(f"Tipo de entidade inválido: {entidade_tipo}")
        if not c.execute(f"SELECT 1 FROM {tabela} WHERE id=?", (rid,)).fetchone():
            raise ValueError(f"{entidade_tipo} {rid} não existe.")

    def definir_abrangencia(self, entidade_tipo, entidade_id, territorio, papel="abrangencia", usuario="sistema"):
        ttipo, tid = territorio if isinstance(territorio, tuple) else self.parse_territorio(territorio)
        with self.conn() as c:
            self._existe(c, entidade_tipo, entidade_id)
            if self._nome_territorio(c, ttipo, tid) is None:
                raise ValueError("Território não encontrado.")
            c.execute(
                "INSERT OR IGNORE INTO abrangencias(entidade_tipo, entidade_id, territorio_tipo, territorio_id, papel) "
                "VALUES (?,?,?,?,?)", (entidade_tipo, entidade_id, ttipo, tid, papel))
            self._auditar(c, usuario, "abrangencia", "abrangencias", None, None,
                          {"entidade": f"{entidade_tipo}:{entidade_id}", "territorio": f"{ttipo}:{tid}", "papel": papel})

    def vincular(self, a_tipo, a_id, b_tipo, b_id, papel="relacionado", usuario="sistema"):
        with self.conn() as c:
            self._existe(c, a_tipo, a_id)
            self._existe(c, b_tipo, b_id)
            c.execute("INSERT OR IGNORE INTO vinculos(a_tipo, a_id, b_tipo, b_id, papel) VALUES (?,?,?,?,?)",
                      (a_tipo, a_id, b_tipo, b_id, papel))
            self._auditar(c, usuario, "vincular", "vinculos", None, None,
                          {"a": f"{a_tipo}:{a_id}", "b": f"{b_tipo}:{b_id}", "papel": papel})

    def anexar_evidencia(self, entidade_tipo, entidade_id, titulo, tipo, referencia=None, data_documento=None,
                         usuario="sistema"):
        with self.conn() as c:
            self._existe(c, entidade_tipo, entidade_id)
        return self.criar("evidencias", {"entidade_tipo": entidade_tipo, "entidade_id": entidade_id,
                                         "titulo": titulo, "tipo": tipo, "referencia": referencia,
                                         "data_documento": data_documento}, usuario)

    def registrar_resultado(self, entidade_tipo, entidade_id, indicador, valor=None, descricao=None, data=None,
                            fonte=None, usuario="sistema"):
        with self.conn() as c:
            self._existe(c, entidade_tipo, entidade_id)
        return self.criar("resultados", {"entidade_tipo": entidade_tipo, "entidade_id": entidade_id,
                                         "indicador": indicador, "valor": valor, "descricao": descricao,
                                         "data": data, "fonte": fonte}, usuario)

    # ---------------------------------------------------------------- pessoas
    def criar_interlocutor(self, nome, base_legal, finalidade, contato=None, contato_autorizado=False,
                           preferencias=None, restricoes=None, usuario="sistema"):
        if base_legal not in T.BASES_LEGAIS:
            raise PrivacyError("Informe uma base legal válida para registrar a pessoa.")
        if not (finalidade or "").strip():
            raise PrivacyError("Toda pessoa registrada precisa de finalidade documentada.")
        if (contato or "").strip():
            if not contato_autorizado:
                raise PrivacyError("Contato só pode ser guardado com autorização registrada.")
            if base_legal != "consentimento":
                raise PrivacyError("Contato pessoal exige base legal 'consentimento'.")
        rid = self.criar("interlocutores", {
            "nome": nome, "base_legal": base_legal, "finalidade": finalidade,
            "contato": contato if contato_autorizado else None,
            "contato_autorizado": 1 if (contato_autorizado and (contato or "").strip()) else 0,
            "preferencias_comunicacao": preferencias, "restricoes": restricoes}, usuario)
        self.criar("consentimentos", {
            "interlocutor_id": rid, "finalidade": finalidade, "base_legal": base_legal,
            "concedido": 1 if contato_autorizado else 0, "data": date.today().isoformat()}, usuario)
        return rid

    def criar_representacao(self, interlocutor_id, organizacao_id, funcao, fonte=None, usuario="sistema"):
        return self.criar("representacoes", {"interlocutor_id": interlocutor_id, "organizacao_id": organizacao_id,
                                             "funcao": funcao, "fonte": fonte}, usuario)

    def registrar_interacao(self, interlocutor_id, canal, resumo, data=None, usuario="sistema"):
        p = self.obter("interlocutores", interlocutor_id)
        if not p:
            raise ValueError("Interlocutor não encontrado.")
        if not p["contato_autorizado"]:
            raise PrivacyError("Sem contato autorizado: não é permitido registrar interações com esta pessoa.")
        return self.criar("interacoes", {"interlocutor_id": interlocutor_id, "canal": canal, "resumo": resumo,
                                         "data": data or date.today().isoformat()}, usuario)

    def eliminar_interlocutor(self, interlocutor_id, usuario="sistema"):
        """Direito de eliminação (LGPD): apaga a pessoa e tudo o que depende dela."""
        with self.conn() as c:
            if not c.execute("SELECT 1 FROM interlocutores WHERE id=?", (interlocutor_id,)).fetchone():
                raise ValueError("Interlocutor não encontrado.")
            c.execute("DELETE FROM interacoes WHERE interlocutor_id=?", (interlocutor_id,))
            c.execute("DELETE FROM representacoes WHERE interlocutor_id=?", (interlocutor_id,))
            c.execute("DELETE FROM consentimentos WHERE interlocutor_id=?", (interlocutor_id,))
            c.execute("DELETE FROM interlocutores WHERE id=?", (interlocutor_id,))
            self._auditar(c, usuario, "eliminar", "interlocutores", interlocutor_id, None, None)

    # ---------------------------------------------------------------- demandas
    def decidir_prioridade(self, demanda_id, nivel, criterios, decidido_por, usuario="sistema"):
        """A prioridade é sempre decisão humana registrada; o agente apenas sugere critérios."""
        if nivel not in T.NIVEIS_PRIORIDADE:
            raise ValueError("Nível de prioridade inválido.")
        if not (criterios or "").strip() or not (decidido_por or "").strip():
            raise ValueError("Informe os critérios e quem decidiu (pessoa, assembleia, conselho...).")
        d = self.obter("demandas", demanda_id)
        if not d:
            raise ValueError("Demanda não encontrada.")
        dados = {"prioridade_nivel": nivel, "prioridade_criterios": criterios,
                 "prioridade_decidida_por": decidido_por}
        antes = T.SITUACAO_DEMANDA.index(d["situacao"])
        if antes < T.SITUACAO_DEMANDA.index("priorizada"):
            dados["situacao"] = "priorizada"
        self.atualizar("demandas", demanda_id, dados, usuario)

    # ------------------------------------------------------- contexto do agente
    def _descendentes(self, c, raiz):
        return [r["id"] for r in c.execute(
            "WITH RECURSIVE d(id) AS (SELECT ? UNION ALL "
            "SELECT t.id FROM territorios_oficiais t JOIN d ON t.pai_id=d.id) SELECT id FROM d", (raiz,))]

    def _ancestrais(self, c, ini):
        return [r["id"] for r in c.execute(
            "WITH RECURSIVE a(id, pai) AS (SELECT id, pai_id FROM territorios_oficiais WHERE id=? UNION ALL "
            "SELECT t.id, t.pai_id FROM territorios_oficiais t JOIN a ON t.id=a.pai) SELECT id FROM a", (ini,))]

    @staticmethod
    def _in(lista):
        return ",".join("?" for _ in lista) or "NULL"

    def _ids_por_territorio(self, c, entidade_tipo, oficiais, comunitarios):
        sql = ("SELECT DISTINCT entidade_id FROM abrangencias WHERE entidade_tipo=? AND ("
               f"(territorio_tipo='oficial' AND territorio_id IN ({self._in(oficiais)})) OR "
               f"(territorio_tipo='comunitario' AND territorio_id IN ({self._in(comunitarios)})))")
        return [r["entidade_id"] for r in c.execute(sql, [entidade_tipo, *oficiais, *comunitarios])]

    def _linhas(self, c, tabela, ids, extra_select, limite):
        if not ids:
            return [], 0
        ids = sorted(set(ids))
        total = len(ids)
        marcas = self._in(ids[:limite])
        rows = c.execute(f"SELECT {extra_select} FROM {tabela} t WHERE t.id IN ({marcas})", ids[:limite]).fetchall()
        return [dict(r) for r in rows], total

    def contexto_territorial(self, territorio, limite=40):
        """Reúne o que o sistema SABE sobre um território. Nunca inclui pessoas nem contatos pessoais."""
        ttipo, tid = territorio if isinstance(territorio, tuple) else self.parse_territorio(territorio)
        with self.conn() as c:
            if ttipo == "oficial":
                base = c.execute("SELECT * FROM territorios_oficiais WHERE id=?", (tid,)).fetchone()
                if not base:
                    raise ValueError("Território não encontrado.")
                baixo = self._descendentes(c, tid)
                alto = self._ancestrais(c, tid)
                com_ids = [r["id"] for r in c.execute(
                    f"SELECT id FROM territorios_comunitarios WHERE oficial_id IN ({self._in(baixo)})", baixo)]
                rotulo = ORIGEM_TERRITORIO["oficial"]
            else:
                base = c.execute("SELECT * FROM territorios_comunitarios WHERE id=?", (tid,)).fetchone()
                if not base:
                    raise ValueError("Território não encontrado.")
                baixo, com_ids = [], [tid]
                alto = self._ancestrais(c, base["oficial_id"]) if base["oficial_id"] else []
                rotulo = ORIGEM_TERRITORIO["comunitario"]

            ctx = {"territorio": {**dict(base), "tipo_cadastro": ttipo, "natureza": rotulo},
                   "contagens_totais": {}}
            ctx["hierarquia_oficial"] = [r["nome"] for r in c.execute(
                f"SELECT nome FROM territorios_oficiais WHERE id IN ({self._in(alto)})", alto)]
            ctx["comunidades"] = [dict(r) for r in c.execute(
                f"SELECT id, nome, tipo, validacao, fonte FROM territorios_comunitarios "
                f"WHERE id IN ({self._in(com_ids)}) LIMIT {limite}", com_ids)]

            # Organizações e atuações: do território e de tudo que está abaixo dele
            org_ids = self._ids_por_territorio(c, "organizacao", baixo, com_ids)
            ctx["organizacoes"], ctx["contagens_totais"]["organizacoes"] = self._linhas(
                c, "organizacoes", org_ids,
                "t.id, t.nome, t.sigla, (SELECT nome FROM categorias WHERE id=t.categoria_id) categoria, "
                "t.area_atuacao, t.finalidades, t.contato_publico, t.origem, t.validacao", limite)
            if org_ids:
                ctx["atuacoes"], ctx["contagens_totais"]["atuacoes"] = self._linhas(
                    c, "atuacoes",
                    [r["id"] for r in c.execute(
                        f"SELECT id FROM atuacoes WHERE organizacao_id IN ({self._in(org_ids)})", org_ids)],
                    "t.id, t.titulo, t.descricao, t.situacao, t.organizacao_id, "
                    "(SELECT nome FROM categorias WHERE id=t.categoria_id) tipo, t.origem, t.validacao", limite)
            else:
                ctx["atuacoes"] = []

            # Demandas e potencialidades: do território, abaixo dele e também as de escala mais ampla que o alcançam
            dem_ids = self._ids_por_territorio(c, "demanda", baixo + alto, com_ids)
            ctx["demandas"], ctx["contagens_totais"]["demandas"] = self._linhas(
                c, "demandas", dem_ids,
                "t.id, t.titulo, t.descricao, (SELECT nome FROM categorias WHERE id=t.categoria_id) categoria, "
                "t.escala, t.situacao, t.orgao_relacionado, t.pendencias, t.prioridade_nivel, "
                "t.prioridade_decidida_por, t.origem, t.validacao, "
                "(SELECT COUNT(*) FROM evidencias e WHERE e.entidade_tipo='demanda' AND e.entidade_id=t.id) n_evidencias", limite)
            pot_ids = self._ids_por_territorio(c, "potencialidade", baixo + alto, com_ids)
            ctx["potencialidades"], ctx["contagens_totais"]["potencialidades"] = self._linhas(
                c, "potencialidades", pot_ids,
                "t.id, t.titulo, t.descricao, (SELECT nome FROM categorias WHERE id=t.categoria_id) categoria, "
                "t.possibilidades, t.origem, t.validacao, "
                "(SELECT COUNT(*) FROM evidencias e WHERE e.entidade_tipo='potencialidade' AND e.entidade_id=t.id) n_evidencias",
                limite)
            proj_ids = set(self._ids_por_territorio(c, "projeto", baixo + alto, com_ids))
            for r in c.execute(
                    "SELECT DISTINCT b_id FROM vinculos WHERE b_tipo='projeto' AND a_tipo='demanda' "
                    f"AND a_id IN ({self._in(dem_ids)})", dem_ids):
                proj_ids.add(r["b_id"])
            ctx["projetos"], ctx["contagens_totais"]["projetos"] = self._linhas(
                c, "projetos", list(proj_ids),
                "t.id, t.titulo, t.objetivos, t.situacao, t.proposto_por, t.validacao", limite)
            ctx["vinculos"] = [dict(r) for r in c.execute(
                "SELECT a_tipo, a_id, b_tipo, b_id, papel FROM vinculos WHERE "
                f"(a_tipo='demanda' AND a_id IN ({self._in(dem_ids)})) OR "
                f"(a_tipo='potencialidade' AND a_id IN ({self._in(pot_ids)})) LIMIT 200", [*dem_ids, *pot_ids])]
        ctx["lacunas"] = lacunas(ctx)
        return ctx

    # ---------------------------------------------------------------- missões
    def iniciar_missao(self, modo, territorio, categoria_alvo, objetivo, modelo, usuario="sistema"):
        ttipo, tid = (None, None)
        if territorio:
            ttipo, tid = territorio if isinstance(territorio, tuple) else self.parse_territorio(territorio)
        return self.criar("missoes", {"modo": modo, "territorio_tipo": ttipo, "territorio_id": tid,
                                      "categoria_alvo": categoria_alvo, "objetivo": objetivo, "modelo": modelo},
                          usuario)

    def concluir_missao(self, mid, resposta=None, erro=None):
        self.atualizar("missoes", mid, {"status": "erro" if erro else "concluida",
                                        "resposta": resposta, "erro": erro})

    # ------------------------------------------------- exportação / restauração
    def exportar(self):
        dados = {"sistema": "CivicSphere", "formato": 1, "gerado_em": date.today().isoformat(), "tabelas": {}}
        with self.conn() as c:
            for t in database.ORDEM_TABELAS:
                dados["tabelas"][t] = [dict(r) for r in c.execute(f"SELECT * FROM {t}")]
        return dados

    def restaurar(self, dados, substituir=False):
        if dados.get("sistema") != "CivicSphere":
            raise ValueError("Arquivo não é uma exportação do CivicSphere.")
        c = database.conectar(self.caminho)
        try:
            c.execute("PRAGMA foreign_keys=OFF")
            tem_dados = any(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                            for t in ("organizacoes", "demandas", "potencialidades", "projetos", "interlocutores"))
            if tem_dados and not substituir:
                raise ValueError("A base já tem dados. Use substituir=True para sobrescrever.")
            c.execute("BEGIN")
            for t in reversed(database.ORDEM_TABELAS):
                c.execute(f"DELETE FROM {t}")
            for t in database.ORDEM_TABELAS:
                for linha in dados["tabelas"].get(t, []):
                    cols = ", ".join(linha)
                    c.execute(f"INSERT INTO {t} ({cols}) VALUES ({','.join('?' for _ in linha)})", list(linha.values()))
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()
        self.semear_categorias()


ORIGEM_TERRITORIO = {"oficial": "OFICIAL", "comunitario": "COMUNITÁRIA"}


def lacunas(ctx):
    """Lacunas de informação calculadas localmente, sem modelo de linguagem."""
    L = []
    t = ctx["territorio"]
    if t.get("validacao") != "verificado":
        L.append(f"O próprio território ({t['nome']}) não está validado (situação: {t.get('validacao')}).")
    if not t.get("fonte"):
        L.append("O território não tem fonte registrada.")
    if t["tipo_cadastro"] == "oficial" and not ctx["comunidades"]:
        L.append("Nenhuma comunidade (cadastro comunitário) registrada neste território.")
    orgs = ctx["organizacoes"]
    if not orgs:
        L.append("Nenhuma organização registrada com abrangência neste território.")
    else:
        nv = sum(1 for o in orgs if o["validacao"] != "verificado")
        if nv:
            L.append(f"{nv} de {len(orgs)} organizações ainda não verificadas.")
    dem = ctx["demandas"]
    if not dem:
        L.append("Nenhuma demanda registrada para este território.")
    else:
        se = sum(1 for d in dem if not d["n_evidencias"])
        if se:
            L.append(f"{se} de {len(dem)} demandas sem evidência anexada.")
        sp = sum(1 for d in dem if not d["prioridade_decidida_por"])
        if sp:
            L.append(f"{sp} demandas sem prioridade decidida por pessoas/coletivo (o agente não define prioridade).")
        rel = {v["a_id"] for v in ctx["vinculos"] if v["a_tipo"] == "demanda"}
        sr = sum(1 for d in dem if d["id"] not in rel)
        if sr:
            L.append(f"{sr} demandas ainda sem relação com potencialidades ou projetos.")
    pot = ctx["potencialidades"]
    if not pot:
        L.append("Nenhuma potencialidade mapeada para este território.")
    elif any(p["validacao"] != "verificado" for p in pot):
        L.append("Há potencialidades não verificadas.")
    for nome, total in ctx["contagens_totais"].items():
        if total > len(ctx.get(nome, [])):
            L.append(f"Contexto truncado: {len(ctx[nome])} de {total} registros de {nome} enviados ao agente.")
    return L
