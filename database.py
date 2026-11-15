"""Esquema relacional normalizado (SQLite, portável para PostgreSQL).

Princípios do desenho
- Organização, Interlocutor e Atuação são três entidades distintas.
- Território oficial e comunitário são dois cadastros independentes, ligados por
  `territorios_comunitarios.oficial_id`.
- Relações com território, evidências e resultados são genéricas (uma tabela cada),
  em vez de uma tabela por combinação: sem duplicação e extensível.
- Toda gravação passa por `auditoria` (ver repository.py).
"""
import sqlite3
from pathlib import Path

import taxonomy as T


def _enum(valores) -> str:
    return ", ".join(f"'{v}'" for v in valores)


_TS = ("criado_em TEXT NOT NULL DEFAULT (datetime('now')), "
       "atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))")
_VALID = f"validacao TEXT NOT NULL DEFAULT 'nao_verificado' CHECK(validacao IN ({_enum(T.VALIDACAO)}))"
_ORIGEM = f"origem TEXT NOT NULL DEFAULT 'nao_verificada' CHECK(origem IN ({_enum(T.ORIGENS)}))"
_ENT = _enum(T.ENTIDADES)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS territorios_oficiais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_ibge TEXT UNIQUE,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ({_enum(T.TIPOS_TERRITORIO_OFICIAL)})),
    uf TEXT NOT NULL DEFAULT 'GO',
    pai_id INTEGER REFERENCES territorios_oficiais(id),
    fonte TEXT, data_fonte TEXT,
    {_VALID},
    observacoes TEXT,
    {_TS}
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_terr_oficial
    ON territorios_oficiais(tipo, uf, nome, COALESCE(pai_id, 0));

CREATE TABLE IF NOT EXISTS territorios_comunitarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ({_enum(T.TIPOS_TERRITORIO_COMUNITARIO)})),
    oficial_id INTEGER REFERENCES territorios_oficiais(id),
    descricao TEXT,
    fonte TEXT, data_fonte TEXT,
    {_VALID},
    {_TS}
);

CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK(tipo IN ('organizacao','demanda','potencialidade','atuacao')),
    codigo TEXT NOT NULL,
    nome TEXT NOT NULL,
    grupo TEXT,
    ativa INTEGER NOT NULL DEFAULT 1,
    UNIQUE(tipo, codigo)
);

-- ORGANIZAÇÃO: entidade coletiva que atua no território
CREATE TABLE IF NOT EXISTS organizacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    sigla TEXT,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    area_atuacao TEXT,
    finalidades TEXT,
    contato_publico TEXT,
    fonte TEXT, data_fonte TEXT,
    {_ORIGEM},
    {_VALID},
    ativa INTEGER NOT NULL DEFAULT 1,
    {_TS}
);

-- INTERLOCUTOR: pessoa com relação autorizada. Coleta mínima; sem dados sensíveis.
CREATE TABLE IF NOT EXISTS interlocutores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    base_legal TEXT NOT NULL CHECK(base_legal IN ({_enum(T.BASES_LEGAIS)})),
    finalidade TEXT NOT NULL,
    contato TEXT,
    contato_autorizado INTEGER NOT NULL DEFAULT 0,
    preferencias_comunicacao TEXT,
    restricoes TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    {_TS},
    CHECK(contato IS NULL OR contato_autorizado = 1)
);

-- REPRESENTAÇÃO: liga pessoa e organização pela função institucional
CREATE TABLE IF NOT EXISTS representacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interlocutor_id INTEGER NOT NULL REFERENCES interlocutores(id) ON DELETE CASCADE,
    organizacao_id INTEGER NOT NULL REFERENCES organizacoes(id),
    funcao TEXT NOT NULL,
    inicio TEXT, fim TEXT,
    fonte TEXT,
    {_VALID},
    {_TS},
    UNIQUE(interlocutor_id, organizacao_id, funcao)
);

-- ATUAÇÃO: o que a organização faz (projeto, iniciativa, serviço...)
CREATE TABLE IF NOT EXISTS atuacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organizacao_id INTEGER NOT NULL REFERENCES organizacoes(id),
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    titulo TEXT NOT NULL,
    descricao TEXT,
    situacao TEXT NOT NULL DEFAULT 'em_andamento' CHECK(situacao IN ({_enum(T.SITUACAO_ATUACAO)})),
    inicio TEXT, fim TEXT,
    fonte TEXT,
    {_ORIGEM},
    {_VALID},
    {_TS}
);

CREATE TABLE IF NOT EXISTS demandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descricao TEXT,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    escala TEXT NOT NULL CHECK(escala IN ({_enum(T.ESCALAS_DEMANDA)})),
    organizacao_id INTEGER REFERENCES organizacoes(id),
    fonte TEXT,
    data_identificacao TEXT,
    situacao TEXT NOT NULL DEFAULT 'identificada' CHECK(situacao IN ({_enum(T.SITUACAO_DEMANDA)})),
    orgao_relacionado TEXT,
    acoes_realizadas TEXT,
    pendencias TEXT,
    prioridade_nivel TEXT CHECK(prioridade_nivel IS NULL OR prioridade_nivel IN ({_enum(T.NIVEIS_PRIORIDADE)})),
    prioridade_criterios TEXT,
    prioridade_decidida_por TEXT,
    {_ORIGEM},
    {_VALID},
    {_TS}
);

CREATE TABLE IF NOT EXISTS potencialidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descricao TEXT,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id),
    localizacao TEXT,
    possibilidades TEXT,
    fonte TEXT,
    {_ORIGEM},
    {_VALID},
    {_TS}
);

CREATE TABLE IF NOT EXISTS projetos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    objetivos TEXT,
    etapas TEXT,
    recursos TEXT,
    beneficiarios TEXT,
    responsaveis TEXT,
    indicadores TEXT,
    situacao TEXT NOT NULL DEFAULT 'proposta' CHECK(situacao IN ({_enum(T.SITUACAO_PROJETO)})),
    proposto_por TEXT NOT NULL DEFAULT 'humano' CHECK(proposto_por IN ('humano','agente')),
    {_VALID},
    {_TS}
);

-- Relações genéricas entre entidades (org-projeto, demanda-potencialidade, demanda-projeto...)
CREATE TABLE IF NOT EXISTS vinculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a_tipo TEXT NOT NULL CHECK(a_tipo IN ({_ENT})),
    a_id INTEGER NOT NULL,
    b_tipo TEXT NOT NULL CHECK(b_tipo IN ({_ENT})),
    b_id INTEGER NOT NULL,
    papel TEXT NOT NULL DEFAULT 'relacionado',
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(a_tipo, a_id, b_tipo, b_id, papel)
);

-- Onde cada entidade atua / de onde vem / quem afeta (papel: origem, afetado, atuacao, abrangencia)
CREATE TABLE IF NOT EXISTS abrangencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ({_ENT})),
    entidade_id INTEGER NOT NULL,
    territorio_tipo TEXT NOT NULL CHECK(territorio_tipo IN ('oficial','comunitario')),
    territorio_id INTEGER NOT NULL,
    papel TEXT NOT NULL DEFAULT 'abrangencia',
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(entidade_tipo, entidade_id, territorio_tipo, territorio_id, papel)
);
CREATE INDEX IF NOT EXISTS ix_abrang_terr ON abrangencias(territorio_tipo, territorio_id);

CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ({_ENT})),
    entidade_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ({_enum(T.TIPOS_EVIDENCIA)})),
    referencia TEXT,
    data_documento TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_evid_ent ON evidencias(entidade_tipo, entidade_id);

CREATE TABLE IF NOT EXISTS encaminhamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id INTEGER REFERENCES demandas(id),
    projeto_id INTEGER REFERENCES projetos(id),
    instituicao TEXT NOT NULL,
    descricao TEXT,
    data TEXT,
    situacao TEXT NOT NULL DEFAULT 'enviado' CHECK(situacao IN ({_enum(T.SITUACAO_ENCAMINHAMENTO)})),
    resposta TEXT,
    {_TS},
    CHECK(demanda_id IS NOT NULL OR projeto_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS resultados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade_tipo TEXT NOT NULL CHECK(entidade_tipo IN ({_ENT})),
    entidade_id INTEGER NOT NULL,
    indicador TEXT NOT NULL,
    valor TEXT,
    descricao TEXT,
    data TEXT,
    fonte TEXT,
    {_TS}
);

-- Participação registrada de forma agregada: sem lista de pessoas, sem monitoramento individual
CREATE TABLE IF NOT EXISTS participacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK(tipo IN ({_enum(T.TIPOS_PARTICIPACAO)})),
    titulo TEXT NOT NULL,
    data TEXT,
    territorio_tipo TEXT CHECK(territorio_tipo IS NULL OR territorio_tipo IN ('oficial','comunitario')),
    territorio_id INTEGER,
    descricao TEXT,
    decisoes TEXT,
    numero_participantes INTEGER,
    {_TS}
);

CREATE TABLE IF NOT EXISTS interacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interlocutor_id INTEGER NOT NULL REFERENCES interlocutores(id) ON DELETE CASCADE,
    canal TEXT NOT NULL CHECK(canal IN ({_enum(T.CANAIS_INTERACAO)})),
    data TEXT,
    resumo TEXT,
    {_TS}
);

CREATE TABLE IF NOT EXISTS consentimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interlocutor_id INTEGER NOT NULL REFERENCES interlocutores(id) ON DELETE CASCADE,
    finalidade TEXT NOT NULL,
    base_legal TEXT NOT NULL,
    concedido INTEGER NOT NULL DEFAULT 0,
    data TEXT,
    validade TEXT,
    observacao TEXT,
    {_TS}
);

CREATE TABLE IF NOT EXISTS missoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    modo TEXT NOT NULL,
    territorio_tipo TEXT,
    territorio_id INTEGER,
    categoria_alvo TEXT,
    objetivo TEXT,
    modelo TEXT,
    status TEXT NOT NULL DEFAULT 'iniciada' CHECK(status IN ('iniciada','concluida','erro')),
    resposta TEXT,
    erro TEXT,
    {_TS}
);

CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (datetime('now')),
    usuario TEXT NOT NULL,
    acao TEXT NOT NULL,
    tabela TEXT NOT NULL,
    registro_id INTEGER,
    antes TEXT,
    depois TEXT
);
"""

# Ordem de dependência (usada na exportação/restauração)
ORDEM_TABELAS = [
    "territorios_oficiais", "territorios_comunitarios", "categorias", "organizacoes",
    "interlocutores", "representacoes", "atuacoes", "demandas", "potencialidades",
    "projetos", "vinculos", "abrangencias", "evidencias", "encaminhamentos",
    "resultados", "participacoes", "interacoes", "consentimentos", "missoes", "auditoria",
]


def conectar(caminho) -> sqlite3.Connection:
    c = sqlite3.connect(str(caminho))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def inicializar(caminho) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    c = conectar(caminho)
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()
