# OPERATORA ROKASGRĀMATA — WPNO LEVEL-1 AUDITS (R4)

Šī ir vienīgā rokasgrāmata, kas nepieciešama, lai palaistu Level-1 auditu.
Visas komandas ir paredzētas palaišanai no Level-1 mapes.

```text
LEVEL1_ROOT = ~/WPNO/08.18.26_Level1_Audits_R3
```

Ceļš rakstīts ar tildi ar nolūku: pakotne nekur neierakststa konkrētu lietotāja
vārdu. Trīs saknes (`PROJECT_ROOT`, `DISCOVERY_ROOT`, `LEVEL1_ROOT`) tiek
noteiktas izpildes laikā no `paths.json`.

---

## 0 · Kas notika pirms tam — un kāpēc šī ir R3

Iepriekšējā pakotne `~/WPNO/08.18.26_Level1_Audits` **neizturēja** neatkarīgu
Codex pirmsiesaldēšanas verifikāciju:

```text
VERIFICATION_FAIL — 11 atradumi, VF-001 līdz VF-011
```

Īsi, kas tur bija nepareizi:

| ID | kas nedarbojās |
| --- | --- |
| VF-001 | 188 paštestu komplektā: 4 neizdošanās, 2 kļūdas |
| VF-002 | simbolisko saišu aizsargs atrisināja ceļu, pirms to pārbaudīja — tāpēc neko neatrada |
| VF-003 | derīgs RUN-A konteksts tika noraidīts kā „izolācijas pārkāpums" |
| VF-004 | IBAN marķieris tika pārrakstīts ar BIC likumu: `[[REDACTED:BIC]:IBAN]` |
| VF-005 | tika pieņemta neiespējama fāžu secība (COMPARISON bez RUN-A) |
| VF-006 | L1-A31 teksts neizturēja paša komplekta prasību |
| VF-007 | D-08 apgalvojums par bytecode kešatmiņu bija faktiski nepareizs |
| VF-008 | git bāzlīnija tika aprakstīta kā „pirms izveides", lai gan tā tāda nebija |
| VF-009 | būve importēja ģenerētu kodu, ko paši noteikumi aizliedza |
| VF-010 | paštestu rakstīšanas topoloģija bija pretrunā ar verifikācijas robežu |
| VF-011 | L1-A24 prasīja mapi, kas vienlaikus atrodas divās izslēdzošās vietās |

**Vecā pakotne netika mainīta.** Tā ir pierādījums par neveiksmi un paliek
neskarta. R2 bija jauna, neatkarīga pakotne, kas šos vienpadsmit punktus laboja.

### Kāpēc pēc R2 vajadzēja R3

Arī R2 **neizturēja** neatkarīgu Codex pirmsiesaldēšanas verifikāciju:

```text
VERIFICATION_FAIL — 2 atlikušie bloķētāji
```

| ID | kas nedarbojās |
| --- | --- |
| PV-001 | `00_BUILD_STATUS.md` neietvēra būves laika Git HEAD, lai gan HEAD sakrita ar pierādījumu failu |
| PV-002 | viens no 256 paštestiem neizdevās: `TestUnicodeNormalization.test_nfc_and_nfd_agree` — abas Unicode virknes bija identiskas, jo saliktais simbols bija ierakstīts tieši pirmkodā |

Deviņi no vienpadsmit R2 labojumiem (VF-002 līdz VF-011) tika atzīti par
atrisinātiem. R3 tos saglabā **nemainītus** un labo tikai šos divus bloķētājus.

**R2 pakotne netika mainīta.** Arī tā ir pierādījums un paliek neskarta.
Abas neveiksmīgās pakotnes — R1 un R2 — ir tikai lasāmas.

R3 **neapgalvo**, ka labojumi ir apstiprināti. To nosaka Codex verifikācija.

---

## 1 · Ko Claude Code izveidoja

Pilnu Level-1 audita paketi, un neko citu:

| kas | kur | daudzums |
| --- | --- | --- |
| audita specifikācijas (prompti) | `prompts/L1-A01.md` … `L1-A35.md` | 35 |
| mērķa saistījumi (bindings) | `bindings/L1-A01.binding.json` … | 35 |
| audita reģistrs | `audit_registry.json` | 1 |
| kopīgie noteikumi | `00_COMMON_RULES.md` | 1 |
| aģentu noteikumi | `AGENTS.md` | 1 |
| Discovery saskaņošana | `discovery_reconciliation/` | 13 + manifests |
| kontroliera pirmkods | `automation/` | 13 moduļi |
| JSON shēmas | `automation/schemas/` | 8 |
| kontroliera paštesti | `automation/tests/` | 11 testu faili |
| būves pierādījumi | `build_evidence/` | git status un hash bāzlīnijas |
| Codex prompti | `00_…`, `01_…`, `02_…`, `03_…` | 4 |
| būves manifests | `BUILD_MANIFEST.sha256` | 1 |
| šī rokasgrāmata | `00_OPERATOR_RUNBOOK_LV.md` | 1 |

Precīzs failu skaits katrā kategorijā ir `00_BUILD_STATUS.md`. Skaitļi tur ir
izmērīti būves beigās, nevis pieņemti.

Pakotnes stāvoklis šobrīd:

```text
MODE=GENERATED_UNVERIFIED
```

---

## 2 · Ko Claude Code **nedarīja**

Tas ir tikpat svarīgi kā tas, ko tas izdarīja:

```text
Kontroliera paštesti palaisti:  0
WPNO testi palaisti:            0
Level-1 auditi palaisti:        0
Level-2 auditi palaisti:        0
Ģenerēts kods izpildīts:        NĒ
Ģenerēts validators importēts:  NĒ
Ģeneratora skripti izveidoti:   NĒ
Projekta faili mainīti:         NĒ
Discovery faili mainīti:        NĒ
Vecā pakotne mainīta:           NĒ
Tīkls izmantots:                NĒ
Docker izmantots:               NĒ
Datubāze izmantota:             NĒ
```

Neviens WPNO Python fails netika importēts vai palaists. Neviens šīs pakotnes
modulis netika importēts vai palaists. Nav mapes `build_tmp/` un nav neviena
ģeneratora skripta — iepriekšējā pakotne tos izmantoja, un tieši tas kļuva par
atradumu VF-009.

**Kāpēc paštesti nav palaisti:** lomu sadalījums ir apzināts. Claude Code
ģenerē. Codex verificē. Ja tas pats, kurš uzrakstīja kontrolieri, arī
apstiprinātu, ka tas ir pareizs, pārbaudes vērtība būtu nulle.

---

## 3 · Kur viss atrodas

```text
~/WPNO/08.18.26_Level1_Audits_R3/
├── BUILD_ID · BUILD_STATE.json · BUILD_JOURNAL.jsonl · MODE
├── 00_BUILD_STATUS.md              ← būves rezultāts, skaitļi
├── 00_COMMON_RULES.md              ← noteikumi katram auditam
├── 00_OPERATOR_RUNBOOK_LV.md       ← šis fails
├── 00_CODEX_VERIFY_LEVEL1_PACKAGE.md   ← PIRMAIS Codex prompts
├── 01_CODEX_RUN_LEVEL1.md              ← OTRAIS, pēc iesaldēšanas
├── 02_CODEX_CONSOLIDATE_LEVEL1.md      ← pēc visiem 35
├── 03_CODEX_LEVEL2_ADVERSARIAL.md      ← visbeidzot
├── AGENTS.md · audit_registry.json · paths.json · BUILD_MANIFEST.sha256
├── build_evidence/                 ← git status un hash bāzlīnijas (sākums/beigas)
├── discovery_reconciliation/       ← ko īsti atrada uz šīs mašīnas
├── bindings/ · prompts/            ← 35 + 35
├── automation/                     ← kontrolieris, shēmas, paštesti
├── references/                     ← ŠEIT jūs ievietojat ārējo materiālu
└── verification/ · state/ · results/ · evidence/ · work/ · logs/
```

---

## 4 · Kā palaist Codex

Vienmēr no Level-1 mapes:

```bash
cd ~/WPNO/08.18.26_Level1_Audits_R3
```

Nekad no `~/WPNO` un nekad no mājas mapes. Darba mape nosaka, ko Codex redz un
kur tas raksta.

---

## 5 · Kā iestatīt šauras atļaujas

Pirms Codex palaišanas pārliecinieties:

| iestatījums | vērtība | kāpēc |
| --- | --- | --- |
| pilnas piekļuves režīms | **IZSLĒGTS** | verifikācija ar lielākām tiesībām nekā pati sistēma neko nepierāda |
| automātisks apstiprinājums | **IZSLĒGTS** | apstiprinājumu dod cilvēks, ne modelis |
| tīkls | **IZSLĒGTS** | Level-1 strādā offline; trūkstošs avots = `BLOCKED` |
| rakstīšanas tiesības | tikai `08.18.26_Level1_Audits_R3/` | `~/WPNO`, Discovery un abas vecās pakotnes (R1, R2) ir tikai lasāmas |

Ja kāds no tiem nav pareizi iestatīts, pirmais Codex prompts atteiksies sākt.
Tas ir paredzēts.

---

## 6 · Kuru promptu izmantot pirmo

```text
00_CODEX_VERIFY_LEVEL1_PACKAGE.md
```

Tas pārbauda pakotni: manifestus, 35 promptus, 35 saistījumus, reģistru,
izpildes secību, replikācijas, kontroliera paštestus (izolētā kopijā),
bīstamos kodu paraugus, apstiprinājumu neatkārtojamību, ceļu aizsardzību,
RUN-B izolāciju, pierādījumu aizzīmogošanu, avotu hash saskaņošanu un
Discovery novirzi. Tas atsevišķi ziņo, vai VF-001 līdz VF-011 ir novērsti.

Tas **neiesaldē** pakotni pats. Tas apstājas un pieprasa no jums žetonu:

```text
FREEZE-LEVEL1 PACKAGE-SHA256=<64_HEX> VERIFICATION-SHA256=<64_HEX> RUN-ONCE
```

Abus hash izdrukā pats prompts. Kad esat tos pārbaudījis un ievadījis žetonu
**jaunā gājienā**, Codex izveido `CONTROL_MANIFEST.sha256`,
`BASELINE_MANIFEST.json`, `state/PACKAGE_VERIFIED.json` un uzstāda
`MODE=FROZEN` — un tad atkal apstājas.

Ja kaut kas neizdodas, žetons netiek pieprasīts vispār un `MODE` paliek
`GENERATED_UNVERIFIED`. Tā tas notika ar iepriekšējo pakotni.

---

## 7 · Kuru promptu izmantot pēc verifikācijas

```text
01_CODEX_RUN_LEVEL1.md
```

Tas atsakās sākt, ja nav izpildīts viss šis:

```text
MODE=FROZEN
CONTROL_MANIFEST=VALID
BASELINE_MANIFEST=VALID
PACKAGE_VERIFIED=VALID
```

---

## 8 · Kā darbojas apstiprinājuma žetoni

Katrai izpildei nepieciešams **precīzs** žetons, ko ievadāt jūs:

```text
APPROVE-EXECUTION L1-Axx RUN=<RUN-PHASE> PLAN-SHA256=<64_HEX> TARGET-SHA256=<64_HEX> RUN-ONCE
```

Tieši **seši** lauki, atdalīti ar vienu atstarpi. Audita numurs ir bez prefiksa.
Ne `AUDIT=L1-Axx`, ne `APPROVE-L1-Axx` nav derīgs žetons — abi tiek noraidīti,
un noraidīts žetons neko nemaina.

### 8.1 · Vispirms jāsasniedz vārti, tikai pēc tam tos var atvērt (R4)

Šeit R3 apstājās. Plāna fails **nav** kontroliera stāvoklis. Apstiprinājumu var
ierakstīt tikai tad, kad fāze tiešām atrodas stāvoklī `AWAITING_APPROVAL`:

```text
NOT_STARTED -> PLANNING -> PLAN_READY -> AWAITING_APPROVAL -> APPROVED
                                                 ^
                                 record-approval veic tikai šo soli
```

R3 nebija nevienas publiskas komandas, kas veiktu pirmos trīs soļus. Pareizs,
pareizi saistīts žetons tika noraidīts ar `invalid transition NOT_STARTED -> …`,
un audits nevarēja sākties. R4 pievieno tieši vienu komandu, kas šo trūkumu
novērš:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONNOUSERSITE=1 \
PYTHONPATH="$LEVEL1_ROOT" \
/usr/bin/python3 -m automation.controller prepare-execution \
  --audit-id L1-A31 \
  --run-phase RUN-A \
  --plan-path "$LEVEL1_ROOT/results/L1-A31/RUN-A/plan.json" \
  --target-path "$LEVEL1_ROOT/references/REF-11-original-mail-attachment.zip"
```

Pilnā secība:

1. izveido un noslēdz plānu `results/<AUDIT>/<PHASE>/plan.json`;
2. `controller prepare-execution`;
3. kontrolieris sasniedz `AWAITING_APPROVAL`;
4. kontrolieris izdrukā precīzo sešu lauku žetonu;
5. jūs ievadāt tieši šo žetonu;
6. `controller record-approval`;
7. kontrolieris sasniedz `APPROVED`;
8. `controller execute-approved`;
9. kontrolieris sasniedz `EXECUTING` un pēc tam gala stāvokli.

Seši noteikumi, kas no tā izriet:

- **Plāna fails `work/` mapē nav kontroliera stāvoklis.**
- **Apstiprinājumu nevar ierakstīt no `NOT_STARTED`.**
- **Stāvokļa failus nekad nedrīkst labot ar roku** — ne reizi, ne lai atbloķētu.
- **Pareizs žetons nelabo nesagatavotu stāvokli.** Atbilde ir
  `prepare-execution`, nevis cits žetons.
- **`prepare-execution` neapstiprina un neizpilda.**
- **`record-approval` neizpilda.**

`prepare-execution` ir droši atkārtojama. Ar tiem pašiem argumentiem tā turpina
no vietas, kur apstājās, neatkārtojot jau veiktu pāreju. Ar citu plānu vai citu
mērķi tā atsakās ar `PREPARATION_BINDING_MISMATCH`.

### 8.1a · Iesaldēšanas žetons (R4) ir saistīts ar iesaldēšanas plānu

R3 iesaldēšanas žetonam bija četri lauki un tas nesaturēja neko, kas identificē
konkrēto mēģinājumu. Kad pirmais R4 iesaldēšanas mēģinājums tika atsaukts
artefakta defekta dēļ — pati pakotne nemainījās —, otrajam mēģinājumam
nepieciešamais žetons būtu bijis burtiski identisks jau izlietotajam. `RUN-ONCE`
žetons, ko nevar atšķirt no tā paša žetona atkārtotas izmantošanas, nav
vienreizējs.

R4 žetonam ir **pieci** lauki:

```text
FREEZE-LEVEL1 PACKAGE-SHA256=<64hex> VERIFICATION-SHA256=<64hex> FREEZE-PLAN-SHA256=<64hex> RUN-ONCE
```

`FREEZE-PLAN-SHA256` ir `build/FREEZE_PLAN_V2.json` hash. Plāns satur
mēģinājuma numuru, gaidāmos hash, iepriekšējā mēģinājuma pierādījumu hash un
gaidāmā baseline priekšskatījuma hash. Divi mēģinājumi nekad nevar dalīties ar
vienu plāna hash, tātad arī ar vienu žetonu.

Vecais R3 četru lauku žetons R4 tiek noraidīts jau pēc formas.

### 8.2 · Kāpēc kļūdas ziņojumā parādās `[REDACTED:BIC]`

Kontroliera kļūdu teksts iziet cauri konfidencialitātes filtram. Tā bankas
identifikatora paraugs atbilst jebkuram astoņu lielo burtu vārdam, tāpēc
`APPROVED` un `PLANNING` ziņojumā tiek aizstāti ar `[REDACTED:BIC]`. Piemēram:

```text
invalid transition NOT_STARTED -> [REDACTED:BIC]     nozīmē      NOT_STARTED -> APPROVED
state is [REDACTED:BIC]                              nozīmē      state is APPROVED vai PLANNING
```

Tas ir kosmētisks defekts kļūdu izdrukā, nevis kontroles kļūda. R4 filtru
**apzināti nemaina** — tā ir konfidencialitātes kontrole, un tās maiņa nebija
šīs revīzijas uzdevums. Precīzu stāvokli vienmēr var nolasīt ar:

```bash
/usr/bin/python3 -m automation.controller status
```

Tas ir reģistrēts kā atklāts jautājums `R4_CHANGE_SCOPE.md` sadaļā
„Observed and deliberately not remediated".

- **audit-bound** — derīgs tikai tam auditam;
- **run-bound** — tikai tai fāzei (`RUN-A`, `RUN-B` vai `COMPARISON`);
- **plan-bound** — tikai tam plānam; ja plāns mainās, žetons zaudē spēku;
- **target-bound** — tikai tam mērķa hash; ja fails mainās, žetons zaudē spēku;
- **vienreizējs** — `RUN-ONCE`, atkārtota izmantošana tiek noraidīta;
- **ierakstīts** — katrs apstiprinājums tiek saglabāts.

Kontrolieris **nekad** neģenerē žetonu pats. Nav `--auto-approve`, nav `--yes`,
nav apiešanas. Ja jums šķiet, ka tāda vajadzētu būt — tas ir tieši tas gadījums,
kuram šī sistēma tika uzbūvēta.

Ievadiet žetonu tikai tad, kad esat izlasījis izdrukāto plānu un abus hash.
Žetona ievadīšana, to nepārbaudot, atceļ visu šo mehānismu.

**L1-A24 papildus:** pirms izpildes jums jāapstiprina un plānā jāieraksta
ārējā darba mape (ārpus `PROJECT_ROOT`), no kuras tests tiks palaists. Tajā
mapē netiek rakstīts nekas; tā tiek hashota pirms un pēc. Bez šīs saistīšanas
audits ir `BLOCKED`.

---

## 9 · Kāpēc vienlaikus notiek tikai viena audita fāze

Katrs Codex izsaukums veic tieši vienu no: **PLAN**, **EXECUTE**, **REVIEW** —
un tad apstājas.

Iemesli:

1. **Konteksta piesārņojums.** Divi auditi vienā sesijā sāk dalīties ar
   pieņēmumiem. Otrais audits „zina", ko atrada pirmais, un vairs nav
   neatkarīgs.
2. **Plānotājs un recenzents ir atsevišķi.** Plānotājs neveido spriedumu.
   Recenzents nesaņem to, ko plānotājs gaidīja. Ja abi būtu vienā sesijā, otrais
   viedoklis būtu pirmā atbalss.
3. **Apstiprinājums ir starp fāzēm.** Ja izpilde turpinātos automātiski,
   apstiprinājums būtu formalitāte.
4. **Pierādījumu aizzīmogošana.** Fāze tiek noslēgta un aizzīmogota pirms
   nākamās sākuma.

---

## 10 · Kā atsākt

Palaidiet `01_CODEX_RUN_LEVEL1.md` jaunā Codex sesijā. Tas nolasa `state/` un
turpina no turienes.

- Nepārtaisiet aizzīmogotu fāzi.
- Nemēģiniet „ātri pārbaudīt" pabeigtu auditu — atkārtots lauks rada otru
  ierakstu par to pašu jautājumu un nav veida, kā noteikt, kurš ir spēkā.
- Nemainiet failus `state/` mapē ar roku.

---

## 11 · Ko darīt, ja rezultāts ir BLOCKED

`BLOCKED` ir **pilnvērtīgs un pareizs** rezultāts. Tas nozīmē: audits tika
specificēts pilnībā, bet nebija materiāla, ar ko to izpildīt.

Šobrīd **vienpadsmit** auditi ir gaidāmi kā `BLOCKED`:

```text
L1-A11   trūkst oficiāla BGH saraksta
L1-A14   trūkst reālā 43 citātu dokumenta
L1-A27   trūkst ZIP arhīva
L1-A28   trūkst parakstītā satura
L1-A29   nav definēts, uz ko attiecas „376"
L1-A30   trūkst arhīva
L1-A31   trūkst sertifikātu un uzticības enkura
L1-A32   trūkst CMS objekta
L1-A33   trūkst OSCI konteinera un 563203462.xml
L1-A34   trūkst vhn.xml.p7s
L1-A35   trūkst 17.08. avota un mērķa kopiju
```

Rīcība:

1. Atveriet `references/README_REQUIRED_OFFLINE_REFERENCES_LV.md`.
2. Atrodiet attiecīgo `REF-xx` ierakstu.
3. Ievietojiet failu `references/` mapē.
4. Ierakstiet to `references/manifest.json` kopā ar SHA-256 **pirms**
   lietošanas.
5. Palaidiet attiecīgo auditu no jauna.

**Svarīgi:** neviens no šiem materiāliem nav vajadzīgs, lai pakotni verificētu
un iesaldētu. To trūkums nav pakotnes defekts.

**Nekādā gadījumā** neļaujiet Codex lejupielādēt materiālu. Tīkls ir izslēgts ar
nolūku, un modeļa atmiņa nav avots.

---

## 12 · Ko darīt, ja rezultāts ir CRITICAL

Kritisks atradums aptur visu secību:

```text
HALT_CRITICAL
```

Nākamais audits nesākas, kamēr jūs neievadāt:

```text
ACKNOWLEDGE-CRITICAL L1-Axx FINDING-ID=<ID>
```

**Svarīgi:** apliecinājums nozīmē tikai to, ka cilvēks to redzēja. Tas **nav**
labojums. Tas nemaina atradumu, nemaina spriedumu un neko neslēdz.

Un: **Level-1 laikā sistēma netiek labota.** Ja redzat, kā to salabot, ierakstiet
to atradumā un atstājiet sistēmu tādu, kāda tā ir. Salabots defekts vairs nav
izmērāms.

---

## 13 · Kad izmantot konsolidāciju

```text
02_CODEX_CONSOLIDATE_LEVEL1.md
```

Tikai tad, kad **visiem 35** auditiem ir termināls statuss (`SEALED`,
`BLOCKED`, `ERROR` vai `CONTAMINATED`) — ieskaitot `RUN-A`, `RUN-B` un
`COMPARISON` četriem replicētajiem auditiem.

Tas pārbauda manifestus, uzskaita spriedumus, meklē pretrunas starp auditiem,
grupē atkārtotus atradumus un skaidri norāda, kas **netika** pārbaudīts.

Tas nelabo un nemaina spriedumus. Sprieduma maiņa ir atsevišķs labojums
(amendment) ar savu ID.

---

## 14 · Kad izmantot Level-2

```text
03_CODEX_LEVEL2_ADVERSARIAL.md
```

Tikai pēc tam, kad konsolidētais ziņojums ir aizzīmogots.

Level-2 mērķis:

```text
Mēģināt pierādīt, ka sistēma joprojām var neizdoties, pat ja atsevišķie
Level-1 auditi tika izturēti.
```

Level-1 ir 35 punktveida pārbaudes. Ķēde plīst savienojumos, un punktveida
pārbaude savienojumos neskatās. Uz šīs mašīnas **pieci no deviņiem** apstrādes
ķēdes posmiem Level-1 nav pārbaudīti vispār.

---

## 15 · Ko nekad nedrīkst darīt

| nekad | kāpēc |
| --- | --- |
| palaist `git clean -fd` mapē `~/WPNO` | tas dzēstu šo pakotni, veco pakotni un `08.18.26_Discovery` — visas trīs ir untracked. Tas ir arī tieši tas, ko pārbauda `L1-A25` |
| mainīt kaut ko vecajā pakotnē `08.18.26_Level1_Audits` | tā ir pierādījums par neveiksmīgu verifikāciju un ir nemainīga |
| labot sistēmu Level-1 laikā | salabots defekts vairs nav izmērāms |
| rediģēt failus mapē `state/` ar roku | kontrolieris pārvalda stāvokli; roku labojumi rada stāvokli, kāds nekad nav bijis paredzēts |
| rediģēt aizzīmogotus pierādījumus | labojums ir amendment ar savu ID |
| ievadīt apstiprinājuma žetonu, nepārbaudot plānu | tas atceļ visu apstiprinājuma mehānismu |
| atļaut Codex tīkla piekļuvi | trūkstošs avots ir `BLOCKED`, nevis iemesls meklēt internetā |
| lejupielādēt atsauces automātiski | avota izcelsme ir daļa no pierādījuma |
| ielikt reālus klienta datus testa fiksācijās | visas šīs pakotnes fiksācijas ir sintētiskas |
| palaist `pytest` mapē `~/WPNO` | tas izveidotu `__pycache__` un `.pytest_cache` tikai lasāmā saknē |
| pieņemt „zaļu" testu par pierādījumu | tests ar nulli savāktiem testiem un iziešanas kodu 0 nav pierādījums — tas ir tieši tas defekts, ko meklē `L1-A15` un `L1-A22` |
| mainīt `MODE` ar roku | to dara tikai Codex verifikācija ar derīgu iesaldēšanas žetonu |
| pievienot 36. Level-1 promptu | sistēmas mēroga nepilnības pieder Level-2 |

---

## 16 · Īss darbību kopsavilkums

```bash
cd ~/WPNO/08.18.26_Level1_Audits_R3
```

1. Codex + `00_CODEX_VERIFY_LEVEL1_PACKAGE.md` → verifikācija → apstājas
2. Jūs pārbaudāt abus hash → ievadāt `FREEZE-LEVEL1 …` → `MODE=FROZEN` → apstājas
3. Codex + `01_CODEX_RUN_LEVEL1.md` → plāns → apstājas
4. Jūs izlasāt plānu → ievadāt `APPROVE-EXECUTION …` → izpilde → apstājas
5. Recenzents → spriedums → aizzīmogošana → apstājas
6. Atkārtojiet 3–5 visām fāzēm, fiksētajā secībā
7. Codex + `02_CODEX_CONSOLIDATE_LEVEL1.md`
8. Codex + `03_CODEX_LEVEL2_ADVERSARIAL.md`

Katrā solī sistēma apstājas un gaida jūs. Tas nav trūkums — tas ir vienīgais
iemesls, kāpēc rezultātam var uzticēties.
