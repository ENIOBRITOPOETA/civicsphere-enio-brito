"""Taxonomia única do CivicSphere.

Tudo que é classificação vive aqui e só aqui. O banco, a interface e o agente leem
destas listas; para ampliar uma categoria basta acrescentar uma linha (o banco
semeia as categorias novas na próxima inicialização, sem reconstruir nada).
"""

# ---------------------------------------------------------------------------
# Eixos temáticos do Super Agente
# (derivados das áreas de inteligência discutidas; ajuste os textos se os
#  "quatro princípios fundadores" originais tiverem outra redação)
# ---------------------------------------------------------------------------
PRINCIPIOS = {
    "educacao_politica": "Educação política: formação cidadã, participação, transparência e controle social.",
    "ambientalismo": "Ambientalismo: nascentes, recursos hídricos, resíduos, agroecologia e recuperação ambiental.",
    "mobilidade_urbana": "Mobilidade urbana: transporte coletivo, mobilidade ativa e acesso ao território.",
    "empreendedorismo_solidario": "Empreendedorismo solidário: cooperativas, economia solidária, trabalho e renda.",
}

# ---------------------------------------------------------------------------
# Natureza e confiabilidade da informação
# ---------------------------------------------------------------------------
ORIGENS = {
    "oficial": "OFICIAL",
    "comunitaria": "COMUNITÁRIA",
    "documental": "DOCUMENTAL",
    "nao_verificada": "NÃO VERIFICADA",
    "inferencia_agente": "INFERÊNCIA DO AGENTE",
}
VALIDACAO = ["nao_verificado", "em_verificacao", "verificado", "contestado"]

# ---------------------------------------------------------------------------
# Território
# ---------------------------------------------------------------------------
TIPOS_TERRITORIO_OFICIAL = [
    "estado", "municipio", "distrito", "bairro", "setor", "povoado",
    "assentamento", "territorio_reconhecido", "outra_divisao",
]
TIPOS_TERRITORIO_COMUNITARIO = [
    "comunidade_urbana", "comunidade_rural", "ocupacao", "nucleo_habitacional",
    "comunidade_tradicional", "localidade_reconhecida", "territorio_atuacao",
]
ESCALAS_DEMANDA = {
    "bairro_comunidade": "Bairro ou comunidade",
    "regiao_bairros": "Região ou conjunto de bairros",
    "municipio": "Município",
    "regiao": "Região geográfica ou administrativa",
    "estado": "Estado",
    "interestadual_nacional": "Interestadual ou nacional",
    "tematica_transversal": "Temática/setorial que atravessa territórios",
}

# ---------------------------------------------------------------------------
# Categorias (tabela `categorias`): (codigo, nome, grupo)
# ORGANIZAÇÃO = entidade coletiva. Pessoas NÃO são categorizadas por religião,
# política ou filiação: interlocutores têm apenas função institucional.
# ---------------------------------------------------------------------------
CATEGORIAS = {
    "organizacao": [
        ("ong", "ONG / instituto", "sociedade civil"),
        ("associacao_comunitaria", "Associação comunitária / de moradores", "sociedade civil"),
        ("associacao_cultural", "Associação cultural", "sociedade civil"),
        ("associacao_profissional", "Associação profissional", "sociedade civil"),
        ("movimento_social", "Movimento ou iniciativa social", "sociedade civil"),
        ("organizacao_juvenil", "Organização / movimento de jovens e estudantes", "sociedade civil"),
        ("grupo_mulheres", "Grupo de mulheres", "sociedade civil"),
        ("organizacao_religiosa", "Organização religiosa (institucional)", "sociedade civil"),
        ("sindicato", "Sindicato / entidade de trabalhadores", "trabalho"),
        ("cooperativa", "Cooperativa", "economia solidária"),
        ("empreendimento_solidario", "Empreendimento / rede de economia solidária", "economia solidária"),
        ("comercio_local", "Comércio local / associação comercial", "economia"),
        ("organizacao_cultural", "Coletivo artístico / grupo cultural", "cultura"),
        ("organizacao_ambiental", "Organização ou coletivo ambiental", "meio ambiente"),
        ("organizacao_rural", "Organização rural / associação de produtores", "campo"),
        ("instituicao_educacional", "Instituição educacional", "serviços e instituições"),
        ("instituicao_saude", "Instituição ou entidade de saúde", "serviços e instituições"),
        ("conselho_forum", "Conselho / fórum de participação", "participação"),
        ("orgao_publico", "Órgão ou equipamento público", "poder público"),
    ],
    "demanda": [
        ("saude", "Saúde", "setorial"),
        ("educacao", "Educação", "setorial"),
        ("habitacao", "Habitação", "setorial"),
        ("regularizacao_fundiaria", "Regularização fundiária", "setorial"),
        ("mobilidade_transporte", "Mobilidade e transporte", "setorial"),
        ("trabalho_renda", "Trabalho e renda", "setorial"),
        ("agricultura_familiar", "Agricultura familiar", "setorial"),
        ("reforma_agraria", "Reforma agrária", "setorial"),
        ("cultura", "Cultura", "setorial"),
        ("meio_ambiente", "Meio ambiente", "setorial"),
        ("saneamento", "Saneamento básico", "setorial"),
        ("seguranca_alimentar", "Segurança alimentar", "setorial"),
        ("juventude", "Juventude", "setorial"),
        ("pessoa_idosa", "Direitos da pessoa idosa", "setorial"),
        ("pessoa_deficiencia", "Direitos das pessoas com deficiência", "setorial"),
        ("esporte_lazer", "Esporte e lazer", "setorial"),
        ("empreendedorismo_solidario", "Empreendedorismo solidário", "setorial"),
        ("infraestrutura", "Infraestrutura urbana e rural", "setorial"),
        ("inclusao_digital", "Inclusão digital", "setorial"),
        ("participacao_popular", "Participação popular", "setorial"),
    ],
    "potencialidade": [
        ("producao_agricola", "Produção agrícola", "econômica"),
        ("agricultura_familiar", "Agricultura familiar", "econômica"),
        ("cooperativismo", "Cooperativas", "econômica"),
        ("pequenos_empreendimentos", "Pequenos empreendimentos", "econômica"),
        ("comercio_local", "Comércio local", "econômica"),
        ("economia_solidaria", "Economia solidária", "econômica"),
        ("turismo_comunitario", "Turismo comunitário", "econômica"),
        ("artesanato", "Artesanato", "econômica"),
        ("cadeias_produtivas", "Cadeias produtivas regionais", "econômica"),
        ("conhecimento_tecnico", "Conhecimentos técnicos e profissionais", "econômica"),
        ("nascentes_agua", "Nascentes e recursos hídricos", "ambiental"),
        ("areas_verdes", "Áreas verdes e biodiversidade", "ambiental"),
        ("recuperacao_ambiental", "Projetos de recuperação ambiental", "ambiental"),
        ("coleta_reciclagem", "Coleta seletiva e reciclagem", "ambiental"),
        ("agroecologia", "Produção agroecológica", "ambiental"),
        ("energias_renovaveis", "Energias renováveis", "ambiental"),
        ("artistas_artesaos", "Artistas, escritores e artesãos", "cultural"),
        ("grupos_musicais", "Grupos musicais e manifestações populares", "cultural"),
        ("patrimonio_historico", "Patrimônio histórico", "cultural"),
        ("saberes_tradicionais", "Saberes tradicionais", "cultural"),
        ("espacos_culturais", "Espaços culturais, festivais e eventos", "cultural"),
        ("voluntariado_solidariedade", "Voluntariado e redes de solidariedade", "humana e social"),
        ("cuidado_coletivo", "Iniciativas de cuidado coletivo", "humana e social"),
        ("experiencias_educacionais", "Experiências educacionais", "humana e social"),
        ("capacidade_organizativa", "Capacidades organizativas", "humana e social"),
        ("equipamentos_publicos", "Equipamentos públicos", "institucional"),
        ("instituicoes_ensino", "Universidades, escolas e centros de formação", "institucional"),
        ("programas_publicos", "Programas públicos", "institucional"),
        ("espacos_comunitarios", "Espaços disponíveis para atividades comunitárias", "institucional"),
    ],
    # ATUAÇÃO = o que uma organização faz (projeto, iniciativa, serviço...). Não é a organização.
    "atuacao": [
        ("projeto", "Projeto", "atuação"),
        ("iniciativa", "Iniciativa", "atuação"),
        ("servico", "Serviço continuado", "atuação"),
        ("evento_recorrente", "Evento recorrente", "atuação"),
        ("campanha", "Campanha", "atuação"),
        ("articulacao", "Articulação / rede", "atuação"),
    ],
}

SITUACAO_ATUACAO = ["planejada", "em_andamento", "concluida", "suspensa"]

# Ciclo de acompanhamento da demanda (ordem importa)
SITUACAO_DEMANDA = [
    "identificada", "registrada", "verificada", "classificada", "priorizada",
    "em_proposta", "encaminhada", "em_acompanhamento", "avaliada", "arquivada",
]
SITUACAO_PROJETO = ["proposta", "planejado", "em_execucao", "concluido", "suspenso"]
SITUACAO_ENCAMINHAMENTO = ["enviado", "em_analise", "respondido", "atendido", "negado", "sem_resposta"]
NIVEIS_PRIORIDADE = ["baixa", "media", "alta", "urgente"]

TIPOS_EVIDENCIA = ["documento", "link", "ata", "foto", "declaracao", "dado_publico"]
TIPOS_PARTICIPACAO = ["reuniao", "consulta", "forum", "proposta", "contribuicao", "decisao_coletiva"]
CANAIS_INTERACAO = ["telefone", "mensagem", "email", "presencial", "reuniao"]

# Base legal (LGPD, art. 7º) aceitas para registrar uma pessoa interlocutora
BASES_LEGAIS = ["consentimento", "legitimo_interesse", "obrigacao_legal", "politicas_publicas"]

# Entidades que podem receber território, evidência, vínculos e resultados
ENTIDADES = {
    "organizacao": "organizacoes",
    "atuacao": "atuacoes",
    "demanda": "demandas",
    "potencialidade": "potencialidades",
    "projeto": "projetos",
}

MODOS_MISSAO = {
    "diagnostico": "Diagnóstico territorial (o que está comprovado, informado e por verificar)",
    "relacionar": "Relacionar demandas e potencialidades",
    "projeto": "Propor projeto ou ação de baixo custo",
    "articulacao": "Estratégia de articulação com um tipo de organização",
}
