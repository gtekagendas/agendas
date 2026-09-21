# Painel Gtek — Agendas (standalone)

Versão do painel que roda **sem depender do Claude** e **sem precisar do
Google Cloud Console**: um robô do GitHub Actions busca os compromissos
direto dos links "secretos" em formato iCal de cada agenda, aplica as
mesmas regras de técnico/etiqueta do painel original, e publica uma
página estática atualizada — de tempos em tempos, sozinho.

## Estrutura

```
.github/workflows/update.yml   → o robô: quando e como ele roda
config/calendars.json          → as 9 agendas (nomes, cores, chave de cada uma)
config/settings.json           → etiquetas renomeadas/recoloridas/ocultas
config/event_overrides.json    → comentários e etiquetas por compromisso
scripts/build.py               → busca os dados (via iCal) e gera o index.html
scripts/template.html          → o "molde" visual da página
scripts/requirements.txt       → dependências Python
assets/logo.b64                → logo em base64
index.html                     → gerado automaticamente (não edite à mão)
```

## Configuração (única vez, ~10-15 min — não precisa de Google Cloud)

### 1. Pegar o link secreto iCal de cada uma das 9 agendas

Para **cada agenda** (Gtek Suporte, Ausente, Presencial/Online de Rafael e
Eviany, Agenda em comum, Contato retenções, Contato com cliente):

1. No Google Calendar, abra as **Configurações** (ícone de engrenagem) e clique na agenda específica na lista à esquerda.
2. Role até **"Integrar agenda"**.
3. Copie o **"Endereço secreto em formato iCal"** (não o público — esse não deixa a agenda visível na internet, só quem tem o link consegue ler).

Você vai terminar com 9 links, parecidos com:
`https://calendar.google.com/calendar/ical/xxxxx/private-yyyyy/basic.ics`

⚠️ Trate esses links como senha — quem tiver o link lê a agenda inteira.

### 2. Montar o JSON com os 9 links

Monte um único JSON associando a **chave** de cada agenda (veja `config/calendars.json`, campo `"key"`) ao link dela:

```json
{
  "gtek": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_ausente": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_presencial_rafael": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_online_rafael": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_comum": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_online_eviany": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
  "perif_presencial_eviany": "https://calendar.google.com/calendar/ical/.../private-.../basic.ics",
}
```

### 3. Subir os arquivos deste pacote para o repositório

No repositório `gtekagendas/agendas`, envie **todas** as pastas e arquivos deste pacote, mantendo a estrutura (arraste a pasta inteira na tela "Add file → Upload files", ou use `git` localmente).

### 4. Guardar o JSON dos links como segredo no GitHub

1. No repositório: **Settings → Secrets and variables → Actions**.
2. "New repository secret".
3. Nome: `ICAL_URLS_JSON`
4. Valor: cole o JSON inteiro montado no passo 2.
5. Salve.

Isso mantém os 9 links fora do código-fonte — nem aparecem no repositório público.

### 5. Ativar o GitHub Pages

Settings → Pages → Source: "Deploy from a branch" → Branch: `main` / `(root)` → Save.

### 6. Testar

Aba **Actions** → workflow "Atualizar painel de agendas" → **Run workflow** (botão manual). Acompanhe o log — se tudo estiver certo, ele gera/atualiza o `index.html` e faz commit sozinho. O GitHub Pages republica automaticamente.

## Alterar a frequência de atualização

Edite `.github/workflows/update.yml`, a linha `cron: "0 */6 * * *"` (sintaxe cron: minuto hora dia mês dia-da-semana). Exemplos:
- `"0 * * * *"` → a cada hora
- `"0 8,12,18 * * *"` → às 8h, 12h e 18h UTC (subtraia 3h para horário de Brasília)

## Ajustar etiquetas, cores ou ocultar algo

Edite `config/settings.json` (nomes/cores/ocultas) ou `config/event_overrides.json` (comentário/etiqueta de um compromisso específico, pela chave `origem__id-do-evento`). Na próxima execução do robô, a mudança já aparece.

## Se uma agenda parar de aparecer

O link secreto iCal pode ser regenerado manualmente no Google Calendar (o que invalida o antigo). Se isso acontecer sem querer, é só pegar o novo link e atualizar o segredo `ICAL_URLS_JSON` no GitHub.

## Solicitar atualização manual

O botão "Solicitar atualização" na página abre uma nova *issue* no repositório — não dispara o robô sozinho, é um aviso pra alguém rodar manualmente (Actions → Run workflow) ou esperar o próximo horário programado.
