# Mi Briefing 📰

Resumen diario de noticias internacionales para familia y amigos.  
Daily international news briefing — bilingual ES/EN.

**Actualizaciones automáticas:** 6:00 AM ET y 2:00 PM ET todos los días.

---

## Setup en 5 pasos

### 1. Crea el repositorio en GitHub
- Ve a github.com → **New repository**
- Nombre: `mi-briefing` (o el que prefieras)
- Visibilidad: **Public** (necesario para GitHub Pages gratis)
- Inicializa con un README

### 2. Sube los archivos
Copia estos archivos a tu repo:
```
mi-briefing/
├── fetch_news.py
├── .github/
│   └── workflows/
│       └── update.yml
└── docs/
    └── index.html   ← se genera automáticamente
```

Para crear la carpeta `docs/` inicial, puedes crear un archivo vacío `docs/.gitkeep`.

### 3. Activa GitHub Pages
- Ve a tu repo → **Settings** → **Pages**
- Source: **Deploy from a branch**
- Branch: `main` / Folder: `/docs`
- Guarda → en 1-2 minutos tendrás tu URL: `https://tuusuario.github.io/mi-briefing`

### 4. Ejecuta el workflow manualmente la primera vez
- Ve a tu repo → **Actions** → **Update News Briefing**
- Clic en **Run workflow** → **Run workflow**
- Espera ~30 segundos → revisa que se generó `docs/index.html`

### 5. Comparte el link
Tu URL permanente es:
```
https://tuusuario.github.io/mi-briefing
```
Compártelo con tu familia — la página se actualiza sola dos veces al día.

---

## Fuentes de noticias
- **BBC News** — Internacional, Economía, Tecnología, Clima
- **Reuters** — Internacional, Economía, Tecnología  
- **DW Español** — Internacional, Economía (en español)
- **El País** — Internacional (en español)

## Datos económicos
El ticker de precios se puede conectar a APIs gratuitas en una siguiente versión.

---

## Próximos pasos (cuando tengas presupuesto)
- [ ] Resúmenes con IA (Claude API)
- [ ] Indicadores económicos en tiempo real (Alpha Vantage)
- [ ] Suscripciones por email (newsletter)
- [ ] Publicidad (Google AdSense)
