"""Super Agente CivicSphere: monta o contexto, chama o modelo e registra a missão.

Limites assumidos (e declarados ao modelo):
- só raciocina sobre o que está no CONTEXTO enviado; não tem acesso à internet;
- nunca recebe dados pessoais de interlocutores (nomes, contatos);
- não define prioridades: sugere critérios, quem decide são pessoas/coletivos.
"""
import json

import config
import taxonomy as T
from repository import Repo

SISTEMA = """Você é o SUPER AGENTE DO CIVICSPHERE, plataforma de inteligência territorial e participação social em Goiás.

EIXOS DE ATUAÇÃO:
{eixos}

SEPARAÇÃO CONCEITUAL (não confundir):
- ORGANIZAÇÃO = entidade coletiva que atua no território.
- ATUAÇÃO = o que a organização faz (projeto, iniciativa, serviço).
- INTERLOCUTOR = pessoa que representa uma organização. Você NÃO recebe dados de pessoas.

REGRAS DE VERACIDADE (invioláveis):
1. Use somente o CONTEXTO fornecido. Nunca invente lideranças, contatos, organizações, demandas, números, leis ou estatísticas.
2. Você NÃO tem acesso à internet nesta versão. Se algo exigir consulta externa, diga "A VERIFICAR" e indique o tipo de fonte pública que deveria ser consultada (ex.: IBGE, prefeitura, Ministério Público), sem afirmar o conteúdo dela.
3. Marque toda afirmação relevante com um rótulo:
   [OFICIAL] cadastro oficial · [COMUNITÁRIA] informado pela comunidade · [DOCUMENTAL] sustentado por evidência anexada · [NÃO VERIFICADA] registrada mas sem verificação · [INFERÊNCIA DO AGENTE] conclusão ou proposta sua.
   Itens do contexto trazem 'origem' e 'validacao'; respeite-os. Se n_evidencias = 0, não trate como documental.
4. Toda proposta sua é [INFERÊNCIA DO AGENTE]. Distinga claramente fato registrado de proposta.
5. Liste as LACUNAS DE INFORMAÇÃO e o que fazer para preenchê-las.

PRIVACIDADE E ÉTICA:
- Não crie nem sugira perfis de pessoas. Não infira religião, opinião política ou filiação de ninguém. Trabalhe com organizações, funções institucionais e territórios.
- Não defina a prioridade final de demandas: proponha critérios transparentes e indique que a decisão é da comunidade, registrada por pessoas.
- Prefira ações de baixo custo, articulação com o que já existe no território e participação voluntária e transparente.
- Responda em português do Brasil, em Markdown, de forma objetiva."""

FORMATOS = {
    "diagnostico": "Entregue: 1) Resumo do território; 2) O que está comprovado; 3) O que foi informado pela comunidade; 4) O que ainda precisa ser verificado; 5) Lacunas e como preenchê-las.",
    "relacionar": "Entregue: relações possíveis entre demandas e potencialidades/organizações/atuações existentes no contexto, cada uma com justificativa e rótulo; ao final, o que falta para confirmar cada relação.",
    "projeto": "Entregue uma proposta de projeto de baixo custo ancorada em demanda(s) e potencialidade(s) do contexto: origem, objetivos, território, organizações envolvidas (somente as do contexto), etapas, recursos, indicadores, riscos e o que precisa ser verificado antes de começar.",
    "articulacao": "Entregue uma estratégia de articulação com o tipo de organização indicado, usando apenas organizações e atuações do contexto: abordagem, mensagens-chave, formatos de participação, cuidados com proteção de dados e lacunas a preencher.",
}


def criar_cliente():
    from openai import OpenAI  # import tardio: o app abre mesmo sem a biblioteca instalada
    return OpenAI(base_url=config.NVIDIA_BASE_URL, api_key=config.NVIDIA_API_KEY, timeout=config.LLM_TIMEOUT)


def montar_mensagens(modo, contexto, categoria_alvo, objetivo):
    eixos = "\n".join(f"- {d}" for d in T.PRINCIPIOS.values())
    sistema = SISTEMA.format(eixos=eixos)
    corpo = {k: v for k, v in contexto.items() if k not in ("lacunas",)}
    usuario = (
        f"MODO: {T.MODOS_MISSAO[modo]}\n"
        f"TIPO DE ORGANIZAÇÃO-ALVO: {categoria_alvo or 'não especificado'}\n"
        f"OBJETIVO DA MISSÃO: {objetivo or 'não especificado'}\n\n"
        f"{FORMATOS[modo]}\n\n"
        f"LACUNAS JÁ DETECTADAS PELO SISTEMA:\n" + "\n".join(f"- {x}" for x in contexto["lacunas"]) + "\n\n"
        f"CONTEXTO (única fonte de fatos; JSON):\n```json\n{json.dumps(corpo, ensure_ascii=False, default=str)}\n```"
    )
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


def executar_missao(repo: Repo, territorio, modo, categoria_alvo, objetivo, usuario="sistema", cliente=None):
    """Retorna (markdown_resposta, markdown_lacunas, id_missao)."""
    if modo not in T.MODOS_MISSAO:
        raise ValueError("Modo de missão inválido.")
    contexto = repo.contexto_territorial(territorio, limite=config.MAX_ITENS_CONTEXTO)
    lacunas_md = "\n".join(f"- {x}" for x in contexto["lacunas"]) or "- Nenhuma lacuna detectada pelas regras automáticas."
    mid = repo.iniciar_missao(modo, territorio, categoria_alvo, objetivo, config.NVIDIA_MODEL, usuario)

    if cliente is None:
        if not config.NVIDIA_API_KEY:
            msg = "NVIDIA_API_KEY não configurada no servidor. Defina a variável de ambiente e reinicie."
            repo.concluir_missao(mid, erro=msg)
            return f"⚠️ {msg}", lacunas_md, mid
        cliente = criar_cliente()

    try:
        r = cliente.chat.completions.create(
            model=config.NVIDIA_MODEL,
            messages=montar_mensagens(modo, contexto, categoria_alvo, objetivo),
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )
        texto = (r.choices[0].message.content or "").strip()
        if not texto:
            raise RuntimeError("O modelo devolveu resposta vazia.")
    except Exception as e:  # noqa: BLE001 - erro de rede/modelo vira mensagem, não derruba a interface
        repo.concluir_missao(mid, erro=str(e))
        return (f"⚠️ Falha ao consultar o modelo `{config.NVIDIA_MODEL}`: {e}\n\n"
                "Verifique a chave e o nome do modelo com `python check_model.py`."), lacunas_md, mid

    repo.concluir_missao(mid, resposta=texto)
    return texto, lacunas_md, mid
