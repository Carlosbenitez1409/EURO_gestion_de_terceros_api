"""
Servicio para realizar consultas a Stradata
Integrado con el sistema de terceros - consulta personas asociadas
Actualizado con código optimizado del notebook
"""
import csv
import time
import random
import requests
import urllib3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from tempfile import NamedTemporaryFile
import os
from requests_toolbelt.multipart.encoder import MultipartEncoder

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class StrataDataService:
    """Servicio para consultar Stradata con Selenium - integrado con terceros"""
    
    BASE_LOGIN_URL = "https://sdssso.stradata.com.co/signin?serviceURL=https://sds.stradata.com.co/"
    INICIAR_URL = "https://sds.stradata.com.co/app/unifiedquery/iniciar_ejecucion/"
    LOGS_URL = "https://sds.stradata.com.co/app/logs/find?limit=100"
    
    BUSCAR_ENDPOINTS = [
        "https://sds.stradata.com.co/app/lista/buscar_masivo",
        "https://sds.stradata.com.co/app/medios/buscar_masivo",
        "https://sds.stradata.com.co/app/jep/buscar_masivo",
        "https://sds.stradata.com.co/app/registraduria/buscar_masivo",
        "https://sds.stradata.com.co/app/buscador_web/buscar_masivo",
    ]
    
    BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    REQ_HEADERS = {
        "Referer": "https://sds.stradata.com.co/app/UnifiedQuery",
        "Origin": "https://sds.stradata.com.co",
    }
    
    def __init__(self):
        self.session: Optional[requests.Session] = None
        self.is_authenticated = False
        
    def _make_driver(self, headless: bool = True) -> webdriver.Chrome:
        """Crear driver de Chrome con configuración optimizada"""
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"user-agent={self.BROWSER_UA}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return webdriver.Chrome(options=options)
        
    def login(self, username: str, password: str) -> bool:
        """
        Realiza login en Stradata usando Selenium y obtiene sesión con cookies
        """
        try:
            logger.info(f"Iniciando login en Stradata para usuario: {username}")
            
            driver = self._make_driver()
            driver.get(self.BASE_LOGIN_URL)
            
            # Esperar y completar formulario de login
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "usuario"))
            ).send_keys(username)
            
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "clave"))
            ).send_keys(password + Keys.RETURN)
            
            time.sleep(5)
            
            # Verificar redirección exitosa
            if "sds.stradata.com.co" not in driver.current_url:
                driver.quit()
                logger.error("Login falló - no se redirigió correctamente")
                return False
            
            # Obtener cookies y crear sesión
            cookies = driver.get_cookies()
            driver.quit()
            
            self.session = requests.Session()
            for cookie in cookies:
                self.session.cookies.set(cookie.get("name"), cookie.get("value"))
            
            self.session.headers.update({"User-Agent": self.BROWSER_UA})
            self.is_authenticated = True
            
            logger.info("Login exitoso en Stradata")
            return True
            
        except Exception as e:
            logger.error(f"Error en login Stradata: {str(e)}")
            if 'driver' in locals():
                driver.quit()
            return False
    
    def _generar_codigo_unico(self):
        """Generar código único para rastreo de consultas"""
        return str(int(time.time() * 1000)) + str(random.randint(100, 999))
    
    def _generar_csv_temporal(self, personas: List[Dict[str, str]]) -> str:
        """
        Genera archivo CSV temporal con las personas a consultar
        Formato: nombre;identificacion;tipo
        """
        temp_file = NamedTemporaryFile(mode='w', suffix='.csv', delete=False, 
                                      encoding='utf-8', newline='')
        
        try:
            writer = csv.writer(temp_file, delimiter=';')
            writer.writerow(["nombre", "identificacion", "tipo"])
            
            for persona in personas:
                writer.writerow([
                    persona.get("nombre", ""),
                    persona.get("identificacion", ""),
                    persona.get("tipo", "C")  # Por defecto Cédula
                ])
            
            temp_file.close()
            logger.info(f"CSV temporal generado con {len(personas)} personas: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            temp_file.close()
            logger.error(f"Error generando CSV temporal: {str(e)}")
            raise
    
    def ejecutar_consulta_tercero(self, tercero_data: Dict[str, Any], username: str = None) -> Dict[str, Any]:
        """
        Ejecuta consulta masiva para un tercero y todas sus personas asociadas
        Ahora incluye espera de logs y seguimiento completo del proceso
        """
        if not self.is_authenticated or not self.session:
            return {
                'success': False,
                'error': 'No hay sesión autenticada en Stradata'
            }
        
        try:
            # Recopilar todas las personas a consultar
            personas = self._recopilar_personas_tercero(tercero_data)
            
            if not personas:
                return {
                    'success': False,
                    'error': 'No se encontraron personas para consultar'
                }
            
            # Generar CSV temporal
            archivo_csv = self._generar_csv_temporal(personas)
            
            try:
                # Enviar consulta a Stradata
                resultado_envio = self._enviar_consulta_masiva(archivo_csv)
                
                if not resultado_envio.get('id_busqueda'):
                    return {
                        'success': False,
                        'error': 'No se obtuvo id_busqueda de Stradata',
                        'respuesta_stradata': resultado_envio
                    }
                
                # Disparar búsquedas en todos los servicios
                resultado_busquedas = self._disparar_busquedas(resultado_envio['id_busqueda'])
                
                # No esperamos logs ya que Stradata ejecuta en background
                
                return {
                    'success': True,
                    'message': 'Proceso finalizado: consultas disparadas. Stradata seguirá ejecutando en background y enviará resultados al correo.',
                    'data': {
                        'personas_consultadas': len(personas),
                        'personas': [f"{p['nombre']} ({p['identificacion']})" for p in personas],
                        'id_busqueda': resultado_envio['id_busqueda'],
                        'codigo_busqueda': resultado_envio['codigo_busqueda'],
                        'id_plantilla': resultado_envio['id_plantilla'],
                        'servicios': resultado_busquedas['servicios_disparados'],
                        'resumen_servicios': resultado_busquedas['resumen']
                    }
                }
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(archivo_csv)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error en consulta tercero: {str(e)}")
            return {
                'success': False,
                'error': f'Error ejecutando consulta: {str(e)}'
            }
    
    def _recopilar_personas_tercero(self, tercero_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Recopila todas las personas asociadas al tercero para consulta
        Actualizado para manejar tanto personas naturales como jurídicas
        """
        personas = []
        
        # 1. Datos básicos del tercero
        if tercero_data.get('numero_documento'):
            # Determinar el nombre según el tipo de persona
            if tercero_data.get('tipo_persona') == 'juridica':
                # Para persona jurídica, usar razón social o nombres
                nombre_completo = (tercero_data.get('razon_social') or 
                                 tercero_data.get('nombres') or 
                                 tercero_data.get('nombre_completo', '')).strip()
                tipo_doc = 'NIT'  # Personas jurídicas siempre NIT
            else:
                # Para persona natural, usar nombres y apellidos
                nombre_completo = f"{tercero_data.get('nombres', '')} {tercero_data.get('apellidos', '')}".strip()
                # Mapear tipo de documento para persona natural
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'pasaporte': 'PP',
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE', 
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(tercero_data.get('tipo_documento', 'CC'), 'CC')
            
            if nombre_completo:  # Solo agregar si hay nombre
                personas.append({
                    'nombre': nombre_completo,
                    'identificacion': tercero_data['numero_documento'],
                    'tipo': tipo_doc,
                    'categoria': f'Tercero principal ({tercero_data.get("tipo_persona", "natural")})'
                })

        # 2. Representantes legales
        representantes = tercero_data.get('representantes_legales', []) or tercero_data.get('representantes', [])
        for rep in representantes:
            if rep.get('numero_identificacion') or rep.get('numero_documento'):
                # Obtener nombre del representante
                nombre_rep = (rep.get('nombre_completo') or 
                            rep.get('nombres_completo') or
                            f"{rep.get('nombres', '')} {rep.get('apellidos', '')}").strip()
                
                # Obtener número de identificación
                numero_id = rep.get('numero_identificacion') or rep.get('numero_documento')
                
                # Mapear tipo de documento
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'pasaporte': 'PP',
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE',
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(rep.get('tipo_identificacion', 'CC'), 'CC')
                
                if nombre_rep and numero_id:
                    personas.append({
                        'nombre': nombre_rep,
                        'identificacion': numero_id,
                        'tipo': tipo_doc,
                        'categoria': 'Representante legal'
                    })

        # 3. Información PEP
        pep_data = tercero_data.get('informacion_pep', []) or tercero_data.get('informacion_pep_nueva', [])
        for pep in pep_data:
            if pep.get('numero_identificacion') and pep.get('nombre'):
                # Mapear tipo de documento
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE', 
                    'pasaporte': 'PP',
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE',
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(pep.get('tipo', 'CC'), 'CC')
                
                personas.append({
                    'nombre': pep['nombre'],
                    'identificacion': pep['numero_identificacion'],
                    'tipo': tipo_doc,
                    'categoria': f'Persona PEP - {pep.get("cargo", "N/A")}'
                })

        # 4. Accionistas y subaccionistas
        accionistas = tercero_data.get('accionistas', [])
        for accionista in accionistas:
            if accionista.get('numero_identificacion') and accionista.get('nombre'):
                # Mapear tipo de documento
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'pasaporte': 'PP', 
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE',
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(accionista.get('tipo_identificacion', 'CC'), 'CC')
                
                porcentaje = accionista.get('porcentaje_participacion', accionista.get('porcentaje', 0))
                personas.append({
                    'nombre': accionista['nombre'],
                    'identificacion': accionista['numero_identificacion'],
                    'tipo': tipo_doc,
                    'categoria': f'Accionista principal ({porcentaje}%)'
                })
        
        # 5. Subaccionistas (accionistas de accionistas)
        subaccionistas = tercero_data.get('subaccionistas', [])
        for subaccionista in subaccionistas:
            if subaccionista.get('numero_identificacion') and subaccionista.get('nombre'):
                # Mapear tipo de documento
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'pasaporte': 'PP', 
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE',
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(subaccionista.get('tipo_identificacion', 'CC'), 'CC')
                
                porcentaje = subaccionista.get('porcentaje_participacion', subaccionista.get('porcentaje', 0))
                accionista_padre = subaccionista.get('accionista_padre', 'N/A')
                nivel = subaccionista.get('nivel', 1)
                
                personas.append({
                    'nombre': subaccionista['nombre'],
                    'identificacion': subaccionista['numero_identificacion'],
                    'tipo': tipo_doc,
                    'categoria': f'Subaccionista nivel {nivel} ({porcentaje}%) - Sub de: {accionista_padre}'
                })
        
        # 6. Composición accionaria (para compatibilidad con diferentes estructuras)
        composicion = tercero_data.get('composicion_accionaria', [])
        for comp in composicion:
            if comp.get('numero_identificacion') and comp.get('nombre_razon_social'):
                tipo_doc_mapping = {
                    'cedula_ciudadania': 'CC',
                    'cedula_extranjeria': 'CE',
                    'pasaporte': 'PP',
                    'nit': 'NIT',
                    'CC': 'CC',
                    'CE': 'CE', 
                    'PP': 'PP',
                    'NIT': 'NIT'
                }
                tipo_doc = tipo_doc_mapping.get(comp.get('tipo_identificacion', 'CC'), 'CC')
                
                porcentaje = comp.get('porcentaje_participacion', 0)
                personas.append({
                    'nombre': comp['nombre_razon_social'],
                    'identificacion': comp['numero_identificacion'],
                    'tipo': tipo_doc,
                    'categoria': f'Composición accionaria ({porcentaje}%)'
                })

        # Eliminar duplicados por número de documento
        personas_unicas = []
        documentos_vistos = set()
        
        for persona in personas:
            doc = persona['identificacion']
            if doc not in documentos_vistos:
                documentos_vistos.add(doc)
                personas_unicas.append(persona)
        
        logger.info(f"Recopiladas {len(personas_unicas)} personas únicas para consulta")
        for persona in personas_unicas:
            logger.info(f"  - {persona['nombre']} ({persona['tipo']}: {persona['identificacion']}) - {persona['categoria']}")
        
        return personas_unicas
    
    def _enviar_consulta_masiva(self, archivo_csv: str) -> Dict[str, Any]:
        """Envía el archivo CSV a Stradata para ejecutar consulta masiva con código único"""
        try:
            codigo = self._generar_codigo_unico()  # Código único para rastreo
            
            with open(archivo_csv, "rb") as csv_file:
                m = MultipartEncoder(
                    fields={
                        "codigo": codigo,
                        "tipo_busqueda": "lote",
                        "listas": "101,74,42,14,155,29,28,32,177,132,108,51,138,52,15,53,180,65,105,68,128,73,134,159,151,165,157,79,161,80,174,81,178,82,182,83,1,84,107,86,127,87,130,88,133,89,135,90,139,91,152,92,156,93,158,94,160,95,162,96,173,97,175,98,176,99,179,100,181,184,183,104,185,186,187,188,126,150,171,163,164,172,169,167,166,168,170",
                        "medios": "4,3,2,6,5",
                        "rucom": "",
                        "jep": "Buga,Bogota,Bucaramanga,Barranquilla,Armenia,SantaMarta,Valledupar,Cartagena,Cali,Manizales,Ibague,Medellin,Monteria,Florencia,Popayan,Pereira,Quibdo,Neiva,Palmira,Pasto,Villavicencio,Tunja",
                        "procesosrj": "",
                        "motor": "2",
                        "prompt": "",
                        "parcial": "null",
                        "servicios": "BUSCADOR,FISC,JEP,REGIS,NEWS",
                        "porcentaje_nom": "85",
                        "porcentaje_id": "100",
                        "archivo_clientes": (os.path.basename(archivo_csv), csv_file, "text/csv"),
                        "separador": ";",
                    }
                )
                
                resp = self.session.post(
                    self.INICIAR_URL, 
                    headers={"Content-Type": m.content_type}, 
                    data=m, 
                    verify=False,
                    timeout=60
                )
            
            data = resp.json()
            busqueda = data.get("busqueda", {})
            id_busqueda = busqueda.get("id")
            id_plantilla = data.get("id_plantilla")
            
            logger.info(f"Consulta enviada: id_busqueda={id_busqueda}, codigo={codigo}, plantilla={id_plantilla}")
            
            return {
                'id_busqueda': id_busqueda,
                'id_plantilla': id_plantilla,
                'codigo_busqueda': codigo,
                'respuesta_completa': data
            }
                    
        except Exception as e:
            logger.error(f"Error enviando consulta masiva: {str(e)}")
            raise
    
    def _disparar_busquedas(self, id_busqueda: int) -> Dict[str, Any]:
        """Dispara todas las búsquedas en los diferentes servicios de Stradata"""
        resultados = {}
        servicios_exitosos = 0
        servicios_fallidos = 0
        
        for url in self.BUSCAR_ENDPOINTS:
            servicio_nombre = url.split('/')[-2]  # Extrae el nombre del servicio de la URL
            try:
                resp = self.session.post(
                    url, 
                    json={"id_busqueda": id_busqueda}, 
                    verify=False, 
                    timeout=180
                )
                resultados[servicio_nombre] = {
                    'status': 'success',
                    'status_code': resp.status_code,
                    'url': url
                }
                servicios_exitosos += 1
                logger.info(f"[OK] {servicio_nombre} disparado exitosamente")
            except Exception as e:
                resultados[servicio_nombre] = {
                    'status': 'error',
                    'error': str(e),
                    'url': url
                }
                servicios_fallidos += 1
                logger.error(f"[ERROR] {servicio_nombre} error: {e}")
            time.sleep(1)
        
        return {
            'servicios_disparados': resultados,
            'resumen': {
                'total': len(self.BUSCAR_ENDPOINTS),
                'exitosos': servicios_exitosos,
                'fallidos': servicios_fallidos
            }
        }
    
    def _esperar_logs(self, codigo_busqueda: str, username: str, max_wait: int = 300) -> Optional[Dict]:
        """
        Espera y busca los logs de ejecución por código de búsqueda
        Retorna información de logs cuando estén disponibles
        """
        inicio = time.time()
        logger.info(f"Esperando logs para codigo={codigo_busqueda} (timeout={max_wait}s)")
        
        for intento in range(max_wait // 10):
            try:
                resp = self.session.post(self.LOGS_URL, json={
                    "buscar": "individuales",
                    "fecha": {
                        "desde": time.strftime("%Y-%m-%d"), 
                        "hasta": time.strftime("%Y-%m-%d")
                    },
                    "usuarios": [username]
                }, verify=False)

                data = resp.json()
                elapsed = int(time.time() - inicio)

                for r in data.get("results", []):
                    if r.get("txtCodigoBusqueda") == codigo_busqueda:
                        archivos = r.get("archivos", [])
                        servicios = r.get("servicios", [])
                        logger.info(f"[OK] Logs encontrados en {elapsed}s -> {len(archivos)} archivos, servicios={','.join(servicios)}")
                        return r

                logger.info(f"[{elapsed}s] Aun sin logs para codigo={codigo_busqueda} (intento {intento+1})")
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error consultando logs: {str(e)}")
                time.sleep(10)

        logger.warning(f"Timeout ({max_wait}s) esperando logs para codigo={codigo_busqueda}")
        return None
        """
        Ejecuta una consulta por lotes en Stradata
        
        Args:
            personas: Lista de diccionarios con 'nombre', 'identificacion', 'tipo'
        
        Returns:
            Diccionario con el resultado de la consulta
        """
        try:
            if not self.is_authenticated:
                return {
                    'success': False,
                    'error': 'No autenticado',
                    'message': 'Debe hacer login primero'
                }
            
            # Construir CSV en memoria
            csv_data = "nombre;identificacion;tipo\n"
            for persona in personas:
                csv_data += f"{persona['nombre']};{persona['identificacion']};{persona['tipo']}\n"
            
            # Parámetros fijos de búsqueda (basados en tu notebook)
            data = {
                "codigo": "26311757444202039",
                "tipo_busqueda": "lote",
                "listas": "101,74,42,14,155,29,28,32,177,132,108,51,138,52,15,53,180,65,105,68,128,73,134,159,151,165,157,79,161,80,174,81,178,82,182,83,1,84,107,86,127,87,130,88,133,89,135,90,139,91,152,92,156,93,158,94,160,95,162,96,173,97,175,98,176,99,179,100,181,184,183,104,185,186,187,188,126,150,171,163,164,172,169,167,166,168,170",
                "medios": "4,3,2,6,5",
                "rucom": "",
                "jep": "Buga,Bogota,Bucaramanga,Barranquilla,Armenia,SantaMarta,Valledupar,Cartagena,Cali,Manizales,Ibague,Medellin,Monteria,Florencia,Popayan,Pereira,Quibdo,Neiva,Palmira,Pasto,Villavicencio,Tunja",
                "procesosrj": "",
                "motor": "2",
                "prompt": "",
                "parcial": "null",
                "servicios": "BUSCADOR,FISC,JEP,REGIS,NEWS",
                "porcentaje_nom": "85",
                "porcentaje_id": "100",
                "separador": ";"
            }
            
            # Archivo CSV adjunto
            files = {
                "archivo_clientes": ("lote.csv", csv_data, "text/csv")
            }
            
            # Enviar ejecución
            resp_exec = self.session.post(
                self.EXEC_URL, 
                data=data, 
                files=files,
                timeout=60
            )
            
            logger.info(f"Consulta Stradata ejecutada. Status: {resp_exec.status_code}")
            
            if resp_exec.status_code == 200:
                try:
                    result = resp_exec.json()
                    return {
                        'success': True,
                        'result': result,
                        'personas_consultadas': len(personas),
                        'message': 'Consulta ejecutada exitosamente. El resultado será enviado al correo asociado.'
                    }
                except Exception as json_error:
                    logger.warning(f"Respuesta no es JSON válido: {str(json_error)}")
                    return {
                        'success': True,
                        'result': resp_exec.text,
                        'personas_consultadas': len(personas),
                        'message': 'Consulta ejecutada. Respuesta no JSON pero status 200.'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {resp_exec.status_code}',
                    'message': resp_exec.text[:500] if resp_exec.text else 'Sin respuesta'
                }
                
        except Exception as e:
            logger.error(f"Error ejecutando consulta Stradata: {str(e)}")
            return {
                'success': False,
                'error': 'Error interno',
                'message': str(e)
            }
    
    def ejecutar_consulta_personas(self, personas: List[Dict[str, str]], username: str = None) -> Dict[str, Any]:
        """
        Ejecuta consulta masiva directamente con una lista de personas
        Ideal para consultas desde el sistema de usuarios GH
        """
        if not self.is_authenticated or not self.session:
            return {
                'success': False,
                'error': 'No hay sesión autenticada en Stradata'
            }
        
        try:
            if not personas:
                return {
                    'success': False,
                    'error': 'No se proporcionaron personas para consultar'
                }
            
            logger.info(f"Consultando {len(personas)} personas directamente en Stradata")
            
            # Generar CSV temporal con las personas
            archivo_csv = self._generar_csv_temporal(personas)
            
            try:
                # Enviar consulta a Stradata
                resultado_envio = self._enviar_consulta_masiva(archivo_csv)
                
                if not resultado_envio.get('id_busqueda'):
                    return {
                        'success': False,
                        'error': 'No se obtuvo id_busqueda de Stradata',
                        'respuesta_stradata': resultado_envio
                    }
                
                # Disparar búsquedas en todos los servicios
                resultado_busquedas = self._disparar_busquedas(resultado_envio['id_busqueda'])
                
                return {
                    'success': True,
                    'message': 'Consulta ejecutada exitosamente. Stradata procesará en background y enviará resultados por correo.',
                    'data': {
                        'personas_consultadas': len(personas),
                        'personas': [f"{p['nombre']} ({p['identificacion']})" for p in personas],
                        'id_busqueda': resultado_envio['id_busqueda'],
                        'codigo_busqueda': resultado_envio['codigo_busqueda'],
                        'id_plantilla': resultado_envio['id_plantilla'],
                        'servicios': resultado_busquedas['servicios_disparados'],
                        'resumen_servicios': resultado_busquedas['resumen']
                    }
                }
                
            finally:
                # Limpiar archivo temporal
                try:
                    import os
                    os.unlink(archivo_csv)
                    logger.info(f"Archivo CSV temporal eliminado: {archivo_csv}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar archivo temporal {archivo_csv}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error ejecutando consulta de personas: {str(e)}")
            return {
                'success': False,
                'error': f'Error ejecutando consulta: {str(e)}'
            }

    def close_session(self):
        """Cierra la sesión"""
        self.session.close()
        self.is_authenticated = False
