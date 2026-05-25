import json
import logging
from typing import Dict, Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

if HAS_GENAI and settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

def get_predictions(data: Dict[str, Any]) -> Dict[str, Any]:
    if not HAS_GENAI or not settings.gemini_api_key:
        return {
            "tendencia_ventas": "No se ha configurado la API Key de Gemini o no se encuentra la librería.",
            "recomendaciones_comprar": [],
            "productos_estancados": []
        }
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Using a modern available model for fast and robust generation
            model = genai.GenerativeModel('gemini-flash-latest')
            prompt = f"""
            Actúa como un experto en análisis de datos de retail y analista de negocios.
            Aquí tienes los datos de las ventas e inventario del último mes (y su comparación) de una tienda:
            
            {json.dumps(data, indent=2, default=str)}
            
            Basado en esta información, realiza predicciones de ventas y sugerencias de inventario.
            
            Debes devolver ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta (sin formato Markdown, sin comillas invertidas, solo JSON puro):
            {{
                "tendencia_ventas": "Explicación de la tendencia de ventas estimada para los próximos días/semanas basándote en los datos.",
                "recomendaciones_comprar": [
                    {{
                        "producto": "Nombre del producto",
                        "motivo": "Por qué se sugiere comprar o aumentar stock",
                        "accion_sugerida": "Acción específica recomendada (ej. Aumentar stock máximo a 50 unidades)"
                    }}
                ],
                "productos_estancados": [
                    {{
                        "producto": "Nombre del producto",
                        "motivo": "Por qué se considera estancado",
                        "accion_sugerida": "Acción específica recomendada (ej. Aplicar descuento del 10%)"
                    }}
                ]
            }}
            
            Asegúrate de incluir hasta 5 recomendaciones para comprar y hasta 5 productos estancados, enfocándote en los más críticos o representativos.
            """
            
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
                
            return json.loads(text.strip())
            
        except Exception as e:
            logger.error(f"Error calling Gemini AI (intento {attempt + 1}/{max_retries}): {str(e)}")
            import time
            time.sleep(2) # Esperar un poco antes de reintentar
            
    # Si llega aquí es porque falló los 3 intentos
    return {
        "tendencia_ventas": "Hubo un error al generar las predicciones con la Inteligencia Artificial después de 3 intentos.",
        "recomendaciones_comprar": [],
        "productos_estancados": []
    }
