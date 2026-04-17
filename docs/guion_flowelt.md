# FlowELT — Guión cortometraje

## Contexto

Video animado corto dirigido a dos audiencias simultáneas:
- **Desarrolladores e ingenieros de datos** que reconocen el dolor
- **Empresas y reclutadores** que evalúan criterio técnico y visión

Basado en tres experiencias reales: banca con SSIS + DB2 + Teradata, retail con Airflow + GCP, y cubos OLAP con problemas de licencias y gobernanza.

---

## Escena 1 — El mundo real (30 seg)

*Pantalla oscura. Texto aparece lento:*

> "Cada día, miles de empresas mueven datos de un sistema a otro."

*Aparecen íconos: un banco, un retail, una aseguradora.*

> "Bases de datos distintas. Sistemas legados. Formatos incompatibles."

*Los íconos intentan conectarse entre sí — flechas que no llegan, conexiones que se cortan.*

---

## Escena 2 — El dolor (45 seg)

*Tres situaciones rápidas, como viñetas:*

**Viñeta 1**
> *Un desarrollador frente a SSIS intentando conectar DB2 con SQL Server.*
> Texto: *"¿Por qué Teradata no habla con Microsoft?"*

**Viñeta 2**
> *Alarma a las 2am. El pipeline de Airflow falló. Nadie sabe en qué paso.*
> Texto: *"¿Cuándo falló? ¿Qué datos llegaron? ¿Qué datos no?"*

**Viñeta 3**
> *Un ETL detenido. El usuario dueño del proceso renunció.*
> Texto: *"El proceso estaba a nombre de Juan. Juan ya no trabaja aquí."*

*Pausa. Texto solo:*

> **"Esto no debería ser tan difícil."**

---

## Escena 3 — La pregunta (10 seg)

> *"¿Qué pasaría si mover datos fuera simple, rápido y auditable?"*

---

## Escena 4 — FlowELT (40 seg)

*Animación simple: un archivo CSV entra por un lado. Del otro lado aparece una tabla en la base de datos.*

> "FlowELT carga datos masivos directamente al motor de base de datos."
> "Sin frameworks complejos. Sin licencias. Sin depender de una persona."

*Aparecen íconos: SQL Server, PostgreSQL, más motores.*

> "Funciona con los motores que ya tienes."

*Aparece un archivo de log estructurado.*

> "Cada carga queda registrada. El auditor, el DBA, el arquitecto — todos pueden ver qué pasó, cuándo y cuánto tardó."

---

## Escena 5 — Para quién es (25 seg)

*Aparecen cinco perfiles, uno por uno:*

- **El ingeniero de datos** — que quiere una herramienta simple y rápida
- **El DBA** — que necesita trazabilidad y control
- **El arquitecto** — que no quiere dependencia de licencias ni vendors
- **El auditor** — que necesita saber exactamente qué datos entraron y cuándo
- **El responsable de Gobierno de Datos** — que necesita conocer la calidad del dato antes de que llegue a producción *(perfilamiento opcional por archivo)*

---

## Escena 6 — Cierre (15 seg)

> "FlowELT nació de experiencias reales en banca y retail."
> "Código abierto. Sin magia. Sin vendor lock-in."

*Logo FlowELT. Link al repositorio.*

> **"Porque mover datos no debería ser el problema."**

---

## Notas de producción

- Tono: directo, cercano, sin tecnicismos en pantalla
- Duración total estimada: ~2:45 min
- Perfilamiento de datos: disponible hoy como opción `profile: true` en yaml, por archivo
- Roadmap visual: interfaz gráfica en versión futura