# WhatsApp Print Automation

Automatiza WhatsApp Web en Windows para descargar adjuntos PDF/JPG/JPEG/PNG, registrar el proceso y enviar a impresion solo cuando el mensaje inmediatamente anterior contiene la frase `Hola, quiero imprimir estos documentos`, `LASER` o `COLOR`.

## Arquitectura

- `main.py`: arranque de la aplicacion.
- `config.py`: carga `.env`, rutas y nombres de impresoras.
- `whatsapp/client.py`: sesion persistente con Playwright, deteccion de chats no leidos, descarga de adjuntos.
- `printer/service.py`: impresion de PDF con SumatraPDF e imagenes con GDI/pywin32.
- `printer/queue.py`: cola secuencial con deduplicacion por hash de archivo e impresora.
- `state.py`: SQLite para mensajes procesados y trabajos de impresion.
- `logs/`: log rotativo `whatsapp_printer.log`.
- `pendientes/`: descargas recientes o archivos sin palabra clave.
- `impresos/`: archivos impresos correctamente.
- `errores/`: archivos que fallaron al imprimir.
- `session/`: perfil persistente de Chromium para conservar WhatsApp Web.

## Instalacion

1. Instala Python 3.12 o superior.
2. Abre PowerShell en esta carpeta:

```powershell
cd C:\Users\shols\PycharmProjects\PythonProject3\whatsapp_print_automation
```

3. Crea y activa el entorno virtual. Si tienes Python 3.12 instalado, usa `py -3.12`; si no, usa el Python actual con `python -m venv .venv`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Alternativa:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Instala dependencias:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

5. Crea la configuracion:

```powershell
Copy-Item .env.example .env
notepad .env
```

6. Ajusta `SUMATRA_PATH`, `LASER_PRINTER_NAME` y `COLOR_PRINTER_NAME`.

## SumatraPDF

1. Descarga e instala SumatraPDF desde `https://www.sumatrapdfreader.org/download-free-pdf-viewer`.
2. Revisa la ruta del ejecutable. Normalmente es:

```text
C:\Program Files\SumatraPDF\SumatraPDF.exe
```

3. Copia esa ruta en `.env`:

```text
SUMATRA_PATH=C:\Program Files\SumatraPDF\SumatraPDF.exe
```

## Ejecucion

```powershell
cd C:\Users\shols\PycharmProjects\PythonProject3\whatsapp_print_automation
.\.venv\Scripts\Activate.ps1
python main.py
```

La primera vez se abre WhatsApp Web. Escanea el QR con el telefono. En ejecuciones posteriores se reutiliza la carpeta `session/`.

## Reglas de uso

El sistema imprime si antes del adjunto, en el mismo chat, aparece una de estas instrucciones:

- `Hola, quiero imprimir estos documentos`: impresora predeterminada.
- `LASER`: impresora configurada como `Laser`.
- `COLOR`: impresora configurada como `Color`.

Ejemplo:

```text
Hola, quiero imprimir estos documentos
archivo.pdf
```

La frase no tiene que ser inmediatamente anterior al documento. Si el cliente escribe la frase y se demora en enviar el archivo, la aplicacion guarda una intencion de impresion para ese contacto durante `PRINT_INTENT_WINDOW_MINUTES` minutos, por defecto 10.

Si no existe una instruccion activa, el archivo se descarga en `pendientes/` y queda registrado como `downloaded_no_print_keyword`.

## Servicio al iniciar Windows

Opcion recomendada: Programador de tareas.

1. Configura y prueba primero la aplicacion manualmente.
2. Ejecuta PowerShell como administrador.
3. Instala la tarea:

```powershell
cd C:\Users\shols\PycharmProjects\PythonProject3\whatsapp_print_automation
.\scripts\install_startup_task.ps1
```

La tarea se ejecuta al iniciar sesion. Para verla: abre `taskschd.msc` y busca `WhatsAppPrinterAutomation`.

Alternativa profesional: instalar como servicio con NSSM.

```powershell
nssm install WhatsAppPrinterAutomation
```

En NSSM configura:

- Application path: `C:\Users\shols\PycharmProjects\PythonProject3\whatsapp_print_automation\.venv\Scripts\python.exe`
- Startup directory: `C:\Users\shols\PycharmProjects\PythonProject3\whatsapp_print_automation`
- Arguments: `main.py`

Nota: si se ejecuta como servicio sin escritorio interactivo, el escaneo QR y la ventana de Chromium pueden no verse. Primero inicia sesion manualmente y deja creada la carpeta `session/`.

## Logs

El archivo principal es:

```text
logs\whatsapp_printer.log
```

Cada evento registra fecha, contacto, archivo y estado del proceso.

## Evitar reprocesamiento

El sistema guarda en `data/state.sqlite3`:

- Mensajes ya procesados.
- Trabajos de impresion por hash del archivo e impresora.

Esto evita repetir el mismo mensaje al reiniciar y evita duplicar trabajos de impresion.

## Limitaciones practicas

WhatsApp Web no ofrece una API publica para automatizar descargas. Si WhatsApp cambia atributos internos o textos de botones, puede ser necesario ajustar selectores en `whatsapp/client.py`.

## Mejoras futuras

- Calculo automatico de precios por numero de paginas, color y tipo de papel.
- Respuesta automatica al cliente con confirmacion, precio y estado.
- Panel web de administracion para ver cola, historial, errores y reimpresiones.
- Integracion con base de datos central y multiples sucursales.
- Reglas por contacto, horario, tamaño maximo y bloqueo de remitentes.
- OCR o analisis de PDF para validar formato antes de imprimir.
