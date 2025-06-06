from flask import Flask, request, render_template_string
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import math
import re

# .env laden (falls vorhanden)
load_dotenv()

# OpenAI-Client initialisieren
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# Minimaler HTML-Code mit horizontalem Layout
html_template = """
<!doctype html>
<html>
<head>
  <title>Sitzverteilung BW 2026</title>
  <style>
    body {
      display: flex;
      justify-content: center;
      align-items: flex-start;
      flex-direction: column;
      min-height: 100vh;
      font-family: Arial, sans-serif;
      text-align: center;
      padding-top: 30px;
    }
    .container {
      display: flex;
      justify-content: center;
      align-items: flex-start;
      gap: 50px;
      margin-top: 20px;
    }
    form {
      width: 280px;
      text-align: left;
    }
    form input[type="number"] {
      width: 100%;
      padding: 5px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    table, th, td {
      border: 1px solid #444;
    }
    th, td {
      padding: 8px 12px;
    }
    .result-box {
      width: 340px;
      text-align: left;
    }
  </style>
</head>
<body>
  <h2>Schätzung der Sitzverteilung im Landtag von Baden-Württemberg<br>aufgrund Prognosen zur Landtagswahl 2026</h2>

  <div class="container">
    <form method="post" action="/prognose">
      {% for party in ["CDU", "B90/Grüne", "AfD", "SPD", "Die Linke", "FDP", "BSW", "Sonstige"] %}
        <label>{{party}} (%):</label><br>
        <input name="{{party}}" type="number" min="0" max="100" required><br><br>
      {% endfor %}
      <input type="submit" value="Absenden">
    </form>

    {% if result %}
      <div class="result-box">
        <h3>Ergebnis:</h3>
        <table>
          <tr>
            <th>Partei</th>
            <th>Sitze</th>
          </tr>
          {% for party, sitze in result.items() if party != "Hinweis" %}
          <tr>
            <td>{{ party }}</td>
            <td>{{ sitze }}</td>
          </tr>
          {% endfor %}
        </table>
        <p><strong>Hinweis:</strong> {{ result['Hinweis'] }}</p>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""


# system_prompt
system_prompt = """
Du bist ein Prognosetool zur Schätzung der Direktmandate bei der Landtagswahl Baden-Württemberg 2026. Grundlage ist eine Wahlprognose mit Zweitstimmenanteilen in Prozent.

Aufgabe:
Schätze, wie viele der 70 Direktmandate (Mehrheitswahl) jede Partei in den 70 Wahlkreisen von Baden-Württemberg gewinnt. Gehe vereinfachend davon aus, dass Erst- und Zweitstimmen gleich verteilt sind.

Datenbasis:
Nutze typische regionale Muster der Bundestagswahl 2025. 
Die folgende Tabelle enthält die Bundestagswahlzweitstimmenverteilung in den 37 Bundestagswahlkreisen in BW (in Dezimalwerten):

Wahlkreis,CDU,B90/Grüne,AfD,SPD,Die Linke,FDP,BSW,Sonstige
Baden-Württemberg,0.32,0.14,0.2,0.14,0.07,0.06,0.04,0.04
Stuttgart I,0.26,0.25,0.09,0.15,0.11,0.07,0.03,0.03
Stuttgart II,0.27,0.17,0.14,0.16,0.11,0.06,0.05,0.04
Böblingen,0.33,0.14,0.18,0.14,0.06,0.07,0.04,0.04
Esslingen,0.33,0.15,0.16,0.16,0.07,0.06,0.04,0.04
Nürtingen,0.34,0.14,0.18,0.14,0.06,0.07,0.04,0.04
Göppingen,0.33,0.09,0.23,0.14,0.05,0.06,0.04,0.04
Waiblingen,0.33,0.13,0.19,0.15,0.06,0.07,0.04,0.04
Ludwigsburg,0.32,0.15,0.17,0.15,0.07,0.06,0.04,0.04
Neckar-Zaber,0.33,0.12,0.2,0.14,0.05,0.06,0.04,0.05
Heilbronn,0.29,0.09,0.25,0.14,0.06,0.06,0.04,0.05
Schwäbisch Hall - Hohenlohe,0.32,0.1,0.25,0.13,0.05,0.06,0.04,0.05
Backnang - Schwäisch Gmünd,0.33,0.11,0.23,0.14,0.06,0.05,0.04,0.04
Aalen - Heidenheim,0.35,0.09,0.23,0.14,0.05,0.05,0.04,0.04
Karlsruhe-Stadt,0.22,0.24,0.14,0.16,0.11,0.05,0.04,0.04
Karlsruhe-Land,0.33,0.13,0.19,0.15,0.06,0.06,0.04,0.04
Rastatt,0.33,0.11,0.23,0.14,0.05,0.05,0.04,0.04
Heidelberg,0.26,0.22,0.12,0.17,0.1,0.06,0.03,0.04
Mannheim,0.23,0.16,0.18,0.18,0.11,0.05,0.05,0.04
Odenwald - Tauber,0.36,0.08,0.24,0.13,0.05,0.05,0.04,0.05
Rhein-Neckar,0.31,0.12,0.21,0.16,0.06,0.06,0.04,0.04
Bruchsal - Schwetzingen,0.32,0.11,0.22,0.14,0.06,0.05,0.04,0.05
Pforzheim,0.3,0.11,0.25,0.13,0.05,0.06,0.04,0.04
Calw,0.34,0.09,0.26,0.12,0.05,0.06,0.04,0.05
Freiburg,0.22,0.27,0.1,0.15,0.14,0.04,0.04,0.04
Lörrach - Müllheim,0.29,0.15,0.18,0.16,0.07,0.05,0.04,0.05
Emmendingen- Lahr,0.32,0.13,0.19,0.16,0.06,0.05,0.04,0.05
Offenburg,0.34,0.11,0.22,0.13,0.06,0.05,0.05,0.05
Rottweil - Tuttlingen,0.34,0.08,0.27,0.11,0.05,0.06,0.05,0.05
Schwarzwald-Baar,0.34,0.1,0.24,0.13,0.05,0.05,0.04,0.05
Konstanz,0.3,0.17,0.18,0.13,0.07,0.06,0.04,0.04
Waldshut,0.34,0.14,0.19,0.14,0.06,0.05,0.04,0.05
Reutlingen,0.33,0.12,0.21,0.13,0.06,0.06,0.05,0.04
Tübingen,0.29,0.19,0.16,0.14,0.1,0.05,0.04,0.04
Ulm,0.34,0.14,0.19,0.13,0.06,0.05,0.04,0.04
Biberach,0.38,0.1,0.23,0.1,0.05,0.05,0.04,0.05
Bodensee,0.35,0.14,0.19,0.13,0.06,0.06,0.04,0.04
Ravensburg,0.35,0.13,0.19,0.12,0.06,0.05,0.04,0.05
Zollernalb - Sigmaringen,0.37,0.08,0.26,0.11,0.05,0.05,0.04,0.04

Hier als Hilfestellung das Ergebnis der Landtagswahl nach (70) Wahlkreisen:
Wahlkreis,"Wahljahr","Wahlbeteiligung". "GRÜNE","CDU","AfD","SPD","FDP","DIE LINKE","Sonstige"
01 Stuttgart I,2021,69.4,44.8,17.9,3.3,9.4,10.1,7.5,7.0
02 Stuttgart II,2021,69.9,39.8,21.7,4.9,10.0,12.9,4.4,6.3
03 Stuttgart III,2021,59.9,33.9,24.3,8.0,12.2,10.6,4.8,6.2
04 Stuttgart IV,2021,59.6,35.6,21.5,5.8,13.2,9.7,7.0,7.0
05 Böblingen,2021,63.3,31.4,25.3,9.4,13.1,11.4,2.3,7.0
06 Leonberg,2021,68.7,32.7,26.0,8.2,10.6,11.7,2.3,8.5
07 Esslingen,2021,65.6,35.7,23.8,7.2,14.2,9.4,3.8,6.0
08 Kirchheim,2021,67.3,33.1,24.4,9.5,12.6,10.3,2.8,7.2
09 Nürtingen,2021,67.7,38.8,21.6,9.1,9.2,11.6,2.6,7.2
10 Göppingen,2021,60.0,28.8,26.5,12.3,12.3,8.9,2.1,9.1
11 Geislingen,2021,65.6,27.5,27.9,11.5,14.4,10.3,2.3,6.0
12 Ludwigsburg,2021,64.2,34.6,22.2,8.7,12.1,11.2,4.2,7.1
13 Vaihingen,2021,69.2,34.9,24.8,8.6,9.2,11.1,2.7,8.7
14 Bietigheim-Bissingen,2021,66.6,34.2,24.5,9.2,10.6,10.9,2.8,7.8
15 Waiblingen,2021,65.2,30.0,25.1,8.1,10.8,13.3,3.1,9.6
16 Schorndorf,2021,67.7,29.7,24.2,9.9,10.4,16.3,2.6,6.8
17 Backnang,2021,64.0,24.0,23.2,12.1,19.0,10.5,2.4,8.7
18 Heilbronn,2021,60.3,30.0,23.0,12.0,11.6,12.3,3.6,7.6
19 Eppingen,2021,65.4,26.3,24.5,13.7,11.1,13.4,2.6,8.3
20 Neckarsulm,2021,64.5,27.4,25.0,13.9,12.7,9.9,3.0,8.1
21 Hohenlohe,2021,62.9,28.7,24.4,14.1,11.9,10.9,2.8,7.2
22 Schwäbisch Hall,2021,61.5,28.7,23.2,12.5,11.3,13.1,3.3,7.8
23 Main-Tauber,2021,63.8,27.1,29.5,10.6,10.4,8.4,2.4,11.4
24 Heidenheim,2021,60.1,25.8,22.4,11.4,20.2,7.6,2.6,10.0
25 Schwäbisch Gmünd,2021,64.1,30.1,25.8,12.0,10.8,10.8,3.4,7.0
26 Aalen,2021,63.9,25.0,29.8,9.5,10.0,9.1,2.7,13.9
27 Karlsruhe I,2021,63.9,39.1,17.5,6.7,11.8,8.2,6.9,9.8
28 Karlsruhe II,2021,58.9,38.6,18.4,7.5,12.0,7.3,6.7,9.4
29 Bruchsal,2021,63.8,26.3,27.1,13.2,11.8,9.7,2.6,9.3
30 Bretten,2021,65.9,32.0,23.0,11.2,10.8,11.4,2.8,8.7
31 Ettlingen,2021,67.6,33.5,24.2,9.5,11.8,10.2,2.8,7.9
32 Rastatt,2021,59.7,30.3,23.8,12.6,13.6,8.0,2.8,8.9
33 Baden-Baden,2021,63.4,32.6,27.8,8.9,11.1,8.8,2.7,8.1
34 Heidelberg,2021,67.3,41.7,15.3,5.2,12.7,7.0,8.4,9.8
35 Mannheim I,2021,51.3,27.8,15.2,12.7,21.7,6.7,6.2,9.7
36 Mannheim II,2021,61.8,35.9,16.7,7.9,15.9,9.3,5.5,8.7
37 Wiesloch,2021,63.4,29.7,26.6,11.2,12.1,9.4,2.8,8.3
38 Neckar-Odenwald,2021,62.1,23.7,31.6,12.3,12.2,7.9,2.4,9.9
39 Weinheim,2021,67.5,35.6,22.6,7.9,13.4,8.6,3.6,8.4
40 Schwetzingen,2021,62.0,31.3,23.6,10.4,14.8,8.2,3.1,8.5
41 Sinsheim,2021,63.4,29.3,25.9,11.0,13.8,9.1,2.9,8.1
42 Pforzheim,2021,54.0,26.2,20.1,15.8,10.1,16.1,3.3,8.3
43 Calw,2021,63.7,27.1,28.8,13.5,7.8,10.0,2.7,10.1
44 Enz,2021,66.3,30.9,19.5,12.9,9.5,17.0,2.3,7.9
45 Freudenstadt,2021,62.2,24.7,27.3,13.2,8.4,14.8,2.2,9.4
46 Freiburg I,2021,70.6,40.2,19.4,5.1,11.2,7.5,6.8,9.8
47 Freiburg II,2021,64.5,40.3,13.3,5.8,12.7,5.9,11.2,10.9
48 Breisgau,2021,66.2,37.7,23.9,7.0,10.3,9.0,3.7,8.3
49 Emmendingen,2021,65.0,36.2,21.8,7.2,11.5,10.1,3.4,9.8
50 Lahr,2021,61.0,33.1,24.5,10.0,10.4,10.2,2.6,9.2
51 Offenburg,2021,61.8,36.8,25.4,8.3,8.6,8.9,2.9,9.0
52 Kehl,2021,61.4,31.4,27.1,9.7,8.7,9.4,2.6,11.0
53 Rottweil,2021,64.3,26.0,26.7,12.8,7.3,16.2,2.6,8.3
54 Villingen-Schwenningen,2021,60.6,34.6,22.5,11.3,9.1,12.2,2.4,7.8
55 Tuttlingen-Donaueschingen,2021,60.2,28.1,29.3,12.9,6.9,13.4,2.6,6.8
56 Konstanz,2021,63.2,42.1,18.2,5.8,8.4,12.1,5.4,8.1
57 Singen,2021,58.5,32.1,21.5,11.3,12.3,11.7,3.0,8.1
58 Lörrach,2021,60.0,35.8,21.4,7.9,12.6,10.3,3.0,9.0
59 Waldshut,2021,56.6,37.1,22.9,9.9,9.6,10.2,2.7,7.6
60 Reutlingen,2021,63.6,36.2,22.0,9.5,10.2,11.3,3.7,7.1
61 Hechingen-Münsingen,2021,64.5,31.6,25.0,12.2,8.9,12.6,2.6,7.1
62 Tübingen,2021,70.5,39.0,20.5,6.5,11.6,7.6,6.7,8.1
63 Balingen,2021,61.5,26.5,32.6,12.2,7.8,10.0,2.4,8.5
64 Ulm,2021,63.4,36.5,22.9,7.4,13.2,7.8,4.3,7.9
65 Ehingen,2021,66.5,29.5,35.9,10.1,7.0,8.2,2.1,7.2
66 Biberach,2021,65.1,28.9,34.1,10.0,5.8,8.1,2.2,10.9
67 Bodensee,2021,67.1,36.8,21.9,8.6,8.5,13.3,3.1,7.8
68 Wangen,2021,63.8,31.3,30.6,9.5,6.5,8.9,2.7,10.6
69 Ravensburg,2021,65.3,33.1,23.7,8.7,8.2,11.5,3.4,11.4
70 Sigmaringen,2021,63.3,32.6,27.8,11.2,6.2,12.1,2.4,7.6


Hinweise:
- Es gibt genau 70 Direktmandate.
- Parteien, die flächig starke Regionen haben, gewinnen dort eher Direktmandate.
- Gib ausschließlich ein korrektes JSON-Objekt zurück – ohne Text, Erklärungen oder Formatierungen.

Beispielausgabe:
{
  "CDU": 60,
  "B90/Grüne": 8,
  "AfD": 2,
  "SPD": 0,
  "Die Linke": 0,
  "FDP": 0,
  "BSW": 0,
  "Sonstige": 0
}
"""

# Berechnung auf Basis Largest Remainders + Ausgleichsmandate


def berechne_verteilung(eingabe, direktmandate):
    # Parteien, die über 5% liegen (ohne BSW, Sonstige)
    parteien = [p for p in eingabe if eingabe[p]
                >= 5 and p not in ["BSW", "Sonstige"]]
    gesamt_prozent = sum(eingabe[p] for p in parteien)
    anteile = {p: eingabe[p] / gesamt_prozent for p in parteien}

    # Schritt 1: Verteilung der 120 Grundsitze (ohne Direktmandate)
    grundsitze = 120
    sitze_vor_rest = {p: math.floor(anteile[p] * grundsitze) for p in parteien}
    rest = grundsitze - sum(sitze_vor_rest.values())
    reste = {p: (anteile[p] * grundsitze) - sitze_vor_rest[p]
             for p in parteien}
    for p in sorted(reste, key=reste.get, reverse=True)[:rest]:
        sitze_vor_rest[p] += 1

    # Schritt 2: Berechne Überhangmandate je Partei
    ueberhang = {p: max(0, direktmandate.get(
        p, 0) - sitze_vor_rest.get(p, 0)) for p in parteien}
    ges_ueberhang = sum(ueberhang.values())

    # Schritt 3: Berechne erforderliche neue Sitzanzahl (mind. 120)
    min_sitze = max(grundsitze, sum(sitze_vor_rest.values()) + ges_ueberhang)

    # Schritt 4: Verteile Sitze proportional auf neue Sitzanzahl
    sitze = {p: round(anteile[p] * min_sitze) for p in parteien}

    # Schritt 5: Korrigiere Ausgleichsmandate, falls nötig
    while any(sitze[p] < direktmandate.get(p, 0) for p in parteien):
        min_sitze += 1
        sitze = {p: round(anteile[p] * min_sitze) for p in parteien}

    # Schritt 6: Abschließende Werte einfügen
    # sitze.update({"BSW": 0, "Sonstige": 0})
    # sitze["Gesamtzahl der Sitze"] = sum(sitze.values())
    # return sitze

    # Schritt 6: Abschließende Werte einfügen – alle Parteien absichern
    alle_parteien = ["CDU", "B90/Grüne", "AfD",
                     "SPD", "Die Linke", "FDP", "BSW", "Sonstige"]
    for p in alle_parteien:
    sitze.setdefault(p, 0)

    sitze["Gesamtzahl der Sitze"] = sum(sitze[p] for p in alle_parteien)


@app.route("/", methods=["GET"])
def index():
    return render_template_string(html_template)


@app.route("/prognose", methods=["POST"])
def prognose():
    eingabe = {party: int(request.form[party]) for party in request.form}
    if sum(eingabe.values()) != 100:
        return render_template_string(html_template, result={"Hinweis": "Fehler: Die Summe der Werte muss genau 100 ergeben."})

    nutzer_prompt = f"Eingabeformat für die Prognose zur Landtagswahl Baden-Württemberg 2026 (Zweitstimmenanteile in Prozent):\n{eingabe}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nutzer_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        text_output = response.choices[0].message.content

        json_block = re.search(r"\{.*\}", text_output, re.DOTALL)
        if not json_block:
            raise ValueError("Kein JSON-Block erkannt.")
        cleaned = json_block.group(0).replace("'", '"')
        gpt_result = json.loads(cleaned)

        # robustere Extraktion mit get() für alle Parteien
        direktmandate = {p: gpt_result.get(p, 0) for p in [
            "CDU", "B90/Grüne", "AfD", "SPD", "Die Linke", "FDP", "BSW", "Sonstige"]}
        result_data = berechne_verteilung(eingabe, direktmandate)

        parteien = ["CDU", "B90/Grüne", "AfD", "SPD",
                    "Die Linke", "FDP", "BSW", "Sonstige"]
        anteile = {p: eingabe[p] / sum(eingabe[p2] for p2 in parteien if eingabe[p2] > 0)
                   for p in parteien if eingabe[p] > 0}
        gesamt = result_data["Gesamtzahl der Sitze"]
        rel = {p: result_data.get(p, 0) / gesamt for p in anteile}
        abweichung = {p: round((rel[p] - anteile[p]) * 100, 2)
                      for p in anteile}
        abw_max = max(abs(v) for v in abweichung.values())

        result_data["Hinweis"] = "Diese Verteilung ist eine Schätzung."
        if abw_max > 2:
            result_data[
                "Hinweis"] += f" ⚠️ Abweichung zur Zweitstimmenverteilung erkennbar: {abweichung}"

    except Exception as e:
        result_data = {"Hinweis": f"Fehler bei API-Anfrage: {e}"}

    return render_template_string(html_template, result=result_data)


# if __name__ == "__main__":
    # app.run(debug=True, port=5000)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
