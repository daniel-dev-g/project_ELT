# Git — Guía de referencia

## Conceptos básicos

Git es un sistema de control de versiones. Registra cada cambio en el código para que puedas:
- Volver a versiones anteriores
- Trabajar en paralelo sin romper lo que funciona
- Colaborar con otros sin pisar cambios

---

## Configuración inicial

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@email.com"
```

---

## Comandos esenciales

### Estado y exploración

```bash
git status                  # Ver qué archivos cambiaron
git log --oneline           # Historial resumido de commits
git log --oneline -5        # Últimos 5 commits
git diff                    # Ver cambios no guardados
```

### Guardar cambios (commit)

```bash
git add archivo.py          # Agregar un archivo al staging
git add .                   # Agregar todos los archivos cambiados
git commit -m "descripción" # Crear un commit con mensaje
```

### Subir y bajar cambios

```bash
git push                    # Subir commits al remoto (GitHub)
git pull                    # Bajar cambios del remoto
git fetch                   # Bajar cambios sin fusionar
```

---

## Ramas (branches)

Una rama es una línea de desarrollo independiente. Permite trabajar en una feature sin afectar el código principal.

### Comandos de ramas

```bash
git branch                  # Ver ramas locales (* = rama actual)
git branch -a               # Ver ramas locales y remotas
git checkout -b nombre      # Crear y cambiar a una nueva rama
git checkout nombre         # Cambiar a una rama existente
git merge nombre            # Fusionar una rama en la actual
git branch -d nombre        # Eliminar rama local (solo si ya fue mergeada)
git push origin --delete nombre  # Eliminar rama remota
```

### Ver en qué rama estás

```bash
git branch
```
La rama activa tiene un `*` al lado.

---

## Flujo de trabajo con ramas — este proyecto

Usamos un flujo con tres niveles:

```
main  →  código estable, lo que "va a producción"
 └── dev  →  integración, donde se acumulan features probadas
       └── feature/*  →  desarrollo de una funcionalidad específica
```

### Ejemplo de flujo completo

```bash
# 1. Partir desde dev
git checkout dev
git pull                          # asegurarse de tener lo último

# 2. Crear feature
git checkout -b feature/mysql-adapter

# 3. Trabajar... hacer commits
git add .
git commit -m "agrega soporte MySQL"

# 4. Subir la feature al remoto
git push -u origin feature/mysql-adapter

# 5. Fusionar en dev cuando está lista
git checkout dev
git merge feature/mysql-adapter

# 6. Cuando dev está estable, fusionar en main
git checkout main
git merge dev
git push
```

### Ramas de este proyecto

| Rama | Propósito |
|------|-----------|
| `main` | Código estable y probado |
| `dev` | Integración antes de pasar a main |
| `feature/docker-sqlserver` | Soporte SQL Server + Docker (ya mergeada) |
| `reestructuracion-completa` | Reestructuración inicial (obsoleta) |

---

## SSH — Conexión segura con GitHub

### ¿Por qué SSH?

Hay dos formas de autenticarse con GitHub:

| Método | Descripción |
|--------|-------------|
| HTTPS | Pide usuario y token cada vez |
| SSH | Usa llaves criptográficas — sin contraseñas |

### El par de llaves

SSH genera dos archivos:

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `~/.ssh/id_ed25519` | Privada | Se queda en tu PC. Nunca la compartes |
| `~/.ssh/id_ed25519.pub` | Pública | Se copia a GitHub |

Funciona como un candado y su llave: GitHub tiene el candado (llave pública), tu PC tiene la llave (llave privada).

### Lo que configuramos en este proyecto

```bash
# 1. Generar el par de llaves
ssh-keygen -t ed25519 -C "ia.daniel1024@gmail.com"

# 2. Ver la llave pública para copiarla en GitHub
cat ~/.ssh/id_ed25519.pub
```

En GitHub: **Settings → SSH and GPG keys → New SSH key** → pegar el contenido de la llave pública.

```bash
# 3. Cambiar la URL del repo de HTTPS a SSH
git remote set-url origin git@github.com:daniel-dev-g/project_ELT.git

# 4. Verificar que quedó configurado
git remote -v
```

### Verificar conexión SSH con GitHub

```bash
ssh -T git@github.com
# Respuesta esperada: Hi daniel-dev-g! You've successfully authenticated...
```

---

## Resolver conflictos de merge

Un conflicto ocurre cuando dos ramas modificaron la misma línea de un archivo.

Git marca el conflicto así dentro del archivo:

```
<<<<<<< HEAD
código de tu rama actual
=======
código de la otra rama
>>>>>>> feature/otra-rama
```

Pasos para resolver:
1. Abrir el archivo y elegir qué código conservar (o combinar ambos)
2. Eliminar las marcas `<<<<<<<`, `=======`, `>>>>>>>`
3. Guardar el archivo
4. `git add archivo.py`
5. `git commit -m "resuelve conflicto"`

---

## Recuperar errores comunes

### Deshacer el último commit (sin perder cambios)

```bash
git reset --soft HEAD~1
```

### Ver qué hay en el remoto sin descargar

```bash
git fetch
git log --oneline origin/main -5
```

### Comparar dos ramas

```bash
git log --oneline main...dev --left-right
```
- `<` = commit solo en `main`
- `>` = commit solo en `dev`