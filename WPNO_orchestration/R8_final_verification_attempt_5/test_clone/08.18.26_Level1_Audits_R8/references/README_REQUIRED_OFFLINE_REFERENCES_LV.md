# NEPIECIEŠAMĀS ĀRĒJĀS ATSAUCES (offline)

Šī mape ir vienīgā vieta, kur operators ievieto ārējo materiālu Level-1 auditam.

**Neviens fails šeit netiek lejupielādēts automātiski.** Level-1 strādā bez
tīkla. Ja auditam trūkst atsauces, tas apstājas ar `BLOCKED` un to pasaka. Tas
neaizstāj trūkstošo avotu ar modeļa zināšanām.

**Neviens no šiem materiāliem nav vajadzīgs, lai pakotni pārbaudītu un
iesaldētu.** Ārējās atsauces nav daļa no nemainīgā vadības slāņa. To trūkums
padara atsevišķus auditus par `BLOCKED` vai `UNVERIFIED` tad, kad tie tiks
palaisti — bet tas nebloķē verifikāciju un nav pakotnes defekts.

## Kā ievietot materiālu

1. Nokopējiet failu šajā mapē (`references/`).
2. Nokopējiet `manifest.template.json` uz `manifest.json`.
3. Ierakstiet katram failam: `ref_id`, `file`, `sha256`, `source`,
   `version_or_date`, `format`, `chain_of_custody`.
4. SHA-256 jāieraksta **pirms** faila izmantošanas auditā un neatkarīgi
   jāpārrēķina saņemšanas brīdī.

Bez ieraksta manifestā fails netiek izmantots. Neapstiprināts fails nav
pierādījums. Trūkstošs, tukšs vai neatbilstošs hash padara failu
nelietojamu.

## Saraksts

| id | audits | kas nepieciešams | pieņemams avots | datums / versija | formāts | ja trūkst |
| --- | --- | --- | --- | --- | --- | --- |
| REF-01 | L1-A18 | IBAN specifikācija un valstu reģistrs (ISO 13616) | SWIFT kā reģistrācijas iestāde; vai līdzvērtīga oficiāla nacionāla publikācija | audita brīdī spēkā esošā redakcija — jāieraksta | PDF / TXT | BLOCKED |
| REF-02 | L1-A18 | Neatkarīgi derīgu un nederīgu IBAN testa vektori vismaz 6 valstīm | oficiālā reģistra piemēri vai neatkarīgas standarta implementācijas testu kopa (offline) | jebkurš | TXT / CSV | BLOCKED |
| REF-03 | L1-A19 | Oficiālā ISO 7064 formula tieši tai shēmai, kas identificēta | ISO 7064 + identifikatoru izdevējiestādes specifikācija (vācu steuerliche Identifikationsnummer gadījumā: Bundeszentralamt für Steuern) | pašreizējā | PDF | BLOCKED_SCHEME_IDENTITY_UNCERTAIN |
| REF-04 | L1-A19 | Neatkarīgi kontrolcipara testa vektori tai pašai shēmai | oficiālās specifikācijas piemēri vai neatkarīga implementācija | jebkurš | TXT / CSV | BLOCKED |
| REF-05 | L1-A11 | Oficiāls BGH sastāva saraksts par pārbaudāmo periodu | Bundesgerichtshof oficiālā publikācija | jāaptver reģistrā deklarētais periods | PDF / HTML (saglabāts offline) | BLOCKED_MISSING_OFFICIAL_REFERENCE |
| REF-06 | L1-A14 | Atgūtais sākotnējais pārbaudītāja DOCX: SHA-256 `9f7ee8caebee9345b54dd535a2681789512f68dfc2e4bf7b0652c5cc48722675`, Word saglabātais lapu skaits 111, 165 citātu gadījumi un 64 unikāli citāti pēc nemainītā noteikuma; 82/43 ir `SUPERSEDED_UNSUPPORTED_EXPECTATION` | operators, no lietas materiāliem; trīs kopijas ir baitu ziņā identiskas | tieši atgūtais S01 ievades fails, identisks AFNA augšupielādētajam avotam | DOCX | BLOCKED |
| REF-07 | L1-A12 | Reāls rakstu korpuss ar neatkarīgām atzīmēm | operatora izvēlēti reāli dokumenti; atzīmes **nedrīkst** būt no pārbaudāmā rīka | jebkurš | mape + atzīmju fails | UNVERIFIED |
| REF-08 | L1-A31, L1-A34 | Uzticības enkura sertifikāts(-i) | izdevēja CA vai oficiālais beA/OSCI uzticības saraksts | derīgs paraksta apgalvotajā laikā | PEM / DER | UNVERIFIED_TRUST_CHAIN |
| REF-09 | L1-A31, L1-A32, L1-A34 | Starpniek­sertifikāti | kā REF-08 | kā REF-08 | PEM / DER | UNVERIFIED_TRUST_CHAIN |
| REF-10 | L1-A31 | CRL vai OCSP pierādījums | CA, saglabāts offline | pēc iespējas tuvāk validācijas laikam | CRL / DER vai OCSP atbilde | atsaukšana tiek ziņota kā `NOT_ASSESSED_OFFLINE` — **nekad** kā „nav atsaukts" |
| REF-11 | L1-A27, A28, A30, A32, A33, A34, A35 | Oriģinālie beA/OSCI artefakti: ZIP arhīvs, `563203462.xml`, `vhn.xml.p7s`, parakstītais saturs, kā arī 17.08. avota un mērķa kopijas | operators, no oriģinālajiem lietas materiāliem, ar dokumentētu glabāšanas ķēdi | oriģināli, nevis atkārtoti eksporti | neapstrādāti baiti, nemainīti | BLOCKED |
| REF-12 | L1-A29 | Definīcija, uz ko attiecas „376", kopā ar pašu artefaktu | operators | — | rakstisks paskaidrojums + artefakts | BLOCKED_376_TARGET_UNIDENTIFIED |
| REF-13 | L1-A21 | Docker metadatu eksports: image ID, digest, image un konteinera izveides laiki, mounts, entrypoint, command, build-context pierādījumi | `docker inspect` izvade, ko sagatavo **operators**, ārpus audita | audita brīdī | JSON | UNVERIFIED_DOCKER_PRODUCTIVE_COPY |
| REF-14 | L1-A17, L1-A23 | Produkcijas konfigurācijas eksports (rediģēts), kur statiskie faili nav pietiekami | operators | audita brīdī | JSON / TXT | UNVERIFIED |

## Noteikumi, kas attiecas uz katru ierakstu

1. **Nekādas automātiskas lejupielādes.** Tīkls Level-1 laikā ir izslēgts.
2. **Hash uzreiz.** SHA-256 tiek ierakstīts `manifest.json` pirms lietošanas un
   pēc tam nonāk audita pierādījumos. Mapei vai korpusam: katram failam savs
   hash, un sakārtotajam sarakstam — kopējais hash.
3. **Neatkarīgs orākuls nedrīkst nākt no pārbaudāmās sistēmas.**
   `BGH_REGISTER` salīdzināšana ar `bgh_referenz.json` **nav** neatkarīgs
   orākuls — abi ir projekta artefakti. `payload_scan.py` izmantošana gaidāmo
   IBAN rezultātu ģenerēšanai **nav** orākuls — tā ir mērāmā lieta.
4. **REF-06 un REF-11 ir klienta materiāls.** Uz tiem attiecas profesionālais
   konfidencialitātes pienākums. Tos lasa audita ietvaros, bet to **saturs**
   nenonāk ziņojumā — tikai hash, skaitļi, strukturāli fakti un rediģēti
   norādes punkti. Rediģēšanu nodrošina `automation/redaction.py`.
5. **Iesniegtais materiāls nav iekļauts `BUILD_MANIFEST.sha256`.** Tā ir
   operatora ievade, kas tiek pievienota pēc būves, tāpēc tās „iesaldēšana"
   būves brīdī būtu nepatiesa. Tai ir savs `manifest.json`. Vienīgie divi
   `references/` faili, kas ietilpst nemainīgajā vadības slānī, ir šis fails un
   `manifest.template.json`.
6. **Trūkstošais nekad netiek ierakstīts kā esošs.** Nepiegādāts materiāls tiek
   ierakstīts kā trūkstošs kopā ar sekām, un audits, kam tas vajadzīgs, atgriež
   `BLOCKED` vai `UNVERIFIED`.

## Kas notiek, ja materiāla nav

Šobrīd **vienpadsmit** auditi (L1-A11, L1-A14 un L1-A27 līdz L1-A35) nevar sākties
bez šeit uzskaitītā materiāla. Tas nav trūkums specifikācijā — visi vienpadsmit
ir pilnībā specificēti. Tie ir bloķēti materiāla dēļ.

Meklēšana visos astoņos Discovery skenēšanas saknes katalogos (6295 faili)
neatrada nevienu no `p7s`, `vhn`, `563203462`, `osci`, `pkcs7`. Pārējā Mac daļa
netika pārmeklēta — tas bija apzināts būves ierobežojums. Tāpēc pareizais
formulējums ir „nav audita tvērumā", nevis „neeksistē".
