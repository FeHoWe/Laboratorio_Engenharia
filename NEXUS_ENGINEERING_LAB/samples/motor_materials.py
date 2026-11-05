"""Materiais TÍPICOS (didáticos) para o exemplo "Motor 4 cilindros".

O NEXUS nunca atribui material sozinho: isto só roda quando o usuário pede
(menu Material › Aplicar materiais típicos ao exemplo). São escolhas plausíveis de
projeto, não dados de um motor real. Vela e junta ficam de fora de propósito
(são conjuntos multimaterial — o usuário decide).
"""
# prefixo do nome da peça -> nome do material no banco
TYPICAL = {
    "Bloco do motor": "Ferro fundido cinzento ASTM A159",
    "Cabecote": "Aluminum alloy 360",
    "Tampa de valvulas": "Aluminum alloy 360",
    "Carter de oleo": "Aluminum alloy 360",
    "Virabrequim": "Aço-liga AISI 4140",
    "Volante do motor": "Ferro fundido cinzento ASTM A159",
    "Polia do virabrequim": "Ferro fundido cinzento ASTM A159",
    "Biela": "Aço-liga AISI 4140",
    "Pistao": "Aluminum alloy 2024-T6",
    "Pino do pistao": "Aço-liga AISI 4140",
    "Parafuso do cabecote": "Aço-liga AISI 4140",
    "Comando de admissao": "Ferro fundido nodular ASTM A536",
    "Comando de escape": "Ferro fundido nodular ASTM A536",
    "Valvula de admissao": "AISI 410 stainless steel",
    "Valvula de escape": "Inconel 718",
    "Coletor de admissao": "Nylon 6,6 (PA66)",
    "Coletor de escape": "Ferro fundido cinzento ASTM A159",
    "Filtro de oleo": "Aluminum alloy 3003, rolled",
    "Alternador": "Aluminum alloy 360",
    "Mola de valvula": "Aço-liga AISI 4140",              # aço-mola não consta do banco: o 4140 é só um valor típico de aço-liga
    "Roda dentada do comando": "Aluminum alloy 360",
    "Roda dentada do virabrequim": "Aço carbono",
    "Roda tensora dentada": "Aço carbono",
    "Eixo do tensor": "Aço carbono",
    "Suporte do tensor": "Aço carbono",
    "Correia dentada": "Policloropreno (CR)",
    "Dente da correia": "Policloropreno (CR)",
    "Engrenagem do comando": "Aço carbono",
}


def material_for(part_name: str):
    """Maior prefixo que casa com o nome (aceita sufixos como ' 1', ' 2')."""
    best = None
    for prefix in TYPICAL:
        if part_name.startswith(prefix) and (best is None or len(prefix) > len(best)):
            best = prefix
    return TYPICAL[best] if best else None
