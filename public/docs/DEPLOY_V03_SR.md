# Nadogradnja GarminAI Public v0.2 → v0.3 na Renderu

## 1) Napravi razvojni token LOKALNO
PowerShell: `python -c "import secrets,hashlib; t=secrets.token_urlsafe(48); print('TOKEN='+t); print('SHA256='+hashlib.sha256(t.encode()).hexdigest())"`
Ako nemaš Python na računaru, u PowerShell-u:
`$bytes=New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Fill($bytes); $token=[Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_'); $hash=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($token))).ToLower(); Write-Host "TOKEN=$token"; Write-Host "SHA256=$hash"`

Zapiši TOKEN u svoj password manager. NIKADA ga nemoj slati u chat, GitHub, issue ili screenshot. SHA256 je njegov otisak (i njega čuvaj izvan GitHub-a). Ako je procurio, odmah regeneriši oba.

## 2) PODESI Render pre GitHub commita
Render Dashboard → `garminai-public-demo` → Environment → Add Environment Variable.
Key: `GARMINAI_DEMO_TOKEN_SHA256`; Value: rezultat `SHA256=` (64 heksadecimalna znaka).
Sačuvaj i izaberi Save, deploy (ili Save, rebuild and deploy).

## 3) GitHub ažuriranje
- Zameni/unesi samo fajlove u `public/` iz ovog paketa na istim putanjama.
- Zameni `render.yaml` u korenu (postojeći Free plan ostaje).
- Ne briši `index.html`, `style.css`, `privacy.html`, `contact.html`.
- Ne menjaj niti prenosi privatnu GarminAI Windows aplikaciju, bazu, JSON, FIT ili ključeve.

## 4) Proveri
`https://garminai-public-demo.onrender.com/healthz` treba da vrati v0.3.0, DEMO_ONLY.
Otvaranje `/mcp` bez tokena treba da vrati JSON grešku `demo_access_denied` sa HTTP 401, NE otkriva alatke.
U MCP Inspector-u: GarminAI_Public → Edit / Settings → Custom Headers → `Authorization` = `Bearer TVOJ_TOKEN`; reconnect.
Inspector može drugačije nazivati polja u zavisnosti od verzije. TOKEN ne prikazuj na snimcima.
Povezivanje sa tokenom treba da ponovo vrati šest demo alatki.

## 5) Važno
Ovo je razvojna zaštita zajedničkim tajnim tokenom, ne OAuth i ne korisnička prijava. Nema stvarnih Garmin aktivnosti niti produkcione bezbednosti. Ne deliti token sa drugim trkačima.
