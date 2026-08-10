# De instancia local a servicio web multiusuario

**Plan técnico de despliegue · v2 con las decisiones tomadas · 9 ago 2026**

Punto de partida: FastAPI + SPA React + Ollama, un solo usuario.
Destino: VPS + A40 propia, grupo cerrado de profesores.

Copia en web (misma versión, actualizable): https://claude.ai/code/artifact/b992b894-6762-412c-8be6-8b499abb51f8

> Este fichero está cubierto por `*.md` en el `.gitignore`, así que es local salvo que lo añadas a mano.

---

## Índice

0. [Veredicto y decisiones](#0-veredicto-antes-de-los-detalles)
1. [Qué impide hoy que esto sea multiusuario](#1-qué-impide-hoy-que-esto-sea-multiusuario)
2. [Las tres decisiones estructurales](#2-las-tres-decisiones-que-determinan-todo-lo-demás)
3. [Arquitectura objetivo](#3-arquitectura-objetivo)
4. [Base de datos](#4-base-de-datos)
5. [Login seguro](#5-login-seguro)
6. [Refactor del núcleo](#6-refactor-del-núcleo)
7. [Cola, equidad y cuotas](#7-cola-equidad-y-cuotas)
8. [Dónde alojarlo](#8-dónde-alojarlo)
9. [Seguridad más allá del login](#9-seguridad-más-allá-del-login)
10. [Operación](#10-operación)
11. [Fases](#11-fases)
12. [Lo que no haría](#12-lo-que-no-haría)
13. [Lo que queda por decidir](#13-lo-que-queda-por-decidir)

---

## 0. Veredicto, antes de los detalles

**Plano de control** en un VPS de Hetzner Cloud (CX32, ~7 €/mes, Alemania) con Caddy para TLS, FastAPI
sirviendo la SPA en el mismo origen, y PostgreSQL en el mismo host.

**Plano de cómputo** en la caja de la A40, ejecutando un *worker* que **sale** hacia el plano de control a
pedir trabajo: así la GPU no necesita IP pública ni puertos abiertos, y si se apaga, la web sigue en pie
con los datos intactos.

**Login** propio y alta por invitación: contraseñas con Argon2id, sesiones opacas en Postgres, cookie
`httpOnly; Secure; SameSite=Lax`. Nada de JWT en `localStorage`. Es viable porque la SPA ya se sirve desde
el mismo origen que la API.

**Datos** en PostgreSQL: usuarios, sesiones, *workspaces*, artefactos versionados como `jsonb`, trabajos y
generaciones. Los PDF/DOCX crudos y los `.npz` de embeddings, como objetos.

### Las cuatro decisiones, ya tomadas

| Pregunta | Decisión | Qué implica en el plan |
| --- | --- | --- |
| Motor de inferencia | **Solo Ollama local.** Ningún endpoint gestionado, ni siquiera de pesos abiertos. | No hay válvula de escape: la GPU es un recurso fijo y compartido, así que el presupuesto de VRAM y la cola pasan a ser decisiones de producto (§2.1, §7). |
| La A40 | **Tuya indefinidamente**, con servicio permanente. | Plano de cómputo a coste cero. Total del sistema: **~7–12 €/mes**. |
| Usuarios | **Grupo cerrado de profesores.** | Alta **por invitación**, sin registro público: desaparece la superficie de ataque más grande y con ella el captcha, la verificación como barrera antispam y las cuotas agresivas (§5, §9). |
| Autenticación | **Contraseña propia.** Sin OAuth ni IdP externo. | Argon2id + sesiones opacas en Postgres. Cero servicios de terceros en la ruta de los datos (§5). |

Esfuerzo: **algo más de 4 semanas** por fases, cada una desplegable. Las rutas de fichero solo se
referencian en ~15 módulos, siempre en fronteras (§6), y el alta por invitación recorta buena parte del
trabajo clásico de autenticación.

> ⚠ **La consecuencia incómoda de «solo Ollama local».** Una GPU, un trabajo cada vez y sin alternativa a
> la que derivar carga: mientras un profesor construye su grafo (~15 min), **ningún otro puede generar**.
> No es un fallo que se corrija programando mejor, es una propiedad del sistema. Se gestiona con dos cosas
> concretas: un presupuesto de VRAM que mantenga residente la ruta interactiva (§2.1) y una cola de dos
> clases con espera visible (§7).

---

## 1. Qué impide hoy que esto sea multiusuario

No es una lista teórica: es lo que rompería el primer día con dos personas conectadas.

### 1. Todas las rutas son constantes de módulo

`config.INSTANCE_DIR`, `KG_PATH`, `RAW_BASE_DATA_DIR` y las demás se resuelven al importar el paquete,
colgando de `PROJECT_ROOT`. Un segundo usuario escribiría encima del grafo del primero. Ya lo estás
sorteando a mano: tienes `raw_data_1/` y `raw_data_2/` y cambias la constante para pasar de uno a otro.
**El *workspace* es exactamente esa variable, convertida en dato.**

### 2. Los singletons son de proceso, no de usuario

`server/deps.py` guarda *un* `PipelineContext` global y `server/runtime.py` *un* bus, *un* runner y *un*
`ReviewState`. Con dos usuarios, el índice de conceptos de uno responde las consultas del otro.

### 3. El WebSocket emite todo a todo el mundo — **fuga de datos**

`/ws` acepta cualquier conexión sin identificar y reproduce el bus entero, incluidos los *logs* del
pipeline y el *stream* de tokens. Hoy es inocuo porque solo hay un usuario; en cuanto haya dos, los
enunciados generados por uno aparecen en el navegador del otro. Es el problema de seguridad más grave del
código actual y se arregla en la misma tarea que la autenticación (§5).

### 4. El estado vive en el disco del proceso

`.review_state.json`, `.history/`, `.runs/*.jsonl` y `cache/embeddings/*.npz`. No hay base de datos, así
que un contenedor con disco efímero se lleva por delante las aprobaciones y el historial de ediciones.

### 5. La cola es de un trabajo cada vez, y a propósito

`JobRunner` lo documenta bien: una sola GPU, y ejecutar dos modelos grandes a la vez solo intercambiaría
pesos. Con varios usuarios eso deja de ser un detalle y pasa a ser *la* experiencia del producto: un
*build* de grafo de 15 minutos bloquea las generaciones de todos los demás. Hay que hacerlo explícito y
gestionarlo (§7).

### 6. No hay identidad ni cuotas

Ni usuarios, ni permisos, ni límite agregado de subida: `raw_data.MAX_BYTES` son 512 MB *por archivo*, sin
tope por cuenta ni por workspace.

### 7. Los *builds* parsean documentos ajenos en el host de la aplicación

`build_process.run_build()` lanza un subproceso con `cwd=PROJECT_ROOT` que abre PDF y DOCX subidos por
terceros con Docling y torch. Fuera de proceso ya está —bien—, pero en producción tiene que estar además
**aislado**: contenedor propio, sin red salvo hacia Ollama, límites de CPU/RAM/tiempo y usuario sin
privilegios (§9).

> ✅ **Lo bueno.** La arquitectura actual ya tiene puestos los tres cortes que importan: `stages/` como API
> pública sin `print()` ni `SystemExit`, `inference.py` como frontera única con el motor de modelos, y el
> *build* como proceso separado con protocolo de eventos. Nada de esto hay que rehacerlo: hay que
> parametrizarlo por workspace.

---

## 2. Las tres decisiones que determinan todo lo demás

### 2.1 · Dónde vive la inferencia

Los pesos instalados hoy suman **66 GB** sobre una A40 de **46 GB**:

| Modelo | Tamaño | Para qué | ¿Ruta interactiva? |
| --- | ---: | --- | --- |
| `qwen3.6:35b-a3b-q8_0` | 38,7 GB | Extracción KG, banco, perfil, descripciones y **reparación de JSON** | Solo al reparar |
| `gemma4:31b-it-q4_K_M` | 19,9 GB | Etiquetado, generación, dominios, enlazado, taggabilidad | Sí |
| `granite4.1-guardian:8b` | 5,1 GB | Guardarraíl (harm / jailbreak) | Sí, si se activa |
| `qwen3-embedding:4b` | 2,5 GB | Índices de conceptos y banco | Sí |

> ⚠ **Hallazgo con impacto directo en el despliegue.** `REPAIR_LLM` es **el modelo más grande del sistema**
> (38,7 GB) y está en la ruta interactiva: en cuanto un JSON viene mal formado, Ollama tiene que desalojar
> gemma4 y cargar 39 GB de disco, con un parón de **uno a varios minutos** a la vista del usuario. En local
> es una molestia; en una web con varios profesores en cola —y sin ningún proveedor externo al que
> derivar— es un fallo de producto.

**Presupuesto de VRAM propuesto.** La ruta interactiva completa cabe holgadamente y puede quedarse
**residente**:

| Conjunto | VRAM | De 46 GB | Política |
| --- | ---: | ---: | --- |
| Interactivo: gemma4 + embedding | 22,4 GB | 49 % | Residente permanente vía `OLLAMA_KEEP_ALIVE` |
| + guardarraíl, si se activa | 27,5 GB | 60 % | Residente; deja 18 GB de margen |
| Por lotes: qwen3.6 q8 | 38,7 GB | 84 % | Solo en *builds*; desaloja lo anterior mientras dura |

> 📌 **Propuesta — toca una nota de diseño existente.** Que el reparador de la ruta interactiva sea **el
> modelo que ya está residente** (gemma4), y que qwen3.6 siga reparando solo dentro de los *builds*, que ya
> toleran minutos. Elimina el único intercambio de pesos que un usuario puede provocar sin querer.
>
> Esto matiza la nota de `config.py` según la cual `REPAIR_LLM` es compartido a propósito «porque reparar
> JSON mal formado es el mismo trabajo en todas partes». El trabajo sí es el mismo; lo que cambia es que
> **una de esas llamadas tiene a alguien esperando delante y la otra no**. Como cada llamante ya pasa el
> reparador explícitamente, el cambio es un argumento por llamada, no un refactor — pero es tu decisión
> documentada y por eso aparece aquí como propuesta, no como hecho.

#### Alternativas consideradas

| Opción | Coste | A favor | En contra |
| --- | --- | --- | --- |
| **A · Tu A40 actual** ✅ *elegida* | 0 € | Modelos ya descargados y validados; cero cambios de código; sin límites de tokens. | Punto único de fallo si además aloja la web — por eso la web no vive ahí (§3). |
| **B · GPU alquilada 24/7** | 250–600 €/mes | Idéntico a A, sin depender de la universidad. | Coste desproporcionado: la GPU estará ociosa el 95 % del tiempo. |
| **C · GPU serverless** ❌ | por segundo | Pagas solo lo que ejecutas; encaja con *builds* largos y esporádicos. | Arranque en frío cargando 20–40 GB desde volumen de red: minutos. Inaceptable para «genera un ejercicio». |
| **D · Endpoint gestionado de pesos abiertos** ❌ *descartada* | céntimos/uso | Cero operación, escala sola, latencia estable. `inference.py` ya es la frontera. | Choca con la decisión cerrada «solo Ollama local». Además ningún proveedor sirve exactamente tus *tags*: habría que revalidar los prompts. |
| **E · Modelos más pequeños** | — | Un stack que quepa entero en 24 GB elimina los intercambios de pesos. | Es un cambio de calidad, no de infraestructura: habría que rehacer las mediciones. |

> ✅ **Decisión tomada: opción A, sin plan B externo.** La regla «solo open-source, Ollama local» se
> mantiene en su lectura estricta. La consecuencia a asumir conscientemente: **la capacidad total del
> sistema es la de una GPU**. No escala añadiendo dinero, solo repartiendo mejor el turno. Con un grupo
> cerrado de profesores es viable, pero convierte §7 en parte del producto y no en un detalle de
> implementación.

### 2.2 · Unidad de aislamiento: usuario o workspace

Un *workspace* es una instancia completa: su corpus, su grafo, su perfil de contenido, su banco, sus
cachés y sus generaciones.

> ✅ **Decisión tomada: workspace de primera clase, con miembros y roles.** Siendo los usuarios un grupo
> cerrado de profesores, compartir instancia deja de ser hipotético: dos profesores de la misma asignatura
> querrán el mismo grafo y el mismo banco, y uno solo debería poder verlo sin poder reconstruirlo. Eso son
> exactamente `owner` / `editor` / `viewer`.

### 2.3 · Dónde está la verdad de los artefactos

| Opción | A favor | En contra |
| --- | --- | --- |
| Solo ficheros, un directorio por workspace | Cambio mínimo: el código ya funciona así. | Sin transacciones, sin historial consultable, backup = tar del disco, imposible escalar a dos máquinas. |
| Solo Postgres | Una sola copia de seguridad, versionado y permisos gratis. | Builders y embedder son de fichero (Docling, `.npz`, caché de markdown): habría que interponer una capa de ficheros virtual. |
| **Híbrido** ✅ | Postgres manda en lo pequeño y estructurado (grafo 48 KB, banco 92 KB, perfil 5 KB, aprobaciones, generaciones). Objetos para lo grande y binario. El worker materializa un directorio de trabajo por trabajo y lo vuelve a subir. | Hay que escribir el materializador (~150 líneas) y decidir bien qué es regenerable. |

Que el híbrido funcione depende de un detalle ya cierto: *las cachés son regenerables*. Los `.npz` se
invalidan solos por huella MD5 y el markdown de Docling se rehace. Si se pierden, cuestan tiempo, no datos
— así que no necesitan respaldo, solo almacenamiento.

---

## 3. Arquitectura objetivo

```
┌─ NAVEGADOR ─────────────────────────────────────────────────────────┐
│  SPA React (la actual + login y selector de workspace)              │
│  Cookie de sesión · httpOnly · Secure · SameSite=Lax                │
└─────────────────────────────────────────────────────────────────────┘
             │  HTTPS + WSS · mismo origen · sin CORS en producción
             ▼
┌─ PLANO DE CONTROL · VPS ~7 €/mes · siempre encendido ───────────────┐
│  Caddy       TLS automático, HSTS, cabeceras                        │
│  FastAPI     Auth, artefactos, cola, WebSocket filtrado             │
│  PostgreSQL  Usuarios, workspaces, artefactos, trabajos, generac.   │
│  Objetos     PDF/DOCX crudos, .npz, markdown                        │
└─────────────────────────────────────────────────────────────────────┘
             ▲  el worker SALE hacia aquí: pide trabajo,
             │  publica progreso, sube resultados
┌─ PLANO DE CÓMPUTO · caja con la A40 · puede apagarse ───────────────┐
│  Worker      Materializa el workspace, ejecuta stages, reporta      │
│  Ollama      localhost:13434                                        │
│  NVIDIA A40  46 GB · un trabajo cada vez                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Por qué el worker sale y no recibe

- **Cero configuración de red.** La caja de la GPU casi seguro está detrás de NAT o de un cortafuegos
  universitario. Saliendo, no hay que pedir nada a nadie.
- **Superficie de ataque mínima.** Ollama no expone autenticación: publicarlo en internet es regalar una
  GPU. Con el worker saliendo, Ollama nunca sale de `localhost`.
- **Degradación honesta.** Si la caja se apaga, la web sigue: los usuarios ven sus artefactos y su
  historial, y los trabajos nuevos se quedan en cola con un aviso claro en vez de dar error 500.
- **Sustituible.** El mismo worker corre en un pod alquilado, o en dos cajas a la vez, sin tocar el plano
  de control.

La alternativa —**Cloudflare Tunnel** desde la caja de la GPU exponiendo el FastAPI entero— es más rápida
de montar (una tarde, URL HTTPS incluida) y válida para una demo. Su problema es que fusiona los dos
planos: cuando se apaga la GPU, se cae la web y con ella el acceso a los datos de todos los usuarios.
Sirve como **paso intermedio**, no como destino.

---

## 4. Base de datos

**PostgreSQL 16**, con SQLAlchemy 2.0 (declarativo, tipado) y Alembic para migraciones. No hace falta ORM
asíncrono: las rutas de la API son consultas cortas y el trabajo pesado ya está fuera del proceso web.

### Esquema

| Tabla | Contenido | Por qué así |
| --- | --- | --- |
| `users` | `email citext unique`, `password_hash`, `email_verified_at`, `disabled_at`, `created_at` | `citext` evita el duplicado por mayúsculas. Nunca se guarda la contraseña, solo el hash Argon2id. |
| `sessions` | `token_hash`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, `revoked_at`, `ip`, `user_agent` | Sesión opaca en servidor: revocable al instante, lo que un JWT no permite. Se guarda el SHA-256, no el token. |
| `invites` | `token_hash`, `email`, `workspace_id` (opcional), `role`, `created_by`, `expires_at`, `used_at`, `used_by` | El alta es por invitación, no por registro público. Puede crear cuenta nueva o sumar a alguien a un workspace existente. Un solo uso, con caducidad. |
| `workspaces` | `slug`, `name`, `owner_id`, `deleted_at` | La unidad de aislamiento. Todo lo demás cuelga de aquí. |
| `memberships` | `(workspace_id, user_id)`, `role` | La autorización se reduce a una consulta: ¿existe fila y qué rol tiene? |
| `artifacts` | `workspace_id`, `kind`, `stage` (`draft`/`curated`), `version`, `content jsonb`, `sha256`, `created_by` | Sustituye a los ficheros y al `.history/`. Versionar por filas da historial y *deshacer* gratis, y respeta que borrador y curado son dos cosas distintas. |
| `approvals` | `workspace_id`, `kind`, `artifact_id`, `upstream_hashes jsonb`, `approved_by`, `approved_at` | Traducción directa de `.review_state.json`: la lógica de «obsoleto porque cambió lo de arriba» se conserva tal cual. |
| `raw_documents` | `workspace_id`, `slot` (`corpus`/`exemplars`), `filename`, `bytes`, `sha256`, `object_key` | El fichero va a objetos; los metadatos a la BD, que es lo que la UI lista y lo que las cuotas cuentan. |
| `jobs` | `workspace_id`, `kind`, `class` (`interactive`/`batch`), `params jsonb`, `status`, tiempos, `error`, `result jsonb`, `created_by`, `worker_id` | Persistir la cola es lo que permite reiniciar el servidor sin perderla y que el worker viva en otra máquina. |
| `job_events` | `(job_id, seq)`, `ts`, `kind`, `payload jsonb` | Los `.runs/*.jsonl`. El `seq` monotónico que ya usa el bus para el `?since=N` se convierte en clave primaria. |
| `generations` | `workspace_id`, `job_id`, `concepts text[]`, `fixed jsonb`, `curriculum text[]`, `instructions`, `item jsonb`, `thinking`, `created_at` | Qué generó cada usuario y con qué parámetros. Con `item` en `jsonb` sobrevive a cambios del perfil de contenido. |
| `concept_descriptions` | `(workspace_id, concept)`, `text`, `fingerprint` | Hoy es `cache/concept_descriptions.json`. Es caro de regenerar (modelo de 39 GB) y editable a mano: merece BD, no caché. |
| `blobs` | `workspace_id`, `kind`, `fingerprint`, `object_key` | Punteros a los `.npz` y al markdown. Regenerables: no entran en la copia de seguridad. |
| `audit_log` | `actor_id`, `workspace_id`, `action`, `target`, `at`, `ip` | Quién aprobó qué y quién borró qué. Barato de escribir e imposible de reconstruir después. |
| `quotas` / `usage` | `workspace_id`, contadores por día | Bytes subidos, builds, generaciones. Sin esto, un solo usuario puede monopolizar la GPU (§7). |

### Decisiones concretas

- **Artefactos como `jsonb`, no como ficheros.** Son pequeños y así el aprobado, la versión y el hash se
  escriben en la misma transacción que el contenido. Restaurar la BD restaura la instancia entera.
- **Nada de pgvector, todavía.** El embedder hace coseno exacto en NumPy sobre ~150 conceptos y unos
  cientos de ítems: microsegundos, en memoria. Una extensión más, una migración más y una segunda fuente
  de verdad, a cambio de nada. Se replantea si algún banco pasa de decenas de miles de ítems.
- **`ON DELETE CASCADE` desde `workspaces`** hacia todo lo demás, más un borrado de objetos: es lo que
  hace que «borra mi cuenta» sea una operación real y no una promesa (§9).
- **Migración inicial**: un comando `variant-generator import-instance` que cargue tu `instance/` actual
  como *workspace* nº 1. Sin él, la primera versión desplegada nace vacía y pierdes el grafo ya curado.

---

## 5. Login seguro

> ✅ **Decidido: contraseña propia, sin OAuth ni IdP externo, y alta solo por invitación.** Esa última parte
> no es un detalle: **eliminar el registro público quita de en medio la superficie de ataque más grande de
> cualquier web con login**. Sin ella no hacen falta captcha, ni verificación de correo como barrera
> antispam, ni cuotas defensivas contra altas masivas. Lo que queda es un módulo de autenticación pequeño
> y auditable.

### Alternativas consideradas

| Opción | Qué te da | Qué cuesta |
| --- | --- | --- |
| **A · Sesiones propias sobre Postgres** ✅ *elegida* | Control total, cero servicios extra, y un capítulo de la memoria que puedes escribir y defender. Encaja con el espíritu open-source. | Escribir verificación de correo, recuperación, limitación de intentos y rotación de sesión. ~400 líneas bien conocidas, no investigación. |
| **B · `fastapi-users`** | Registro, verificación, *reset*, OAuth y adaptador de SQLAlchemy ya hechos. | Adoptas su modelo de usuario y su ritmo de versiones. Ahorra ~1 semana y te quita el control sobre el detalle que más querrías explicar. |
| **C · IdP autoalojado** (Zitadel, Authentik, Keycloak) ❌ | OIDC completo, MFA, panel de administración, puerta al SSO de la universidad. Todos open-source. | Otro servicio que operar y una integración que no aporta nada si nadie va a usar SSO. |
| **D · IdP gestionado** (Auth0, Clerk, Supabase) ❌ | Funciona esta tarde. | Un tercero cerrado en la ruta de los datos personales, en un proyecto cuya decisión estructural es «solo open-source». |

### Diseño, al detalle

#### Alta por invitación

- No existe `POST /api/auth/register` abierto: el alta consume un **token de invitación de un solo uso**,
  guardado hasheado, con caducidad de días y opcionalmente atado a un correo concreto.
- Quien invita es el `owner` de un workspace (para sumar a un colaborador) o un administrador (para crear
  una cuenta nueva con su propio workspace).
- La primera cuenta —la tuya— se crea por línea de comandos, no por la web:
  `variant-generator-server create-user`. Así no hay ningún momento en que el sistema acepte registros sin
  credenciales.
- La verificación de correo deja de ser una barrera antispam y pasa a ser solo lo que hace fiable la
  recuperación de contraseña. Sigue mereciendo la pena, pero no bloquea el despliegue.

#### Credenciales

- **Argon2id** vía `argon2-cffi` (o `pwdlib[argon2]`), con parámetros mínimos `t=3, m=64 MiB, p=4`,
  ajustados a que una verificación tarde ~100–250 ms en el VPS. El hash guarda sus propios parámetros, así
  que subirlos más adelante es transparente.
- **Mínimo 12 caracteres y comprobación contra contraseñas filtradas** (rango *k-anonymity* de HIBP, o
  `zxcvbn` en local), en vez de reglas de composición: es lo que recomienda el NIST y lo que de verdad
  reduce el riesgo.
- **Respuestas idénticas** para «ese correo no existe» y «contraseña incorrecta», y tiempo de respuesta
  similar en ambos casos, para no filtrar qué cuentas existen.

#### Sesión

- Token opaco de `secrets.token_urlsafe(32)`; en la BD solo su SHA-256. Si te roban un volcado de la base,
  no obtienen sesiones utilizables.
- Cookie `httpOnly; Secure; SameSite=Lax; Path=/`. Caducidad deslizante de 7–14 días y absoluta de 30.
  **Rotación del identificador** al iniciar sesión y al cambiar la contraseña; revocación en logout y un
  botón «cerrar sesión en todos los dispositivos».
- `SameSite=Lax` basta porque `app.py` ya sirve la SPA desde el mismo origen. Corolario obligatorio:
  **quitar el CORS permisivo en producción** — hoy `allow_origins` apunta al servidor de Vite; con cookies
  eso debe quedar restringido a desarrollo.
- **CSRF**: mismo origen + `SameSite=Lax` + exigir cabecera `Origin` (o `Sec-Fetch-Site: same-origin`) en
  todo método que mute estado. Si quieres cinturón y tirantes, *double submit* con token por sesión.

#### WebSocket — **crítico**

- La cookie viaja en el *handshake*: autentica **antes** de `accept()` y cierra con código 4401 si no hay
  sesión válida.
- Suscribe cada conexión **solo a los eventos de los workspaces del usuario**. Esto implica que
  `EventBus.publish()` pase a llevar `workspace_id`, y que el filtro esté en el servidor, no en el cliente.
  Hoy el filtrado por `job_id` lo hace el navegador —está documentado como decisión— y con varios usuarios
  deja de ser aceptable.

#### Alrededor

- **Limitación de intentos** por IP y por cuenta en login, canje de invitación y recuperación (p. ej. 5/min
  con retroceso exponencial y bloqueo temporal). En un solo proceso vale un contador en Postgres o en
  memoria; no hace falta Redis todavía.
- **Verificación de correo y recuperación** con tokens de un solo uso, guardados hasheados, TTL de 30–60
  minutos, invalidados al usarse. Para enviar: Resend, Postmark o el SMTP de la universidad — con un grupo
  cerrado, el volumen cabe en cualquier plan gratuito.
- **Cabeceras**: HSTS y TLS los pone Caddy; añade CSP (la SPA es estática, así que se puede fijar sin
  `unsafe-inline`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
  `X-Frame-Options: DENY`.
- **Autorización en cada ruta**, no solo autenticación: una dependencia `require_member(workspace_id, role)`
  por la que pasen *todos* los endpoints de artefactos, crudos, trabajos y generaciones. El error clásico
  aquí no es el login, es un `GET /api/kg?workspace=otro` que nadie comprobó.
- **TOTP opcional** (`pyotp` + códigos de recuperación) si quieres que la seguridad sea un punto fuerte de
  la defensa. Sobre este diseño son un par de tardes.
- **Secretos** (`SECRET_KEY`, credenciales de BD, SMTP) por variables de entorno, nunca en el repositorio.

> **Por qué no JWT.** Un JWT sin estado no se puede revocar, obliga a inventar refresco y listas negras, y
> acaba guardado en `localStorage`, que es accesible desde JavaScript y por tanto desde cualquier XSS. Aquí
> no aporta nada: hay un único backend con base de datos, así que una sesión en servidor es más simple *y*
> más segura.

---

## 6. Refactor del núcleo

La buena noticia medida sobre el código: las constantes de ruta se referencian en **~40 sitios repartidos
por 15 módulos**, y todos son fronteras (etapas, constructores de cargadores, módulos del servidor). Los
componentes —embedder, tagger, generador— ya reciben objetos y rutas por parámetro.

### Paso 1 · `Workspace` como dato

```python
# variant_generator/workspace.py
@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def instance_dir(self) -> Path: ...
    @property
    def kg_path(self) -> Path: ...
    @property
    def kg_autogenerated_path(self) -> Path: ...
    @property
    def exemplars_bank_path(self) -> Path: ...
    @property
    def content_profile_path(self) -> Path: ...
    @property
    def raw_corpus_dir(self) -> Path: ...
    @property
    def raw_exemplars_dir(self) -> Path: ...
    @property
    def cache_dir(self) -> Path: ...
```

`config.py` conserva modelos, umbrales y el host de Ollama —que son configuración global de verdad— y
expone `default_workspace()` apuntando a `PROJECT_ROOT`. Las firmas pasan a `initialize(ws=None)`,
`build_artifact(artifact, ws=None)`, resolviendo a la de por defecto: **la CLI no cambia ni una línea**,
que es el contrato de la librería.

**Módulos a tocar:** `stages/_artifacts.py` · `stages/initialize.py` · `stages/build.py` · `stages/tag.py`
· `embedder.py` · `exemplars_bank.py` · `builders/knowledge_graph_builder.py` ·
`builders/_source_docs.py` · `server/settings.py` · `server/review.py` · `server/raw_data.py` ·
`server/editors/bank_edit.py` · `server/editors/kg_edit.py` · `server/routers/health.py` ·
`server/jobs/build_process.py` y `build_worker.py` (que gana un argumento `--workspace`).

### Paso 2 · Registro de contextos en lugar de un global

`deps.py` pasa de una variable a un registro con LRU y caducidad, con invalidación por workspace. El
límite no lo pone la memoria —los dos `.npz` actuales suman 3,3 MB, y los vectores ya son `float32`— sino
el tiempo de reconstrucción: mantener calientes 8–16 contextos es trivial en RAM y evita minutos de
espera.

### Paso 3 · Eventos con dueño

`EventBus.publish(workspace_id, job_id, kind, payload)`, `workspace_id` en `Event`, y el filtro en el
servidor. El `seq` monotónico y el `?since=N` se mantienen intactos: siguen siendo la respuesta correcta a
«recargué la pestaña en mitad de un build».

### Paso 4 · Trabajos persistidos

`Job` deja de vivir en un diccionario del runner y pasa a `jobs`. El runner se convierte en ejecutor: toma
el siguiente trabajo elegible con `SELECT … FOR UPDATE SKIP LOCKED`, que es la forma sencilla de tener una
cola correcta en Postgres sin añadir Redis ni Celery. Al arrancar, los trabajos que quedaron en `running`
se reencolan si son idempotentes (los tres *builds*, `tag`, `generate`) o se marcan como fallidos.

### Paso 5 · Materializador de workspace

El worker recibe un `job_id`, resuelve su workspace, escribe en un directorio temporal los artefactos desde
la BD y los crudos desde objetos, ejecuta la etapa exactamente igual que hoy, y sube de vuelta el
resultado. Es la pieza que hace que el plano de cómputo sea desechable.

### Paso 6 · Cuotas y límites

Bytes por workspace, número de *builds* al día, generaciones al día, tamaño máximo de corpus. Se comprueban
al aceptar la subida y al encolar, nunca solo en el cliente.

> ⚠ **Cuidado.** El *warm start* entre ejecuciones es una decisión de diseño explícita: se etiqueta *antes*
> de enriquecer el índice, de modo que el índice de una ejecución alimenta la siguiente. Al pasar las
> cachés a objetos, hay que conservar esa secuencia y el hash por ítem del banco. Si se pierde, no se rompe
> nada visible — simplemente empeora la calidad del etiquetado, en silencio.

---

## 7. Cola, equidad y cuotas

Con una sola GPU, un trabajo cada vez y sin proveedor externo al que derivar carga, la aritmética es dura:
un *build* de grafo de ~15 minutos deja a todos los demás sin generar durante ese cuarto de hora. Es **el
principal problema de producto** del despliegue multiusuario, y no se arregla con más código: se arregla
decidiendo.

La buena noticia del perfil de uso elegido: con un grupo cerrado de profesores, los *builds* son
acontecimientos —uno por asignatura y cuatrimestre— y lo frecuente son generaciones de segundos. La cola
será casi siempre de longitud cero. Lo que hay que evitar es que las pocas veces que no lo sea, el sistema
parezca colgado.

| Estrategia | Cuándo | Coste |
| --- | --- | --- |
| **Cola única + espera honesta** ✅ *v1* | Siempre. La UI muestra puesto en cola y estimación basada en la duración media real de cada tipo de trabajo. | Casi nada: los datos ya están en `jobs`. Es el mínimo aceptable. |
| Dos clases: interactiva y por lotes | En cuanto haya más de dos o tres usuarios. Las generaciones adelantan a los builds; los builds ceden el turno en sus *checkpoints* por chunk, que ya existen. | Moderado, y encaja con la maquinaria actual de cancelación cooperativa. |
| Segunda GPU a demanda solo para builds | Si los builds se vuelven frecuentes. El plano de cómputo ya admite varios workers. | ~0,40–0,80 $/h mientras esté encendida. |
| Un build por workspace y máximo N en el sistema | Siempre. Impide que una cuenta encole diez builds. | Trivial: una comprobación al encolar. |

La UI ya tiene casi todo lo necesario: la barra ponderada de `build.progress` con porcentaje honesto, la
línea de detalle en vivo y el botón de cancelar. Lo que falta es la **espera**: «eres el 3.º de la cola,
faltan ~22 minutos» es información que el sistema tiene y hoy no enseña.

---

## 8. Dónde alojarlo

### Plano de control

| Plataforma | Precio | A favor | En contra |
| --- | --- | --- | --- |
| **Hetzner Cloud CX32** ✅ | ~7 €/mes | 4 vCPU, 8 GB, 80 GB NVMe. Centros en Alemania y Finlandia: RGPD sin discusión. Docker Compose + Caddy, control total, WebSockets sin límites artificiales, sin suspensión por inactividad. | Administras tú el sistema: actualizaciones, cortafuegos, copias. |
| Fly.io | ~5–25 $/mes | Despliegue por `fly deploy`, TLS y regiones incluidos. | Procesos largos, volúmenes persistentes y WebSockets requieren cuidado; el Postgres gestionado encarece. |
| Railway / Render | ~7–20 $/mes | Lo más cómodo: git push y ya. Postgres de un clic. | El plan gratuito de Render **duerme** tras 15 minutos: mata el contexto caliente y corta el WebSocket. Con el de pago desaparece la ventaja de precio. |
| Servidor de la universidad | 0 € | Gratis, y posible integración con el SSO institucional. | Depende de burocracia y de que te den puerto 443 y un nombre DNS. Merece la pena preguntar antes de pagar nada. |

### Base de datos y objetos

- **Postgres en el mismo VPS**, en contenedor, con `pg_dump` diario cifrado fuera de la máquina. Es lo más
  barato y lo más rápido; el volumen de datos es minúsculo. *Alternativa*: Neon (plan gratuito de 0,5 GB) o
  Supabase, útiles si prefieres no operar la BD — a cambio de latencia extra si no están en la misma
  región.
- **Objetos**: al principio, disco del VPS. Con 20 MB por workspace, 100 workspaces son 2 GB. Cuando
  moleste, MinIO en el mismo host o Hetzner Storage Box (~3,20 €/TB) / Backblaze B2, que además sirven de
  destino de las copias.

### Plano de cómputo

| Opción | Precio | Nota |
| --- | --- | --- |
| **Tu A40 con worker saliente** ✅ | 0 € | Modelos ya descargados, `OLLAMA_KEEP_ALIVE=24h` y 46 GB de VRAM. Nada que migrar. |
| RunPod / Vast.ai, A40 o A6000 48 GB a demanda | ~0,25–0,80 $/h | Enciendes para builds y para la defensa. Comprueba dónde está el centro de datos si va a haber datos personales. |
| Hetzner GEX44 (RTX 4000 SFF, 20 GB) ❌ | ~184 €/mes | No cabe qwen3.6 de 38,7 GB, y gemma4 q4 con 19,9 GB queda al filo. Solo tras rebajar el stack de modelos. |
| Scaleway / OVHcloud (L40S, L4) | ~0,75–1,40 €/h | Dentro de la UE, factura en euros. Caro para 24/7, razonable a demanda. |

> ✅ **Elección: Hetzner Cloud CX32 + Caddy + Postgres en el mismo host, y tu A40 como worker saliente.**
> Unos 7 €/mes, datos en la UE, sin cold starts, WebSockets sin restricciones y una única máquina que
> administrar.

---

## 9. Seguridad más allá del login

### Documentos subidos

- Docling y torch abriendo PDF y DOCX de terceros es **superficie de ataque real**. El build ya corre fuera
  de proceso; en producción, además, en su propio contenedor: sin red salvo hacia Ollama, usuario sin
  privilegios, sistema de ficheros de solo lectura excepto su directorio de trabajo, y límites de CPU,
  memoria y tiempo.
- Verifica el tipo real por *magic bytes*, no solo la extensión: hoy se comprueba el sufijo del nombre. La
  sanitización del nombre de fichero ya evita el recorrido de rutas — eso está bien resuelto.
- Cuota agregada por workspace y número máximo de ficheros, además del límite por archivo.

### Inyección de *prompt* desde el corpus

Un PDF subido entra literalmente en los prompts del extractor de grafo. Puede contener «ignora las
instrucciones anteriores y…». Mitigación realista, por capas: el daño queda **confinado al propio
workspace** del que sube el fichero —otra razón para que el aislamiento sea real—; el modelo no tiene
herramientas ni acceso a red; y toda salida se valida contra esquema con `parse_with_repair`, que ya está
en su sitio. Añade dos cosas: **activar el guardarraíl** que ya está configurado
(`granite4.1-guardian`, criterios *harm* y *jailbreak*) en la ruta pública, y no renderizar jamás como HTML
el texto generado — React protege por defecto, así que basta con no introducir `dangerouslySetInnerHTML`.

### Datos personales, ajustado a un grupo cerrado

Los usuarios son profesores identificados, no alumnos, y no se procesan datos de estudiantes: el listón
baja bastante, pero no a cero — un correo electrónico ya es un dato personal.

- **Imprescindible**: minimización (correo y contraseña, nada más), aviso de privacidad breve, **borrado
  real en cascada** por cuenta y por workspace incluidos los objetos, alojamiento en la UE (Hetzner cumple)
  y copias cifradas.
- **Recomendable**: cifrado del disco en reposo en el VPS y una nota sobre cuánto se conservan los *logs*
  de ejecución, que contienen fragmentos del material subido.
- **Aplazable**: exportación de datos del usuario y registro formal de actividades de tratamiento. Con un
  grupo cerrado e invitado, esto se resuelve por correo mientras el sistema sea del tamaño que es.
- **No aplazable aunque el grupo sea pequeño**: los apuntes que se suben son propiedad intelectual de
  terceros. Unos términos de uso de un párrafo sobre qué se puede subir y qué hace el sistema con ello —
  importa más aquí que la parte de datos personales.

---

## 10. Operación

### Empaquetado

Dos imágenes, no una. La de la **API**: *multi-stage* con Node para compilar la SPA, `uv` para instalar el
paquete con el extra `server`, y una base *slim* — **sin torch**. La del **worker**: el extra `builders`,
con los ~540 MB de Docling. Esa separación de dependencias ya está declarada en `pyproject.toml`; el
despliegue solo tiene que respetarla.

```
# docker-compose.yml (plano de control)
caddy      → TLS, cabeceras, proxy inverso a api
api        → uvicorn server.app:app, migra con Alembic al arrancar
postgres   → volumen persistente
minio      → opcional; al principio, disco

# en la caja de la GPU
worker     → sale hacia el plano de control; habla con ollama en localhost
```

### Integración continua

GitHub Actions sobre el repositorio que ya existe: `uv sync`, `ruff`, `tsc --noEmit`, `vite build`,
construcción de imágenes y despliegue por SSH. Añade una prueba de humo que arranque la app con una BD
vacía y compruebe `/health` — barata y detecta el 80 % de los despliegues rotos.

### Copias de seguridad

`pg_dump` diario cifrado a Storage Box o B2, con retención de 30 días y **una restauración de prueba** —
una copia sin restaurar no es una copia. Los objetos crudos, semanales. Los `.npz` y el markdown, **no se
respaldan**: son regenerables por diseño.

### Observabilidad

Loguru ya emite todo lo relevante; en producción, sink JSON a stdout. Métricas mínimas que de verdad se van
a mirar: longitud de cola y espera p95, duración por tipo de trabajo, VRAM y temperatura de la GPU, 5xx, y
**tasa de ítems generados que no validan contra el esquema** — esa última es una métrica de calidad del
producto, no de infraestructura, y es la que dirá si un cambio de modelo mejora o empeora. Amplía el
`/health` que ya existe con estado de BD, de cola y del worker de GPU.

---

## 11. Fases

Cada fase deja el sistema desplegable y utilizable. Si el plazo se acorta, se corta por el final, no por la
mitad.

### Semana 1 — Cimientos, todavía sin usuarios

Postgres, SQLAlchemy y Alembic. Modelos de `workspaces`, `artifacts`, `approvals`, `raw_documents`.
`Workspace` como dato y los ~40 usos de rutas migrados. Comando de importación de tu instancia actual.

**Sale**: la misma app de un usuario, pero sin rutas globales y con los datos en base de datos. La CLI
intacta.

### Semana 2 — Identidad

Usuarios, sesiones, login, invitaciones de un solo uso, alta de la primera cuenta por CLI, recuperación de
contraseña. Dependencia de autorización en *todas* las rutas. WebSocket autenticado y filtrado por
workspace. CORS fuera de producción. Limitación de intentos.

**Sale**: multiusuario correcto, con miembros y roles por workspace.

### Semana 3 — Multiusuario de verdad

Registro de contextos con LRU. Trabajos en base de datos con `SKIP LOCKED`. Worker separado con
materializador de workspace. Cuotas. Puesto en cola y estimación en la UI.

**Sale**: dos personas trabajando a la vez sin pisarse ni quedarse a ciegas.

### Semana 4 — Despliegue

Dockerfiles, Compose, Caddy y dominio con TLS. Worker corriendo en la caja de la A40. Copias de seguridad
con restauración probada. CI.

**Sale**: URL pública que puedes enseñar.

### Semana 4½ — Endurecimiento (recortado)

Lo que sigue siendo obligatorio con profesores invitados: **aislamiento del contenedor de build** —suben
PDF de terceros—, validación por *magic bytes*, cabeceras de seguridad, borrado en cascada y los términos
de uso. Se aplaza: guardarraíl en producción, exportación de datos y prueba de carga formal; con 5–10
cuentas conocidas, basta con un ensayo manual de dos personas generando mientras corre un build.

**Sale**: algo que se puede abrir al grupo sin cruzar los dedos.

---

## 12. Lo que no haría

- **Kubernetes.** Dos máquinas y un contenedor por servicio. Compose sobra y se entiende de un vistazo.
- **Microservicios.** El único corte que importa —API frente a worker de GPU— ya está hecho y es un límite
  de proceso, no de red.
- **Celery o Redis.** Postgres con `SKIP LOCKED` hace de cola perfectamente a esta escala, y evita un
  servicio más que respaldar y vigilar.
- **pgvector.** Todavía no resuelve ningún problema que tengas.
- **JWT en `localStorage`.** Ver §5.
- **GPU serverless para la ruta interactiva.** Los arranques en frío con 20–40 GB de pesos no son
  compatibles con una web que responde.
- **Reescribir la SPA.** Login, selector de workspace e indicador de cola son aditivos; el visor de grafo y
  los editores no se tocan.
- **Romper la CLI.** Es el contrato de la librería y lo que hace el proyecto reutilizable por terceros; el
  parámetro `ws` siempre tiene valor por defecto.

---

## 13. Lo que queda por decidir

Las cuatro grandes están resueltas (§0). Quedan tres, y ninguna bloquea empezar por la fase 1.

1. **¿Un profesor puede tener varios workspaces, o exactamente uno?** Cambia la navegación de la SPA: con
   uno solo, el workspace es implícito y no hace falta selector. Un profesor con dos asignaturas es el caso
   que decide. El esquema lo soporta en ambos casos, así que se puede posponer hasta la fase 2.

2. **¿Fecha de defensa?** Si el plazo aprieta, la fase 3 (contextos LRU, cola en base de datos, cuotas) es
   la que admite recortes: con cinco profesores que rara vez coinciden, la cola en memoria actual aguanta,
   a cambio de perderla si reinicias el servidor.

3. **¿Apruebas la propuesta sobre `REPAIR_LLM` (§2.1)?** Separar el reparador interactivo del reparador de
   *builds* matiza una nota de diseño que escribiste a propósito. Sin ese cambio, el despliegue funciona
   igual — pero con parones de minutos cuando un JSON venga mal formado.
