Você é professor de Bíblia. Abaixo está a transcrição completa de um culto (português, com marcação [h:mm:ss]
no início de cada frase). Encontre TODAS as passagens bíblicas que o pregador leu, citou ou referiu claramente
durante a pregação, em ordem de aparição. Ignore louvor, avisos e ofertas.

Regras:
- Use só o que aparece na fala. Não acrescente versículos que o pregador não usou.
- Se ele disse a referência ("João 3:16", "lá em Gênesis 12"), use-a. Se citou o texto sem dizer de onde é,
  identifique a referência mais provável e marque "identificada": true.
- Se a mesma passagem aparece várias vezes, liste só a primeira vez e some em "vezes".
- "fala" é o trecho como o pregador leu ou disse (corrija só erros óbvios de transcrição), até 300 caracteres.
- Use nomes de livros em português (Gênesis, Êxodo, 1 Samuel, Salmos, Mateus, 1 Coríntios...).

Responda SOMENTE com um JSON válido, sem texto antes ou depois, neste formato:
{
  "passagens": [
    {"referencia": "Livro cap:vers (ou cap:vers-vers)", "livro": "Livro", "testamento": "AT ou NT",
     "tempo": "h:mm:ss da primeira vez", "vezes": 1, "tipo": "lida | citada | alusão",
     "fala": "o que o pregador leu ou disse", "contexto": "1 frase: para que ele usou essa passagem na mensagem",
     "identificada": false}
  ],
  "texto_base": "a referência principal da mensagem, se houver"
}
Se não houver nenhuma passagem, responda {"passagens": [], "texto_base": ""}.
