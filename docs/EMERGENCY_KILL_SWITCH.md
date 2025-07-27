# Emergency Kill Switch - WebWunder Infrastructure

## 🚨 Übersicht

WebWunder verfügt über mehrere "Kill Switch" Optionen für Notfälle und vollständige Infrastruktur-Zerstörung:

1. **Rollback** - Rollback zu vorherigen Versionen
2. **Emergency Destroy** - Vollständige Infrastruktur-Zerstörung
3. **Terraform Destroy** - Manueller Terraform Destroy

## 🔄 Rollback (Sicherste Option)

### Rollback zu vorherigen Versionen

```bash
# Rollback für Staging
python3 scripts/rollback.py staging --list-versions

# Rollback für Production (mit Bestätigung)
python3 scripts/rollback.py production --target-version 5 --auto-confirm

# Rollback mit Backup
python3 scripts/rollback.py production --target-version 5
```

### Rollback über GitHub Actions

Der Deployment-Workflow unterstützt Rollback über `workflow_dispatch`:

1. Gehe zu **Actions** → **Deployment Pipeline**
2. Klicke **Run workflow**
3. Wähle **production** als Environment
4. Gib die **rollback_version** ein
5. Klicke **Run workflow**

## 🗑️ Emergency Destroy (Vollständige Zerstörung)

### Lokaler Emergency Destroy

```bash
# Liste alle Ressourcen die zerstört werden
python3 scripts/destroy.py staging --list-resources

# Staging zerstören (mit Bestätigung)
python3 scripts/destroy.py staging

# Production zerstören (mit Backup)
python3 scripts/destroy.py production

# Schneller Destroy ohne Backup
python3 scripts/destroy.py production --skip-backup --auto-confirm

# Nur AWS-Ressourcen, kein Terraform
python3 scripts/destroy.py production --skip-terraform
```

### Emergency Destroy über GitHub Actions

1. Gehe zu **Actions** → **Emergency Infrastructure Destroy**
2. Klicke **Run workflow**
3. Wähle Environment: **staging** oder **production**
4. Optionen:
   - **Skip Backup**: Kein Backup erstellen
   - **Skip Terraform**: Nur AWS-Ressourcen zerstören
   - **Auto Confirm**: Keine Bestätigung erforderlich
5. Klicke **Run workflow**

## 🏗️ Terraform Destroy (Manuell)

### Terraform Workspace Destroy

```bash
# Staging zerstören
cd terraform
terraform init
terraform workspace select staging
terraform destroy -auto-approve -var="environment=staging"

# Production zerstören
cd terraform
terraform init
terraform workspace select production
terraform destroy -auto-approve -var="environment=production"
```

### Terraform Destroy über GitHub Actions

```bash
# Staging
gh workflow run emergency-destroy.yml -f environment=staging -f skip_terraform=false

# Production
gh workflow run emergency-destroy.yml -f environment=production -f skip_terraform=false
```

## 🎯 Kill Switch Strategien

### 1. **Schneller Rollback** (Empfohlen)
- **Ziel**: Schnelle Wiederherstellung bei Problemen
- **Methode**: Rollback zu funktionierender Version
- **Dauer**: 2-5 Minuten
- **Risiko**: Niedrig

```bash
python3 scripts/rollback.py production --target-version 5 --auto-confirm
```

### 2. **Selektive Zerstörung**
- **Ziel**: Nur problematische Komponenten entfernen
- **Methode**: Einzelne AWS-Ressourcen zerstören
- **Dauer**: 5-10 Minuten
- **Risiko**: Mittel

```bash
python3 scripts/destroy.py production --skip-terraform
```

### 3. **Vollständige Zerstörung**
- **Ziel**: Komplette Infrastruktur entfernen
- **Methode**: Terraform + AWS-Ressourcen zerstören
- **Dauer**: 10-20 Minuten
- **Risiko**: Hoch

```bash
python3 scripts/destroy.py production --auto-confirm
```

## ⚠️ Sicherheitsmaßnahmen

### Backup vor Zerstörung

```bash
# Backup erstellen
python3 scripts/destroy.py production --list-resources
# Backup wird automatisch erstellt: backup-destroy-backup-production-{timestamp}.json
```

### Bestätigung erforderlich

- **Staging**: Einfache Bestätigung (`y/N`)
- **Production**: Typing `DESTROY PRODUCTION` erforderlich
- **GitHub Actions**: Environment Protection Rules

### Rollback nach Zerstörung

```bash
# Infrastruktur neu erstellen
cd terraform
terraform init
terraform workspace new production
terraform apply -auto-approve -var="environment=production"

# Deployment
gh workflow run deployment.yml -f environment=production
```

## 🚨 Notfall-Prozeduren

### 1. **Kritischer Bug in Production**

```bash
# 1. Schneller Rollback
python3 scripts/rollback.py production --target-version 5 --auto-confirm

# 2. Oder Traffic auf 0% setzen
python3 scripts/manage-canary-deployment.py rollback webwunder-prod prod
```

### 2. **Sicherheitsvorfall**

```bash
# 1. Vollständige Zerstörung
python3 scripts/destroy.py production --auto-confirm

# 2. Infrastruktur neu aufbauen
cd terraform && terraform apply -auto-approve -var="environment=production"
```

### 3. **Kostenexplosion**

```bash
# 1. Alle Ressourcen stoppen
python3 scripts/destroy.py production --skip-terraform

# 2. Terraform später zerstören
cd terraform && terraform destroy -auto-approve -var="environment=production"
```

## 📊 Monitoring und Logging

### Destroy-Logs

```bash
# Logs anzeigen
tail -f backup-destroy-backup-production-*.json

# GitHub Actions Logs
gh run list --workflow=emergency-destroy.yml
```

### Rollback-Logs

```bash
# Rollback-Historie
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/webwunder-prod"

# GitHub Actions Logs
gh run list --workflow=deployment.yml
```

## 🔧 Konfiguration

### Environment Variables

```bash
export AWS_REGION=eu-central-1
export AWS_PROFILE=webwunder-prod
```

### GitHub Secrets

- `AWS_GITHUB_ACTIONS_ROLE_ARN`: AWS Role für GitHub Actions
- Environment Protection Rules für Production

## 📞 Support

Bei Problemen mit Kill Switch Operationen:

1. **Logs prüfen**: GitHub Actions Logs und AWS CloudWatch
2. **Backup verwenden**: `backup-*.json` Dateien
3. **Manueller Rollback**: AWS Console
4. **Support kontaktieren**: DevOps Team

---

**⚠️ WICHTIG**: Kill Switch Operationen sind IRREVERSIBEL. Verwenden Sie sie nur in echten Notfällen! 