# src/state_manager/sql/query_loader.py
"""
Implementación del QueryLoader.
"""
import os
import re
from typing import Dict

class QueryLoader:
    """Carga y cachea queries SQL por nombre desde archivos .sql"""

    def __init__(self, schema: str = 'etl_log'):
        """
        Inicializa el cargador.

        Args:
            schema: Schema de BD para reemplazar {{schema}} en queries
        """
        self.schema = schema
        self._cache: Dict[str, str] = {}  # Diccionario: nombre → SQL
        self._cargar_todas_las_queries()

    def _cargar_todas_las_queries(self):
        """Carga todas las queries de archivos .sql en la carpeta sql/"""
        directorio_actual = os.path.dirname(__file__)
        directorio_sql = os.path.join(directorio_actual, 'sql')

        # Buscar todos los archivos .sql
        archivos_sql = [
            f for f in os.listdir(directorio_sql)
            if f.endswith('.sql')
        ]

        if not archivos_sql:
            print("⚠️  No se encontraron archivos .sql")
            return

        print(f"📂 Cargando {len(archivos_sql)} archivo(s) SQL...")

        for archivo_sql in archivos_sql:
            ruta_completa = os.path.join(directorio_sql, archivo_sql)
            self._cargar_queries_desde_archivo(ruta_completa)

    def _cargar_queries_desde_archivo(self, ruta_archivo: str):
        """
        Extrae y cachea queries nombradas de un archivo .sql.

        Formato esperado:
            -- name: nombre_query
            SQL_AQUI;

            -- name: otra_query
            MAS_SQL_AQUI;
        """
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
                contenido = archivo.read()

            # Reemplazar {{schema}} con el schema real
            contenido = contenido.replace('{{schema}}', self.schema)

            # Buscar patron: -- name: query_name\nSQL
            patron = r'--\s*name:\s*(\w+)\s*\n(.*?)(?=\n--\s*name:|\Z)'

            coincidencias = list(re.finditer(patron, contenido, re.DOTALL))

            if not coincidencias:
                print(f"   ⚠️  {os.path.basename(ruta_archivo)}: Sin queries nombradas")
                return

            for coincidencia in coincidencias:
                nombre_query = coincidencia.group(1).strip()
                sql_crudo = coincidencia.group(2).strip()

                # Limpiar el SQL
                sql_limpio = self._limpiar_query(sql_crudo)

                if sql_limpio:
                    self._cache[nombre_query] = sql_limpio
                    print(f"   ✅ {nombre_query}")
                else:
                    print(f"   ⚠️  {nombre_query}: Query vacía")

        except ImportError as error:
            print(f"❌ Error cargando {ruta_archivo}: {error}")

    def _limpiar_query(self, sql: str) -> str:
        """Limpia comentarios y espacios innecesarios del SQL"""
        # Dividir en líneas y quitar comentarios (-- comentario)
        lineas = sql.split('\n')
        lineas_limpias = []

        for linea in lineas:
            # Quitar todo después de '--' (comentario)
            if '--' in linea:
                linea = linea.split('--')[0]
            linea = linea.strip()
            if linea:  # Solo agregar si no está vacía
                lineas_limpias.append(linea)

        # Unir y normalizar espacios
        query_limpia = ' '.join(lineas_limpias)
        query_limpia = re.sub(r'\s+', ' ', query_limpia).strip()

        # Agregar ';' al final si no tiene
        if query_limpia and not query_limpia.endswith(';'):
            query_limpia += ';'

        return query_limpia

    def obtener(self, nombre_query: str) -> str:
        """
        Obtiene una query SQL por nombre.

        Args:
            nombre_query: Nombre de la query a obtener

        Returns:
            Query SQL lista para usar con parámetros ?

        Raises:
            KeyError: Si la query no existe
        """
        if nombre_query not in self._cache:
            disponibles = ', '.join(sorted(self._cache.keys()))
            raise KeyError(
                f"Query '{nombre_query}' no encontrada. "
                f"Disponibles: {disponibles}"
            )

        return self._cache[nombre_query]

    # Métodos especiales para uso conveniente
    def __getitem__(self, nombre_query: str) -> str:
        """Permite usar queries['nombre'] en lugar de queries.obtener('nombre')"""
        return self.obtener(nombre_query)

    def __contains__(self, nombre_query: str) -> bool:
        """Permite usar 'nombre' in queries"""
        return nombre_query in self._cache

    @property
    def queries_disponibles(self) -> list:
        """Lista de todos los nombres de queries disponibles"""
        return sorted(self._cache.keys())

    def __repr__(self) -> str:
        return f"QueryLoader(schema='{self.schema}', queries={len(self._cache)})"

    def __len__(self) -> int:
        """Cantidad de queries cargadas"""
        return len(self._cache)


def create_query_loader(schema: str = 'etl_log') -> QueryLoader:
    """
    Crea una instancia de QueryLoader.

    Args:
        schema: Schema de base de datos para las queries

    Returns:
        QueryLoader configurado y listo para usar
    """
    return QueryLoader(schema)
