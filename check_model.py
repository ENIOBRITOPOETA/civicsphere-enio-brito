"""Lista os modelos disponíveis na sua chave NVIDIA e testa o modelo configurado.

Uso:  NVIDIA_API_KEY=... python check_model.py
"""
import sys

import config
from agent import criar_cliente


def main():
    if not config.NVIDIA_API_KEY:
        print("NVIDIA_API_KEY não definida.")
        return 1
    cliente = criar_cliente()
    try:
        modelos = sorted(m.id for m in cliente.models.list().data)
        print(f"{len(modelos)} modelos disponíveis. Procurando 'deepseek':")
        for m in modelos:
            if "deepseek" in m.lower():
                print("  ", m)
    except Exception as e:  # noqa: BLE001
        print("Não foi possível listar os modelos:", e)
    print(f"\nTestando o modelo configurado: {config.NVIDIA_MODEL}")
    try:
        r = cliente.chat.completions.create(
            model=config.NVIDIA_MODEL, max_tokens=20,
            messages=[{"role": "user", "content": "Responda apenas: ok"}])
        print("Resposta:", r.choices[0].message.content)
        return 0
    except Exception as e:  # noqa: BLE001
        print("FALHOU:", e)
        print("Ajuste NVIDIA_MODEL para um dos nomes listados acima.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
