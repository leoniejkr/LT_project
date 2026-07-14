kleine süße ideen:


würd wandb nutzen später (macht keinen krassen unterschied im code, nur dass wir sehen wie model parameter unser modelperformance beinflussen)

schreiben code in python!!
prolly ADAM als optimizer



website quatsch
html--> gucken wie mit domain wir es machen


#### Erstellung der lokalen Python Umgebung
python -m venv .../LT_project

Docker Umgebung auf Windows starten und für Projekt vorbereiten
"Devcontainer Extention" für VSCode herunter laden
docker compose build (Auch bei jeder Änderung der requirements.txt, package.json oder go.mod/go.sum ausführen)
docker compose up

Docker Volumes (und damit ganze "Daten") löschen
Gut wenn man grundlegendere Änderungen im Code gemacht hat und diese in den Containern wiederspiegeln lassen möchte
docker compose down -v

Frontend zum laufen bringen
nvm für windows installieren (optional)
nvm on
nvm install latest
nvm use [version die installiert wurde]

Swagger updaten
swag init --dir ./cmd/server,./internal/api --output ./docs

Den Nutzerflow testen
Docker hochfahren docker compose up -d
über den Upload Patientendaten hochladen
PostgreSQL prüfen:
psql -h localhost -p 5432 -U trustai_user -d trustai_db -c "SELECT * FROM patients;"
Orthanc prüfen:
curl -u user:user http://localhost:8042/instances | python3 -m json.tool
Prüfen, ob die Daten zusammenhängend stimmen. Die x_ray_paths in der Patient-Tabelle sind die Orthanc Instance UUIDs:
SELECT x_ray_paths::text FROM patients;
UUIDS sollten mit den IDs aus dem http://localhost:8042/instances übereinstimmen