Você é pastor, professor de Bíblia e redator de conteúdo cristão. Abaixo está a transcrição completa de um
culto (português, com marcação [h:mm:ss] no início de cada frase). Ignore louvor, avisos e ofertas: use só a
pregação. Seja fiel ao que o pregador disse: não invente histórias, nomes nem versículos que ele não citou
(na parte de devocional você pode sugerir versículos que combinem, marcando "sugerido": true).

Gere material de estudo, devocional e frases de efeito. Responda SOMENTE com um JSON válido, sem texto antes
ou depois, neste formato:
{
  "estudo": {
    "tema_central": "uma frase com a ideia principal da mensagem",
    "resumo": "1 parágrafo de 5 a 7 frases resumindo a pregação",
    "textos_base": [{"referencia": "Livro cap:vers", "sugerido": false}],
    "pontos": [{"titulo": "ponto principal da mensagem", "explicacao": "2 a 3 frases", "tempo": "h:mm:ss onde começa"}],
    "licoes": [{"licao": "lição prática em 1 frase", "aplicacao": "o que fazer esta semana, bem concreto"}],
    "perguntas": ["5 a 7 perguntas para célula / pequeno grupo, da mais leve à mais profunda"]
  },
  "devocional": [
    {"dia": 1, "titulo": "título curto", "versiculo": "Livro cap:vers", "sugerido": false,
     "reflexao": "4 a 6 frases ligando o versículo à mensagem", "pratica": "uma ação simples para o dia",
     "oracao": "oração curta de 2 a 3 frases"}
  ],
  "frases": [
    {"frase": "frase de efeito", "tempo": "h:mm:ss", "original": true,
     "uso": "legenda | thumbnail | carrossel | story | título"}
  ]
}
Regras:
- "pontos": 3 a 6; "licoes": 4 a 6; "devocional": 5 dias;
- "frases": 15 a 25. Pelo menos metade "original": true (copiadas como o pregador disse, só tirando vícios de
  fala), com o "tempo" exato. As outras "original": false são frases curtas e marcantes inspiradas na
  mensagem (até 12 palavras), com o "tempo" do trecho que inspirou;
- ordene as frases da mais forte para a mais fraca.
