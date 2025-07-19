#!/bin/bash

# Verzeichnisse erstellen, falls sie nicht existieren
mkdir -p ../lambda_packages

# Durch alle Lambda-Funktionen iterieren
for func_dir in */; do
  func_name=$(basename "$func_dir")
  echo "Building $func_name..."

  # In das Funktionsverzeichnis wechseln
  cd "$func_dir"

  # Temporäres Build-Verzeichnis erstellen
  mkdir -p build

  # Abhängigkeiten installieren
  pip install -r requirements.txt --target ./build

  # Funktionscode kopieren
  cp "${func_name}.py" ./build/

  # ZIP-Paket erstellen
  cd build
  zip -r "../../${func_name}.zip" .

  # Aufräumen
  cd ..
  rm -rf build

  # Zurück zum Lambda-Verzeichnis
  cd ..

  # ZIP-Datei in das lambda_packages-Verzeichnis verschieben
  mv "${func_name}.zip" ../lambda_packages/

  echo "$func_name built and packaged."
done

echo "All Lambda functions packaged successfully."