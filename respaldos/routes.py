"""
respaldos/routes.py
Módulo de Respaldos y Restauraciones — FourOvenPizza
------------------------------------------------------
• Solo accesible para rol Administrador.
• Las operaciones de BD se ejecutan con el usuario 'backup_agent'.
• Detección automática de mysqldump/mysql en Windows, Linux, macOS,
  XAMPP, WAMP, Laragon y MySQL instalado directamente.
• Respaldo Completo: estructura + datos + vistas + SP + funciones + triggers + eventos.
• Respaldo Incremental: solo filas insertadas/modificadas desde el último respaldo exitoso
  (usando columnas de marca de tiempo: created_at, updated_at, fecha, fecha_hora, etc.).
• Sin uso de ninguna API externa.
"""

from respaldos import respaldos
from flask import (
    render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, current_app
)
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text
from models import db
from functools import wraps
import subprocess, os, re, datetime, platform, shutil, math

# ──────────────────────────────────────────────────────────────
# CONSTANTES DE SEGURIDAD
# ──────────────────────────────────────────────────────────────

BACKUP_BASE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backups'
)
MAX_RESTORE_SIZE = 50 * 1024 * 1024   # 50 MB

TABLAS_PERMITIDAS = {
    'roles', 'usuarios', 'resetcontrasenia', 'intentos_fallidos',
    'categorias', 'proveedores', 'unidadesmedida', 'materiasprimas',
    'mermas', 'detallemerma', 'compras', 'detallecompra', 'productos',
    'ventas', 'detalleventa', 'ventastockreservado', 'ticketventa',
    'detalleticketventa', 'recetas', 'detallereceta', 'ordenesproduccion',
    'detalleproduccion', 'bitacora_accesos', 'bitacora_eventos',
    'bitacora_sistema', 'cajamovimientos', 'cortecaja', 'minirecetas',
    'detalleMiniReceta', 'bitacora_respaldos',
}

# Columnas de marca de tiempo que se usan para filtrar en incrementales.
# Se prueban en orden; se usa la primera que exista en cada tabla.
COLUMNAS_TIMESTAMP = [
    'updated_at', 'created_at', 'modificado_en', 'creado_en',
    'fecha_modificacion', 'fecha_creacion',
    'fecha_hora', 'fecha', 'fechaRegistro',
]

BACKUP_DB_USER = 'backup_agent'
BACKUP_DB_PASS = 'Bk@g3nt_F0urOv3n#2024!'
BACKUP_DB_HOST = '127.0.0.1'
BACKUP_DB_NAME = 'fourovenpizzadb'
BACKUP_DB_PORT = '3306'

# ──────────────────────────────────────────────────────────────
# DETECCIÓN AUTOMÁTICA DE mysqldump / mysql
# ──────────────────────────────────────────────────────────────

_RUTAS_WINDOWS = [
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin",
    r"C:\Program Files\MySQL\MySQL Server 8.4\bin",
    r"C:\Program Files\MySQL\MySQL Server 5.7\bin",
    r"C:\Program Files (x86)\MySQL\MySQL Server 8.0\bin",
    r"C:\Program Files (x86)\MySQL\MySQL Server 5.7\bin",
    r"C:\xampp\mysql\bin",
    r"D:\xampp\mysql\bin",
    r"E:\xampp\mysql\bin",
    r"C:\wamp64\bin\mysql\mysql8.0.31\bin",
    r"C:\wamp64\bin\mysql\mysql8.0.27\bin",
    r"C:\wamp\bin\mysql\mysql5.7.36\bin",
    r"C:\wamp64\bin\mysql\mysql5.7.36\bin",
    r"C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin",
    r"C:\laragon\bin\mysql\mysql-5.7.33-winx64\bin",
    r"C:\laragon\bin\mysql\mysql-8.0\bin",
]

_RUTAS_UNIX = [
    "/usr/bin",
    "/usr/local/bin",
    "/usr/local/mysql/bin",
    "/opt/mysql/bin",
    "/opt/local/bin",
    "/opt/homebrew/bin",
    "/usr/local/opt/mysql/bin",
    "/usr/local/opt/mysql-client/bin",
]


def _buscar_ejecutable(nombre: str) -> str:
    ruta = shutil.which(nombre)
    if ruta:
        return ruta

    es_windows = platform.system() == 'Windows'
    ext = '.exe' if es_windows else ''
    candidatos = _RUTAS_WINDOWS if es_windows else _RUTAS_UNIX

    for carpeta in candidatos:
        ruta_candidata = os.path.join(carpeta, nombre + ext)
        if os.path.isfile(ruta_candidata):
            return ruta_candidata

    if es_windows:
        for raiz in [r"C:\wamp64\bin\mysql", r"C:\wamp\bin\mysql",
                     r"C:\laragon\bin\mysql"]:
            encontrado = _scan_subcarpetas(raiz, nombre + '.exe')
            if encontrado:
                return encontrado

    raise FileNotFoundError(
        f"No se encontró '{nombre}' en el sistema. "
        f"Asegúrate de que MySQL Client Tools esté instalado."
    )


def _scan_subcarpetas(raiz: str, nombre: str) -> str:
    if not os.path.isdir(raiz):
        return None
    try:
        for entrada in os.scandir(raiz):
            if entrada.is_dir():
                candidato = os.path.join(entrada.path, 'bin', nombre)
                if os.path.isfile(candidato):
                    return candidato
    except PermissionError:
        pass
    return None


# ──────────────────────────────────────────────────────────────
# HELPERS GENERALES
# ──────────────────────────────────────────────────────────────

def get_ip():
    return request.headers.get('X-Forwarded-For',
                                request.remote_addr).split(',')[0].strip()


def solo_administrador(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('usuario_id'):
            flash('Debes iniciar sesión.', 'danger')
            return redirect(url_for('autentificacion.login'))
        if session.get('usuario_rol') != 'Administrador':
            flash('No tienes permisos para acceder a esta sección.', 'danger')
            return redirect(url_for('inicio'))
        return f(*args, **kwargs)
    return decorated


def _asegurar_directorio(ruta: str) -> bool:
    try:
        os.makedirs(ruta, exist_ok=True)
        return os.path.isdir(os.path.realpath(ruta))
    except OSError:
        return False


def _nombre_seguro(nombre: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-.]', '_', nombre)[:120]


def _validar_tablas(tablas_lista: list) -> tuple:
    validas, invalidas = [], []
    permitidas_lower = {x.lower() for x in TABLAS_PERMITIDAS}
    for t in tablas_lista:
        t_clean = t.strip().lower()
        if t_clean in permitidas_lower:
            validas.append(t_clean)
        else:
            invalidas.append(t)
    return validas, invalidas


def _obtener_todas_tablas() -> list:
    try:
        filas = db.session.execute(
            text("SELECT table_name FROM information_schema.tables "
                 "WHERE table_schema = :db ORDER BY table_name"),
            {'db': BACKUP_DB_NAME}
        ).fetchall()
        return [f[0] for f in filas]
    except Exception:
        return sorted(list(TABLAS_PERMITIDAS))


def _registrar_inicio(tipo, subtipo, tablas_str, archivo,
                       fecha_ref=None, obs=None) -> int:
    try:
        db.session.execute(
            text("CALL sp_iniciar_respaldo(:tipo,:subtipo,:tablas,:archivo,"
                 ":fecha_ref,:uid,:ip,:obs,@id_resp)"),
            {'tipo': tipo, 'subtipo': subtipo, 'tablas': tablas_str,
             'archivo': archivo, 'fecha_ref': fecha_ref,
             'uid': session.get('usuario_id'), 'ip': get_ip(), 'obs': obs}
        )
        row = db.session.execute(text("SELECT @id_resp")).fetchone()
        db.session.commit()
        return int(row[0]) if row and row[0] else 0
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[RESPALDOS] Error registrando inicio: {e}")
        return 0


def _cerrar_registro(id_resp: int, estado: str,
                      tamano: int = 0, error: str = None):
    try:
        db.session.execute(
            text("CALL sp_cerrar_respaldo(:id,:estado,:tam,:err)"),
            {'id': id_resp, 'estado': estado, 'tam': tamano, 'err': error}
        )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[RESPALDOS] Error cerrando registro: {e}")


def _fmt_tamano(b: int) -> str:
    if b < 1024:       return f'{b} B'
    if b < 1024**2:    return f'{b/1024:.1f} KB'
    if b < 1024**3:    return f'{b/1024**2:.1f} MB'
    return f'{b/1024**3:.2f} GB'


# ──────────────────────────────────────────────────────────────
# DETECCIÓN DE COLUMNA TIMESTAMP POR TABLA
# ──────────────────────────────────────────────────────────────

def _columna_timestamp_de_tabla(tabla: str) -> str | None:
    """
    Devuelve el nombre de la primera columna de tipo fecha/hora que
    exista en 'tabla', buscando en COLUMNAS_TIMESTAMP por orden de
    prioridad. Retorna None si la tabla no tiene ninguna.
    """
    try:
        filas = db.session.execute(
            text(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl "
                "  AND DATA_TYPE IN ('datetime','timestamp','date') "
                "ORDER BY ORDINAL_POSITION"
            ),
            {'db': BACKUP_DB_NAME, 'tbl': tabla}
        ).fetchall()
        db.session.commit()
        cols_en_tabla = {r[0].lower(): r[0] for r in filas}
        for candidato in COLUMNAS_TIMESTAMP:
            if candidato.lower() in cols_en_tabla:
                return cols_en_tabla[candidato.lower()]
        # Si la tabla tiene alguna columna datetime, usar la primera
        if filas:
            return filas[0][0]
    except Exception:
        db.session.rollback()
    return None


# ──────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DE COMANDOS
# ──────────────────────────────────────────────────────────────

def _args_conexion() -> list:
    """Argumentos comunes de conexión para mysqldump / mysql."""
    return [
        f'--user={BACKUP_DB_USER}',
        f'--password={BACKUP_DB_PASS}',
        f'--host={BACKUP_DB_HOST}',
        f'--port={BACKUP_DB_PORT}',
    ]


def _construir_comando_dump_completo(ruta_salida: str) -> list:
    """
    Genera un respaldo completo que incluye:
    - Estructura de todas las tablas (DDL con índices, PKs, FKs)
    - Datos de todas las tablas
    - Vistas
    - Stored Procedures y Funciones
    - Triggers
    - Eventos programados
    """
    exe = _buscar_ejecutable('mysqldump')
    return [
        exe,
        *_args_conexion(),
        '--single-transaction',
        '--skip-lock-tables',
        '--set-gtid-purged=OFF',
        '--column-statistics=0',
        '--routines',          # SP + Funciones
        '--triggers',          # Triggers
        '--events',            # Eventos programados
        '--add-drop-table',    # DROP TABLE IF EXISTS antes de cada CREATE
        '--add-drop-trigger',  # DROP TRIGGER IF EXISTS
        '--result-file', ruta_salida,
        BACKUP_DB_NAME,
    ]


def _construir_comando_dump_parcial(ruta_salida: str,
                                    tablas: list,
                                    solo_datos: bool,
                                    solo_estructura: bool) -> list:
    """
    Respaldo parcial de tablas específicas.
    Los triggers, SP y eventos solo se incluyen si es Estructura+Datos o Solo estructura.
    """
    exe = _buscar_ejecutable('mysqldump')
    cmd = [
        exe,
        *_args_conexion(),
        '--single-transaction',
        '--skip-lock-tables',
        '--set-gtid-purged=OFF',
        '--column-statistics=0',
        '--add-drop-table',
    ]
    if not solo_datos:
        # Incluir triggers de las tablas seleccionadas
        cmd.append('--triggers')
    if solo_datos:
        cmd.append('--no-create-info')
    elif solo_estructura:
        cmd.append('--no-data')

    cmd += ['--result-file', ruta_salida, BACKUP_DB_NAME] + tablas
    return cmd


def _construir_comando_mysql() -> list:
    exe = _buscar_ejecutable('mysql')
    return [exe, *_args_conexion(), BACKUP_DB_NAME]


# ──────────────────────────────────────────────────────────────
# LÓGICA DE RESPALDO INCREMENTAL REAL
# ──────────────────────────────────────────────────────────────

def _generar_incremental(ruta_salida: str,
                          fecha_ref: datetime.datetime,
                          tablas_objetivo: list | None,
                          solo_datos: bool,
                          solo_estructura: bool) -> tuple[bool, str]:
    """
    Genera un archivo SQL con SOLO los datos nuevos/modificados desde fecha_ref.

    Estrategia:
    1. Para cada tabla con columna de timestamp, extrae filas donde
       columna_ts >= fecha_ref usando SELECT ... INTO OUTFILE emulado con
       mysqldump --where.
    2. Si la tabla no tiene columna de timestamp, se omite con una nota
       en el encabezado del archivo (no se puede determinar qué es nuevo).
    3. Si solo_estructura=True, se genera solo el DDL incremental (sin datos),
       que en la práctica equivale a un diff de estructura — incluimos un
       comentario explicativo.

    Retorna (éxito: bool, mensaje_error: str)
    """
    exe_dump = _buscar_ejecutable('mysqldump')
    tablas_a_procesar = tablas_objetivo or _obtener_todas_tablas()
    fecha_str = fecha_ref.strftime('%Y-%m-%d %H:%M:%S')
    ts_gen    = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lineas_cabecera = [
        "-- ============================================================\n",
        f"-- Respaldo Incremental — FourOvenPizzaDB\n",
        f"-- Generado     : {ts_gen}\n",
        f"-- Desde        : {fecha_str}\n",
        f"-- Tablas       : {', '.join(tablas_a_procesar) if tablas_objetivo else 'todas'}\n",
        "-- ============================================================\n\n",
        f"USE `{BACKUP_DB_NAME}`;\n\n",
        "SET FOREIGN_KEY_CHECKS = 0;\n",
        "SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n",
        "SET AUTOCOMMIT = 0;\n",
        "START TRANSACTION;\n\n",
    ]

    tablas_sin_ts   = []
    tablas_con_ts   = []
    tablas_vacias   = []

    # Clasificar tablas
    for tabla in tablas_a_procesar:
        col_ts = _columna_timestamp_de_tabla(tabla)
        if col_ts:
            tablas_con_ts.append((tabla, col_ts))
        else:
            tablas_sin_ts.append(tabla)

    try:
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            f.writelines(lineas_cabecera)

            if tablas_sin_ts:
                f.write("-- ADVERTENCIA: Las siguientes tablas no tienen columna de\n")
                f.write("-- fecha/hora y NO pueden incluirse en un respaldo incremental:\n")
                for t in tablas_sin_ts:
                    f.write(f"--   · {t}\n")
                f.write("\n")

            if solo_estructura:
                # El incremental de estructura no tiene sentido real porque
                # mysqldump no detecta DDL-diff. Incluimos el DDL actual de
                # cada tabla seleccionada como referencia.
                f.write("-- NOTA: El respaldo incremental de Solo Estructura incluye\n")
                f.write("-- el DDL actual de las tablas con columna de timestamp.\n\n")
                for tabla, _ in tablas_con_ts:
                    cmd = [
                        exe_dump, *_args_conexion(),
                        '--no-data', '--skip-triggers',
                        '--set-gtid-purged=OFF', '--column-statistics=0',
                        BACKUP_DB_NAME, tabla,
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, timeout=120)
                    if result.returncode == 0:
                        f.write(result.stdout.decode('utf-8', errors='replace'))
                        f.write("\n")
                    else:
                        err = result.stderr.decode('utf-8', errors='replace').strip()
                        f.write(f"-- ERROR al volcar estructura de {tabla}: {err}\n\n")

            else:
                # Datos nuevos/modificados por tabla
                for tabla, col_ts in tablas_con_ts:
                    clausula_where = (
                        f"`{col_ts}` >= '{fecha_str}'"
                    )
                    cmd = [
                        exe_dump, *_args_conexion(),
                        '--no-create-info',       # Solo INSERT, sin CREATE TABLE
                        '--skip-triggers',
                        '--complete-insert',      # INSERT con nombres de columnas
                        '--single-transaction',
                        '--skip-lock-tables',
                        '--set-gtid-purged=OFF',
                        '--column-statistics=0',
                        f'--where={clausula_where}',
                        BACKUP_DB_NAME, tabla,
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, timeout=300)
                    salida = result.stdout.decode('utf-8', errors='replace')

                    if result.returncode != 0:
                        err = result.stderr.decode('utf-8', errors='replace').strip()
                        f.write(f"-- ERROR volcando {tabla}: {err}\n\n")
                        continue

                    # Detectar si hay datos reales (más que solo comentarios/cabeceras)
                    tiene_inserts = 'INSERT INTO' in salida
                    if tiene_inserts:
                        tablas_vacias_flag = False
                        f.write(f"-- Tabla: {tabla}  |  filtro: {col_ts} >= '{fecha_str}'\n")
                        f.write(salida)
                        f.write("\n")
                        tablas_con_ts_con_datos = True
                    else:
                        tablas_vacias.append(tabla)

            f.write("\nCOMMIT;\n")
            f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

            if tablas_vacias:
                f.write("\n-- Tablas sin registros nuevos desde la fecha de referencia:\n")
                for t in tablas_vacias:
                    f.write(f"--   · {t}\n")

        return True, ''

    except Exception as e:
        return False, str(e)


# ──────────────────────────────────────────────────────────────
# RUTAS
# ──────────────────────────────────────────────────────────────

BITACORA_POR_PAGINA = 20


@respaldos.route('/respaldos', methods=['GET'])
@solo_administrador
def index():
    todas_tablas = _obtener_todas_tablas()
    mysqldump_ok, ruta_dump = True, ''
    try:
        ruta_dump = _buscar_ejecutable('mysqldump')
    except FileNotFoundError:
        mysqldump_ok = False

    return render_template(
        'respaldos/respaldos.html',
        csrf_token=generate_csrf(),
        todas_tablas=todas_tablas,
        mysqldump_ok=mysqldump_ok,
        ruta_dump=ruta_dump,
    )


@respaldos.route('/respaldos/realizar', methods=['POST'])
@solo_administrador
def realizar_respaldo():
    tipo_respaldo = request.form.get('tipo_respaldo', '').strip()
    subtipo       = request.form.get('subtipo', 'Estructura+Datos').strip()
    tablas_sel    = request.form.getlist('tablas')
    observaciones = request.form.get('observaciones', '').strip()[:500]
    dir_destino   = request.form.get('dir_destino', '').strip()

    if tipo_respaldo not in ('Completo', 'Incremental', 'Parcial'):
        return jsonify({'success': False, 'message': 'Tipo de respaldo inválido'})
    if subtipo not in ('Estructura+Datos', 'Solo datos', 'Solo estructura'):
        return jsonify({'success': False, 'message': 'Subtipo inválido'})
    if tipo_respaldo == 'Parcial' and not tablas_sel:
        return jsonify({'success': False,
                        'message': 'Selecciona al menos una tabla para el respaldo parcial'})

    tablas_validas = []
    if tablas_sel:
        tablas_validas, invalidas = _validar_tablas(tablas_sel)
        if invalidas:
            return jsonify({'success': False,
                            'message': f'Tablas no permitidas: {", ".join(invalidas)}'})

    # Directorio destino
    if dir_destino:
        dir_destino = os.path.realpath(dir_destino)
        if not os.path.isabs(dir_destino):
            return jsonify({'success': False, 'message': 'Ruta de destino inválida'})
    else:
        dir_destino = os.path.realpath(BACKUP_BASE_DIR)

    if not _asegurar_directorio(dir_destino):
        return jsonify({'success': False,
                        'message': 'No se pudo crear o acceder al directorio de destino'})

    try:
        _buscar_ejecutable('mysqldump')
    except FileNotFoundError as e:
        return jsonify({'success': False, 'message': str(e)})

    # ── Fecha de referencia para incrementales ──
    fecha_ref = None
    if tipo_respaldo == 'Incremental':
        try:
            db.session.execute(text("CALL sp_fecha_ultimo_respaldo(@f)"))
            r = db.session.execute(text("SELECT @f")).fetchone()
            db.session.commit()
            if r and r[0]:
                fecha_ref = r[0]
        except Exception:
            db.session.rollback()

        if fecha_ref is None:
            return jsonify({
                'success': False,
                'message': (
                    'No existe ningún respaldo exitoso previo. '
                    'Realiza primero un respaldo Completo antes de usar el Incremental.'
                )
            })

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    tipo_abrev = {'Completo': 'full', 'Incremental': 'incr', 'Parcial': 'parcial'}
    nombre_archivo = _nombre_seguro(f"backup_{tipo_abrev[tipo_respaldo]}_{ts}.sql")
    ruta_completa  = os.path.join(dir_destino, nombre_archivo)

    tablas_str = ','.join(tablas_validas) if tablas_validas else None
    id_resp = _registrar_inicio(
        tipo=tipo_respaldo, subtipo=subtipo, tablas_str=tablas_str,
        archivo=ruta_completa, fecha_ref=fecha_ref, obs=observaciones,
    )

    solo_datos      = (subtipo == 'Solo datos')
    solo_estructura = (subtipo == 'Solo estructura')

    # ═══════════════════════════════════════════
    # RESPALDO COMPLETO
    # ═══════════════════════════════════════════
    if tipo_respaldo == 'Completo':
        if subtipo == 'Estructura+Datos':
            # Respaldo completo: estructura + datos + vistas + SP + funciones + triggers + eventos
            cmd = _construir_comando_dump_completo(ruta_completa)
        else:
            # Solo datos o solo estructura (sin routines/events en solo_datos)
            exe = _buscar_ejecutable('mysqldump')
            cmd = [
                exe, *_args_conexion(),
                '--single-transaction', '--skip-lock-tables',
                '--set-gtid-purged=OFF', '--column-statistics=0',
                '--add-drop-table',
            ]
            if subtipo == 'Solo estructura':
                cmd += ['--no-data', '--routines', '--triggers', '--events']
            else:
                cmd += ['--no-create-info', '--skip-triggers']
            cmd += ['--result-file', ruta_completa, BACKUP_DB_NAME]

        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, timeout=600)
        except subprocess.TimeoutExpired:
            _cerrar_registro(id_resp, 'Fallido', error='Timeout')
            return jsonify({'success': False, 'message': 'Tiempo de espera agotado'})
        except Exception as e:
            _cerrar_registro(id_resp, 'Fallido', error=str(e))
            return jsonify({'success': False, 'message': str(e)})

        stderr_txt = result.stderr.decode('utf-8', errors='replace').strip()
        if result.returncode != 0:
            _cerrar_registro(id_resp, 'Fallido', error=stderr_txt)
            return jsonify({'success': False,
                            'message': f'Error en mysqldump: {stderr_txt[:300]}'})

    # ═══════════════════════════════════════════
    # RESPALDO INCREMENTAL REAL
    # ═══════════════════════════════════════════
    elif tipo_respaldo == 'Incremental':
        ok, err_msg = _generar_incremental(
            ruta_salida=ruta_completa,
            fecha_ref=fecha_ref,
            tablas_objetivo=tablas_validas or None,
            solo_datos=solo_datos,
            solo_estructura=solo_estructura,
        )
        if not ok:
            _cerrar_registro(id_resp, 'Fallido', error=err_msg)
            return jsonify({'success': False, 'message': f'Error generando incremental: {err_msg}'})

    # ═══════════════════════════════════════════
    # RESPALDO PARCIAL
    # ═══════════════════════════════════════════
    elif tipo_respaldo == 'Parcial':
        cmd = _construir_comando_dump_parcial(
            ruta_salida=ruta_completa,
            tablas=tablas_validas,
            solo_datos=solo_datos,
            solo_estructura=solo_estructura,
        )
        try:
            result = subprocess.run(cmd, stderr=subprocess.PIPE, timeout=300)
        except subprocess.TimeoutExpired:
            _cerrar_registro(id_resp, 'Fallido', error='Timeout')
            return jsonify({'success': False, 'message': 'Tiempo de espera agotado'})
        except Exception as e:
            _cerrar_registro(id_resp, 'Fallido', error=str(e))
            return jsonify({'success': False, 'message': str(e)})

        stderr_txt = result.stderr.decode('utf-8', errors='replace').strip()
        if result.returncode != 0:
            _cerrar_registro(id_resp, 'Fallido', error=stderr_txt)
            return jsonify({'success': False,
                            'message': f'Error en mysqldump: {stderr_txt[:300]}'})

    tamano = os.path.getsize(ruta_completa) if os.path.exists(ruta_completa) else 0
    _cerrar_registro(id_resp, 'Exitoso', tamano=tamano)

    return jsonify({
        'success': True,
        'message': f'Respaldo {tipo_respaldo} generado correctamente.',
        'archivo': nombre_archivo,
        'tamano':  _fmt_tamano(tamano),
        'ruta':    ruta_completa,
    })


@respaldos.route('/respaldos/restaurar', methods=['POST'])
@solo_administrador
def restaurar():
    if 'archivo_sql' not in request.files:
        return jsonify({'success': False, 'message': 'No se recibió ningún archivo'})

    archivo       = request.files['archivo_sql']
    observaciones = request.form.get('observaciones', '').strip()[:500]

    if not archivo or archivo.filename == '':
        return jsonify({'success': False, 'message': 'Archivo vacío'})
    if not archivo.filename.lower().endswith('.sql'):
        return jsonify({'success': False, 'message': 'Solo se permiten archivos .sql'})

    contenido = archivo.read()
    if len(contenido) > MAX_RESTORE_SIZE:
        return jsonify({'success': False,
                        'message': f'El archivo supera el límite de {MAX_RESTORE_SIZE//(1024*1024)} MB'})

    contenido_str = contenido.decode('utf-8', errors='replace')
    if not re.search(r'(INSERT|CREATE|ALTER|DROP|UPDATE)\s', contenido_str, re.IGNORECASE):
        return jsonify({'success': False, 'message': 'El archivo no parece un script SQL válido'})

    for p in [r'GRANT\s', r'CREATE\s+USER', r'DROP\s+USER',
              r'FLUSH\s+PRIVILEGES', r'INTO\s+OUTFILE',
              r'LOAD\s+DATA', r'SYSTEM\s*\(']:
        if re.search(p, contenido_str, re.IGNORECASE):
            return jsonify({'success': False,
                            'message': 'El archivo contiene instrucciones no permitidas'})

    try:
        _buscar_ejecutable('mysql')
    except FileNotFoundError as e:
        return jsonify({'success': False, 'message': str(e)})

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_f  = _nombre_seguro(f"restore_{ts}.sql")
    _asegurar_directorio(BACKUP_BASE_DIR)
    ruta_tmp  = os.path.join(os.path.realpath(BACKUP_BASE_DIR), nombre_f)

    try:
        with open(ruta_tmp, 'wb') as f:
            f.write(contenido)
    except OSError as e:
        return jsonify({'success': False, 'message': f'Error guardando archivo: {e}'})

    id_resp = _registrar_inicio(
        tipo='Restauracion', subtipo='Estructura+Datos',
        tablas_str=None, archivo=ruta_tmp, obs=observaciones,
    )

    cmd = _construir_comando_mysql()
    try:
        with open(ruta_tmp, 'rb') as sql_file:
            result = subprocess.run(
                cmd, stdin=sql_file,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600
            )
    except subprocess.TimeoutExpired:
        _cerrar_registro(id_resp, 'Fallido', error='Timeout')
        return jsonify({'success': False, 'message': 'Tiempo de espera agotado'})
    except Exception as e:
        _cerrar_registro(id_resp, 'Fallido', error=str(e))
        return jsonify({'success': False, 'message': str(e)})

    stderr_txt = result.stderr.decode('utf-8', errors='replace').strip()
    if result.returncode != 0:
        _cerrar_registro(id_resp, 'Fallido', error=stderr_txt)
        return jsonify({'success': False,
                        'message': f'Error en restauración: {stderr_txt[:300]}'})

    tamano = os.path.getsize(ruta_tmp) if os.path.exists(ruta_tmp) else 0
    _cerrar_registro(id_resp, 'Exitoso', tamano=tamano)
    return jsonify({'success': True,
                    'message': 'Restauración completada correctamente.',
                    'archivo': nombre_f})


@respaldos.route('/respaldos/descargar/<int:id_respaldo>', methods=['GET'])
@solo_administrador
def descargar(id_respaldo):
    try:
        row = db.session.execute(
            text("SELECT archivo, estado FROM bitacora_respaldos WHERE idRespaldo = :id"),
            {'id': id_respaldo}
        ).fetchone()
    except Exception:
        flash('Error buscando el respaldo.', 'danger')
        return redirect(url_for('respaldos.index'))

    if not row:
        flash('Respaldo no encontrado.', 'danger')
        return redirect(url_for('respaldos.index'))

    ruta_archivo, estado = row[0], row[1]
    if estado != 'Exitoso':
        flash('Solo se pueden descargar respaldos exitosos.', 'warning')
        return redirect(url_for('respaldos.index'))

    ruta_real = os.path.realpath(ruta_archivo)
    base_real  = os.path.realpath(BACKUP_BASE_DIR)
    if not ruta_real.startswith(base_real):
        flash('Ruta de archivo no permitida.', 'danger')
        return redirect(url_for('respaldos.index'))
    if not os.path.exists(ruta_real):
        flash('El archivo ya no existe en el servidor.', 'danger')
        return redirect(url_for('respaldos.index'))

    return send_file(ruta_real, as_attachment=True,
                     download_name=os.path.basename(ruta_real),
                     mimetype='application/octet-stream')


@respaldos.route('/respaldos/bitacora', methods=['GET'])
@solo_administrador
def bitacora():
    tipo    = request.args.get('tipo', '')   or None
    estado  = request.args.get('estado', '') or None
    fecha_i = request.args.get('fecha_ini', '') or None
    fecha_f = request.args.get('fecha_fin', '') or None

    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except (ValueError, TypeError):
        pagina = 1

    por_pagina = BITACORA_POR_PAGINA
    offset     = (pagina - 1) * por_pagina

    for f in [fecha_i, fecha_f]:
        if f and not re.match(r'^\d{4}-\d{2}-\d{2}$', f):
            return jsonify({'success': False, 'message': 'Formato de fecha inválido'})

    try:
        # Total de registros para paginación
        total_row = db.session.execute(
            text(
                "SELECT COUNT(*) FROM bitacora_respaldos br "
                "JOIN usuarios u ON u.idUsuario = br.usuarioId "
                "WHERE (:tipo   IS NULL OR br.tipo   = :tipo) "
                "  AND (:estado IS NULL OR br.estado = :estado) "
                "  AND (:fi IS NULL OR DATE(br.fecha_inicio) >= :fi) "
                "  AND (:ff IS NULL OR DATE(br.fecha_inicio) <= :ff)"
            ),
            {'tipo': tipo, 'estado': estado, 'fi': fecha_i, 'ff': fecha_f}
        ).fetchone()

        total = int(total_row[0]) if total_row else 0
        total_paginas = max(1, math.ceil(total / por_pagina))

        rows = db.session.execute(
            text(
                "SELECT br.idRespaldo, br.tipo, br.subtipo, br.tablas, br.archivo, "
                "br.tamano_bytes, br.estado, br.detalle_error, br.fecha_referencia, "
                "br.fecha_inicio, br.fecha_fin, br.duracion_seg, br.observaciones, "
                "u.nombre, br.ip "
                "FROM bitacora_respaldos br "
                "JOIN usuarios u ON u.idUsuario = br.usuarioId "
                "WHERE (:tipo   IS NULL OR br.tipo   = :tipo) "
                "  AND (:estado IS NULL OR br.estado = :estado) "
                "  AND (:fi IS NULL OR DATE(br.fecha_inicio) >= :fi) "
                "  AND (:ff IS NULL OR DATE(br.fecha_inicio) <= :ff) "
                "ORDER BY br.fecha_inicio DESC "
                "LIMIT :lim OFFSET :off"
            ),
            {'tipo': tipo, 'estado': estado,
             'fi': fecha_i, 'ff': fecha_f,
             'lim': por_pagina, 'off': offset}
        ).fetchall()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

    return jsonify({
        'success': True,
        'total': total,
        'pagina': pagina,
        'total_paginas': total_paginas,
        'por_pagina': por_pagina,
        'data': [{
            'id':            r[0],
            'tipo':          r[1],
            'subtipo':       r[2],
            'tablas':        r[3] or 'Todas',
            'archivo':       os.path.basename(r[4]) if r[4] else '',
            'tamano':        _fmt_tamano(r[5] or 0),
            'estado':        r[6],
            'error':         r[7] or '',
            'fecha_ref':     str(r[8]) if r[8] else '',
            'fecha_inicio':  str(r[9]) if r[9] else '',
            'fecha_fin':     str(r[10]) if r[10] else '',
            'duracion':      r[11] or 0,
            'observaciones': r[12] or '',
            'usuario':       r[13] or '',
        } for r in rows]
    })


@respaldos.route('/respaldos/tablas', methods=['GET'])
@solo_administrador
def listar_tablas():
    return jsonify({'success': True, 'tablas': _obtener_todas_tablas()})


@respaldos.route('/respaldos/verificar-tools', methods=['GET'])
@solo_administrador
def verificar_tools():
    resultado = {}
    for herramienta in ['mysqldump', 'mysql']:
        try:
            ruta = _buscar_ejecutable(herramienta)
            resultado[herramienta] = {'disponible': True, 'ruta': ruta}
        except FileNotFoundError as e:
            resultado[herramienta] = {'disponible': False, 'error': str(e)}
    return jsonify({'success': True, 'tools': resultado})