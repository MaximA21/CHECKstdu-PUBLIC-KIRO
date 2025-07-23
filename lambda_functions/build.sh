#!/bin/bash

# Enhanced Lambda build script with DI architecture support
# Verzeichnisse erstellen, falls sie nicht existieren
mkdir -p ../lambda_packages

echo "Building Lambda functions with new DI architecture..."

# Durch alle Lambda-Funktionen iterieren
for func_dir in */; do
  func_name=$(basename "$func_dir")
  echo "Building $func_name..."

  # In das Funktionsverzeichnis wechseln
  cd "$func_dir"

  # Temporäres Build-Verzeichnis erstellen
  mkdir -p build

  # Abhängigkeiten installieren
  if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --target ./build --platform linux_x86_64 --only-binary=:all:
  fi

  # Funktionscode kopieren
  cp "${func_name}.py" ./build/

  # Copy entire src directory for DI architecture
  echo "Copying src directory for DI support..."
  cp -r "../../src" ./build/

  # Copy config files
  if [ -d "../../config" ]; then
    cp -r "../../config" ./build/
  fi

  # Create __init__.py files if missing
  find ./build -type d -exec touch {}/__init__.py \;

  # ZIP-Paket erstellen
  cd build
  
  # Exclude unnecessary files to reduce package size
  zip -r "../../${func_name}.zip" . \
    -x "**/__pycache__/*" \
    -x "**/*.pyc" \
    -x "**/*.pyo" \
    -x "**/.DS_Store" \
    -x "**/tests/*" \
    -x "**/.pytest_cache/*"

  # Aufräumen
  cd ..
  rm -rf build

  # Zurück zum Lambda-Verzeichnis
  cd ..

  # ZIP-Datei in das lambda_packages-Verzeichnis verschieben
  mv "${func_name}.zip" ../lambda_packages/

  echo "$func_name built and packaged with DI architecture."
done

echo "All Lambda functions packaged successfully with new architecture."

# Create manifest file with build information
cat > ../lambda_packages/manifest.json << EOF
{
  "build_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "architecture": "new_di_architecture",
  "region": "eu-central-1",
  "functions": [
$(for func_dir in */; do
  func_name=$(basename "$func_dir")
  echo "    \"$func_name\""
  if [ "$func_dir" != "$(ls -d */ | tail -n1)" ]; then
    echo ","
  fi
done)
  ]
}
EOF

echo "Build manifest created at ../lambda_packages/manifest.json"