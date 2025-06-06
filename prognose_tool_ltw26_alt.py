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
client = OpenAI()

app = Flask(__name__)

# Minimaler HTML-Code mit horizontalem Layout
html_template = """
<!doctype html>
<title>Sitzverteilung BW 2026</title>
<h2>Schätzung der Sitzverteilung im Landtag von Baden-Württemberg aufgrund Prognosen zur Landtagswahl 2026</h2>
<div style="display: flex; gap: 50px; align-items: flex-start;">
  <form method=post action="/prognose">
    {% for party in ["CDU", "B90/Grüne", "AfD", "SPD", "Die Linke", "FDP", "BSW", "Sonstige"] %}
      <label>{{party}} (%):</label><br>
      <input name="{{party}}" type="number" min="0" max="100" required><br><br>
    {% endfor %}
    <input type=submit value=Absenden>
  </form>

  {% if result %}
    <div>
      <h3>Ergebnis:</h3>
      <table border="1" cellpadding="5" cellspacing="0">
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
"""

# system_prompt definieren
system_prompt = """
Du bist ein Prognosetool zur Schätzung der Direktmandate bei der Landtagswahl Baden-Württemberg 2026. Grundlage ist eine Wahlprognose mit Zweitstimmenanteilen in Prozent.

Aufgabe:
Schätze, wie viele der 70 Direktmandate (Mehrheitswahl) jede Partei in den 70 Wahlkreisen von Baden-Württemberg gewinnt. Gehe vereinfachend davon aus, dass Erst- und Zweitstimmen gleich verteilt sind.

Datenbasis:
Nutze typische regionale Muster der Bundestagswahl 2025. Die folgende Tabelle enthält die Zweitstimmenverteilung in den 37 Bundestagswahlkreisen in BW (in Dezimalwerten):

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
    ueberhang = {
        p: max(0, direktmandate.get(p, 0) - sitze_vor_rest.get(p, 0))
        for p in parteien
    }
    ges_ueberhang = sum(ueberhang.values())

    # Schritt 3: Berechne erforderliche neue Sitzanzahl (mind. 120)
    min_sitze = grundsitze + ges_ueberhang

    # Schritt 4: Verteile Sitze proportional auf neue Sitzanzahl
    sitze = {p: round(anteile[p] * min_sitze) for p in parteien}

    # Schritt 5: Korrigiere Ausgleichsmandate, falls nötig
    # Stelle sicher, dass keine Partei weniger Sitze als Direktmandate erhält
    while any(sitze[p] < direktmandate.get(p, 0) for p in parteien):
        min_sitze += 1
        sitze = {p: round(anteile[p] * min_sitze) for p in parteien}

    # Schritt 6: Abschließende Werte einfügen
    sitze.update({"BSW": 0, "Sonstige": 0})
    sitze["Gesamtzahl der Sitze"] = sum(sitze.values())
    return sitze


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

        direktmandate = {k: v for k, v in gpt_result.items() if k in [
            "CDU", "B90/Grüne", "AfD", "SPD", "Die Linke", "FDP"] and isinstance(v, int)}
        result_data = berechne_verteilung(eingabe, direktmandate)

        parteien = ["CDU", "B90/Grüne", "AfD", "SPD", "Die Linke", "FDP"]
        anteile = {p: eingabe[p] / sum(eingabe[p2]
                                       for p2 in parteien) for p in parteien}
        gesamt = result_data["Gesamtzahl der Sitze"]
        rel = {p: result_data[p] / gesamt for p in parteien}
        abweichung = {p: round((rel[p] - anteile[p]) * 100, 2)
                      for p in parteien}
        abw_max = max(abs(v) for v in abweichung.values())

        result_data["Hinweis"] = "Diese Verteilung ist eine Schätzung."
        if abw_max > 2:
            result_data[
                "Hinweis"] += f" ⚠️ Abweichung zur Zweitstimmenverteilung erkennbar: {abweichung}"

    except Exception as e:
        result_data = {"Hinweis": f"Fehler bei API-Anfrage: {e}"}

    return render_template_string(html_template, result=result_data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
